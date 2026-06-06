# Interaction Module

Standalone text/voice interaction and semantic workspace memory for the SO-101 care robot.  
Adapted from DimOS (EPFL RoboHack 2026, Unitree Go2 quadruped) for a STATIONARY robotic arm.

## Key Adaptations from DimOS (Quadruped → Stationary Arm)

The original DimOS spatial memory was designed for a mobile robot that **navigates**
through rooms. The SO-101 is a **stationary** arm mounted on a table. Key changes:

| Concept | DimOS (Go2 Quadruped) | SO-101 (Care Arm) |
|---------|----------------------|-------------------|
| Position | Robot base XY from odometry/SLAM | End-effector XYZ from forward kinematics |
| Distance gate | 0.5m (room-scale) | 0.03m (workspace-scale, ~3cm) |
| Time gate | 1.0s | 0.5s |
| Spatial queries | "What's near the kitchen?" | "What was at slot A?" |
| Navigation tools | navigate_with_text, explore | pick_and_place, sort_medicine |
| Query radius | 2.0m (room) | 0.1m (workspace region) |

### Why it still works:

The core of the spatial memory is **CLIP embeddings stored in ChromaDB with XYZ metadata**.
This is robot-agnostic — it doesn't care whether the XYZ comes from wheel odometry or
forward kinematics. The SO-101's wrist camera provides visual frames, and the end-effector
pose (from joint angles + FK) provides the "where" coordinate. The CLIP matching
(text → image, image → image) works identically regardless of robot type.

## Architecture

```
interaction/
├── llm/                 # LLM agent (ask/agent modes + MCP tool calling)
│   ├── provider.py      # Provider-agnostic: Bedrock, OpenAI, EPFL RCP, Ollama
│   └── agent.py         # MCP client + streaming agent loop
├── memory/              # Semantic spatial memory
│   ├── embedding.py     # CLIP embeddings (image + text)
│   ├── visual_memory.py # Image persistence (JPEG → pickle)
│   ├── spatial_vector_db.py  # ChromaDB storage + retrieval
│   └── spatial_memory.py     # Main API: frame+pose → query by text/location
├── speech/              # Speech-to-text
│   └── transcriber.py   # Pluggable: Whisper (local) or AWS Transcribe
└── web/                 # FastAPI endpoints
    └── endpoints.py     # /query/stream, /command/stream, /transcribe
```

## Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn httpx chromadb transformers onnxruntime numpy opencv-python Pillow openai boto3 whisper
```

### 2. Set environment variables

```bash
# LLM Provider — pick one:
export LLM_PROVIDER=bedrock                    # AWS Bedrock (Anthropic Claude)
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
export AWS_REGION=us-west-2
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# OR for OpenAI / EPFL RCP / Ollama:
export LLM_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_API_BASE=https://your-endpoint/v1  # optional
export OPENAI_MODEL=gpt-4o                       # or qwen3.5, gemma-4, etc.

# Speech backend:
export SPEECH_BACKEND=whisper         # local Whisper (default)
# export SPEECH_BACKEND=aws_transcribe  # or AWS Transcribe

# MCP server (robot's tool server):
export DIMOS_MCP_URL=http://localhost:9990/mcp

# CLIP model path (for semantic memory):
export CLIP_MODEL_PATH=/path/to/model.onnx
```

### 3. Use in your robot code

#### Semantic spatial memory

```python
from interaction.memory.spatial_memory import SpatialMemory

# Initialize
mem = SpatialMemory(db_path="/tmp/robot_memory", new_memory=True)

# In your camera+odom loop:
result = mem.process_frame(
    frame=camera_bgr_image,
    position=(odom.x, odom.y, odom.z),
    rotation=(odom.roll, odom.pitch, odom.yaw),
)

# Query:
results = mem.query_by_text("red chair")
results = mem.query_by_location(x=1.5, y=2.0, radius=3.0)
results = mem.spatial_range_retrieval(x=0, y=0, radius=5.0, text="door")

# Tag named locations:
mem.tag_location("kitchen", position=(3.1, 1.2, 0))
loc = mem.find_tagged_location("where is the kitchen")
```

#### LLM agent (ask/agent modes)

```python
from interaction.llm.agent import run_agent_stream

# Agent mode — full tool access (navigate, explore, etc.)
for token in run_agent_stream("go to the kitchen", mode="agent"):
    print(token, end="")

# Ask mode — read-only (observe, query memory, no movement)
for token in run_agent_stream("what do you see?", mode="ask"):
    print(token, end="")
```

#### FastAPI integration

```python
from fastapi import FastAPI
from interaction.web.endpoints import create_router

app = FastAPI()
app.include_router(create_router())
# Now serves: POST /query/stream, POST /command/stream, POST /transcribe
```

#### Speech transcription

```python
from interaction.speech.transcriber import create_transcriber

t = create_transcriber()  # uses SPEECH_BACKEND env
text = t.transcribe(audio_bytes, format="webm")
```

## Adapting to Another Robot

This module is **robot-agnostic**. To integrate with your robot:

### What you provide:

1. **Camera frames** (BGR numpy arrays) — from the SO-101 wrist camera
2. **End-effector pose** (x, y, z, roll, pitch, yaw) — from forward kinematics using joint angles
3. **MCP server** (optional) — if your robot exposes tools via MCP protocol

### What you get:

- Semantic workspace memory that builds as the arm moves and scans
- Natural language queries over what the robot has seen ("where is the Aspirin?")
- Voice input transcription (Whisper)
- LLM agent that can call your robot's tools via MCP

### Integration with SO-101:

```python
import threading
import numpy as np
from interaction.memory.spatial_memory import SpatialMemory
from interaction.llm.agent import run_agent_stream

# 1. Create memory (tuned for arm workspace)
mem = SpatialMemory(
    db_path="./carebot_memory",
    min_distance_threshold=0.03,  # 3cm — workspace scale
    min_time_threshold=0.5,
)

# 2. Compute end-effector pose from joint angles (forward kinematics)
def get_ee_pose(joint_angles: dict) -> tuple:
    """Compute end-effector XYZ + RPY from SO-101 joint angles.
    
    In practice, use so101_kinematics package or a simple DH-parameter chain.
    """
    # Placeholder — replace with actual FK
    import math
    sp = joint_angles.get("shoulder_pan", 0)
    sl = joint_angles.get("shoulder_lift", 0)
    ef = joint_angles.get("elbow_flex", 0)
    # Simplified 3-joint planar approx
    L1, L2, L3 = 0.10, 0.10, 0.08  # link lengths in meters
    x = L1 * math.cos(sl) + L2 * math.cos(sl + ef)
    y = x * math.sin(sp)
    x = x * math.cos(sp)
    z = L1 * math.sin(sl) + L2 * math.sin(sl + ef) + 0.05  # base height
    return (x, y, z, 0, sl + ef, sp)

# 3. In your scan loop:
def memory_loop(camera, joint_state_fn):
    while True:
        frame = camera.read()
        joints = joint_state_fn()
        pose = get_ee_pose(joints)
        mem.process_frame(frame, position=pose[:3], rotation=pose[3:])
        time.sleep(0.3)

# 4. Tag the sorting slots for easy retrieval
mem.tag_location("slot_A_morning", position=(0.15, 0.10, 0.05))
mem.tag_location("slot_B_afternoon", position=(0.15, 0.00, 0.05))
mem.tag_location("slot_C_evening", position=(0.15, -0.10, 0.05))
mem.tag_location("medicine_tray", position=(0.20, 0.0, 0.03))

# 5. Query: "where did I last see Aspirin?"
results = mem.query_by_text("aspirin box")
# → returns frames + EE poses where aspirin-looking objects were seen

# 6. Chat with the robot:
for token in run_agent_stream("pick up the Aspirin and put it in the morning slot"):
    print(token, end="")
```

### If your robot doesn't use MCP:

You can still use the memory module standalone and skip the agent:

```python
# Just semantic memory, no MCP needed
from interaction.memory.spatial_memory import SpatialMemory

mem = SpatialMemory(db_path="./memory")
# ... process frames ...
results = mem.query_by_text("where is the table?")
```

## LLM Provider Details

| Provider | Config | Models |
|----------|--------|--------|
| AWS Bedrock | `LLM_PROVIDER=bedrock` | Claude Sonnet/Opus 4.x |
| OpenAI | `LLM_PROVIDER=openai` | GPT-4o, o1, etc. |
| EPFL RCP | `LLM_PROVIDER=openai` + `OPENAI_API_BASE=...` | Qwen 3.5, Gemma 4 |
| Ollama | `LLM_PROVIDER=openai` + `OPENAI_API_BASE=http://localhost:11434/v1` | Any local model |

## Speech Backend Details

| Backend | Config | Requirements |
|---------|--------|--------------|
| Whisper (local) | `SPEECH_BACKEND=whisper` | `pip install openai-whisper`, runs on GPU/CPU |
| AWS Transcribe | `SPEECH_BACKEND=aws_transcribe` | AWS credentials + S3 bucket |

Your teammate working on Whisper: the `WhisperTranscriber` class uses the standard `whisper` Python package (`github.com/openai/whisper`). Model size configurable: `base`, `small`, `medium`, `large`.
