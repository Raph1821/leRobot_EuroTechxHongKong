# Carebot — AI-Powered Medicine Management Robot (SO-101)

**EuroTech x Hong Kong Hackathon · Munich, June 2026 · AI & Robotics Track**

A stationary SO-101 robotic care arm for elderly home medicine management: identifies medicines via OCR, checks expiration dates, sorts pills into the correct slots, verifies dosage, patrols the workspace for anomalies, and communicates with patients through voice/text — all controlled from a web dashboard.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        WEB DASHBOARD (webapp/)                         │
│   Next.js · 3D Robot Viewer · Schedule · Medications · Interaction    │
│   Manual Control + Gazebo Simulator Diagnostics                       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ WebSocket (ws://localhost:9090)
┌───────────────────────────────▼──────────────────────────────────────┐
│                    ROS2 WebSocket Bridge                               │
│         so_arm_100_web_bridge (joint commands, camera, teleop)         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ ROS2 Topics/Actions
┌───────────────┬───────────────┼───────────────┬──────────────────────┐
│  Gazebo Sim   │  SO-101 HW    │   MoveIt2     │   Isaac Sim          │
│  (Harmonic)   │  (feetech)    │  (planning)   │   (optional)         │
└───────────────┴───────────────┴───────────────┴──────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                         AI PIPELINE (ai/)                              │
│   PaddleOCR → Medicine Name → Expiration Date → Scan State Machine    │
│   Speech Listener → Emergency Detection → Fall Detection (patrol)     │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      INTERACTION MODULE (interaction/)                 │
│   LLM Agent (Bedrock/OpenAI/Ollama) + MCP Tool Calling                │
│   Semantic Spatial Memory (CLIP + ChromaDB)                           │
│   Speech-to-Text (Whisper / AWS Transcribe)                           │
│   FastAPI endpoints (/query/stream, /command/stream, /transcribe)      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (minh/)                              │
│   Medicine Orchestrator: scan → sort → dose → verify                  │
│   YOLO11 Pill Detection · GR00T N1.7 Pick & Place Policy              │
│   DDS Communication · Holoscan Real-Time Pipeline                     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
leRobot_EuroTechxHongKong/
├── README.md                          # This file
├── requirements.txt                   # Unified Python dependencies
├── Dockerfile                         # Docker build (sim + web)
├── docker-compose.yaml                # Full stack orchestration
│
├── ai/                                # AI vision pipeline (standalone)
│   ├── main.py                        # Live camera loop (OCR + speech + patrol)
│   ├── core/                          # App modes enum
│   ├── patrol/                        # Fall detection, room scanning
│   ├── sorting/                       # Medicine name/expiration parsers, scan state
│   ├── speech/                        # Emergency phrase detector, speech listener
│   └── data/                          # Medicine names database (300+)
│
├── interaction/                       # LLM + memory + voice (robot-agnostic)
│   ├── llm/                           # Provider-agnostic LLM (Bedrock/OpenAI/Ollama)
│   ├── memory/                        # CLIP embeddings + ChromaDB spatial memory
│   ├── speech/                        # Whisper / AWS Transcribe
│   └── web/                           # FastAPI streaming endpoints
│
├── minh/                              # Medicine orchestrator + robot policy
│   ├── medicine_orchestrator.py       # Main entry: scan → sort → dose → verify
│   ├── medicine_robot_config.yaml     # Robot + vision + sorting config
│   ├── sorting/                       # OCR parsers (shared with ai/)
│   ├── vision/                        # YOLO pill detection, dose reader, counter
│   ├── policy/                        # GR00T N1.7 pick-and-place runners
│   ├── dds/                           # DDS publisher/subscriber + schemas
│   ├── holoscan_apps/                 # Real-time deployment operators
│   └── training/                      # GR00T fine-tuning + data conversion
│
├── webapp/                            # Next.js web dashboard
│   ├── app/                           # Pages: overview, control, camera, etc.
│   │   ├── control/                   # Simulation & Manual Control (3D + Gazebo diag)
│   │   ├── interaction/               # Text/voice chat with LLM agent
│   │   ├── camera/                    # Live camera feeds
│   │   ├── schedule/                  # Prescription calendar
│   │   ├── medications/               # Inventory + expiration tracking
│   │   ├── reports/                   # Stats, alerts, emergency routing
│   │   └── settings/                  # Robot & notification config
│   ├── components/                    # React components
│   │   ├── ManualControl.tsx          # 3D viewer + tabs (control / simulator)
│   │   ├── SimulatorPanel.tsx         # Gazebo physics diagnostics
│   │   ├── RobotViewer.tsx            # Three.js URDF viewer
│   │   └── ControlPanel.tsx           # Joint sliders (sends to real robot)
│   ├── lib/                           # Joints config, store, navigation
│   └── public/so101/                  # URDF + meshes for web 3D viewer
│
├── web_interface/                     # Legacy Vite web UI (ROS2 bridge client)
├── so_arm_100_web_bridge/             # ROS2 ↔ WebSocket bridge node
├── so_arm_100_description/            # URDF + Gazebo xacro
├── so_arm_100_bringup/                # Launch files (sim + hardware)
├── so_arm_100_moveit_config/          # MoveIt2 config
├── so_arm_100_isaac_sim/              # Isaac Sim integration
├── so101_description/                 # SO-101 URDF + meshes
├── so101_bringup/                     # SO-101 launch files
├── so101_moveit_config/               # SO-101 MoveIt2
├── so101_teleop/                      # Teleoperation
├── so101_kinematics/                  # Forward/inverse kinematics
├── so101_inference/                   # Policy inference node
├── so101_camera_calibration/          # Camera calibration
├── episode_recorder/                  # Episode recording for training
├── policy_server/                     # gRPC/ZMQ policy inference server
├── scripts/                           # Docker build/run helpers
├── tests/                             # Integration tests (bats)
└── workspaces/                        # ROS2 workspace configs
```

---

## Quick Start

### 1. Web Dashboard (runs anywhere)

```bash
cd webapp
npm install
npm run dev
# → http://localhost:3000
```

### 2. AI Pipeline (needs camera)

```bash
pip install -r requirements.txt
python ai/main.py
# Keys: 1=sorting  2=patrol  d=debug  q=quit
```

### 3. Interaction Server

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your-key
pip install -r requirements.txt
python -m uvicorn interaction.web.endpoints:app --port 8000
```

### 4. Medicine Orchestrator

```bash
cd minh
python -m medicine_orchestrator --mode full --camera 0
```

### 5. Full ROS2 Stack (Docker)

```bash
docker compose up
# Web UI:       http://localhost:8080
# WS Bridge:    ws://localhost:9090
# Next.js App:  http://localhost:3000 (run separately)
```

---

## Features

| Feature | Module | Status |
|---------|--------|--------|
| Medicine identification (OCR) | ai/, minh/ | ✅ Working |
| Expiration date parsing | ai/, minh/ | ✅ Working |
| Pill detection (YOLO11) | minh/vision | ✅ Working |
| Pick & place (GR00T N1.7) | minh/policy | 🔧 Fine-tuning |
| Fall detection + patrol | ai/patrol | ✅ Working |
| Voice emergency detection | ai/speech | ✅ Working |
| LLM interaction (agent/ask) | interaction/ | ✅ Working |
| Semantic spatial memory | interaction/memory | ✅ Working |
| Speech-to-text (Whisper) | interaction/speech | ✅ Working |
| 3D robot control (web) | webapp/ | ✅ Working |
| Gazebo simulation | so_arm_100_description | ✅ Working |
| Sim ↔ hardware bridge | so_arm_100_web_bridge | ✅ Working |
| Schedule / calendar | webapp/ | ✅ UI ready |
| Medication inventory | webapp/ | ✅ UI ready |
| Emergency notifications | webapp/reports | 🔧 In progress |
| GPS / nearest hospital | webapp/reports | 🔧 In progress |
| Speaker integration | — | 📋 Planned |

---

## Key Design Decisions

1. **Simulation = Real robot**: Moving sliders on the web dashboard sends joint commands through the WebSocket bridge to both Gazebo simulation AND the physical SO-101 arm simultaneously. The Simulator tab shows physics diagnostics.

2. **Modular AI**: The `ai/` module runs standalone (just needs a camera). The `interaction/` module is robot-agnostic (works with any platform providing camera + pose). The `minh/` orchestrator ties everything together for the medicine workflow.

3. **LLM-powered interaction**: Users can talk to the robot in natural language. The agent mode can call robot tools (pick up, sort, patrol) via MCP protocol. Ask mode is read-only (check inventory, query memory).

4. **Offline-first OCR**: Medicine identification uses PaddleOCR + fuzzy matching against a local database — no cloud dependency for the critical path.

5. **Spatial memory adapted for stationary arm**: The semantic memory (CLIP + ChromaDB) was originally from DimOS (Unitree Go2 quadruped). We adapted it for the SO-101 by:
   - Using **end-effector pose** (from FK) instead of robot base odometry
   - Reducing distance threshold from 0.5m (room-scale) to 0.03m (workspace-scale)
   - Spatial queries answer "what was at slot A?" instead of "what's near the kitchen?"
   - Tagged locations = sorting slots, not rooms

---

## Team

Built for the EuroTech x Hong Kong Hackathon in Munich, June 2026.
