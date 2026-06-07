# Elda

AI-powered elderly care robot built on the SO-101 arm. Scans and sorts medications, detects falls, speaks to the patient, and gives caregivers a live web dashboard.

**EuroTech × Hong Kong Hackathon · Munich · June 2026**

---

<!-- PUT YOUR BEST GIF HERE — robot scanning a medicine bottle or the dashboard live -->
<!-- <img src="assets/demo.gif" width="800"/> -->

---

## What it does

- Reads medicine labels with OCR and parses expiration dates
- Falls into PATROL mode and detects falls via pose estimation
- Counts pills with a RealSense depth camera (DOSAGE mode)
- Listens for voice commands and "help" / "I fell" emergency phrases
- Talks back via TTS using Claude or deterministic responses
- Fires medication reminders on a schedule
- Scores patient wellbeing from a 14-day rolling signal baseline
- Generates a daily summary and morning briefing
- Stores everything to a persistent JSON memory file
- Serves a Next.js dashboard with live camera, chat, schedules, and a Munich emergency hospital map

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  webapp/  (Next.js 16 · React · Three.js · Tailwind)                │
│                                                                     │
│  /          overview dashboard        /schedule   medication cal    │
│  /control   3D SO-101 viewer + arm    /medications inventory        │
│  /camera    live MJPEG feed           /reports    alerts + stats    │
│  /interaction  LLM chat              /emergency  Munich hospital map│
│  /patients  patient profiles         /messages   caregiver inbox    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP (careApi.ts → localhost:8000)
┌────────────────────────────▼────────────────────────────────────────┐
│  server/api_server.py  (FastAPI)                                    │
│                                                                     │
│  GET  /medicines          GET  /schedule         GET  /events       │
│  GET  /camera/stream      GET  /camera/snapshot  GET  /doses/history│
│  POST /schedule           DELETE /schedule/:id   POST /assistant/ask│
│  GET  /doses/dispensed/last7days                                    │
└──────────────┬──────────────────────────────────────────────────────┘
               │ reads shared_frame + care_memory
┌──────────────▼──────────────────────────────────────────────────────┐
│  scripts/main.py  —  the Elda main loop                             │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  SORTING mode    │  │  PATROL mode     │  │  DOSAGE mode     │  │
│  │                  │  │                  │  │                  │  │
│  │  OCR webcam      │  │  wrist camera    │  │  RealSense D4xx  │  │
│  │  PaddleOCR       │  │  MediaPipe pose  │  │  YOLO11 pills    │  │
│  │  medicine parser │  │  emergency SM    │  │  pill count      │  │
│  │  expiry parser   │  │  fall detection  │  │  dose verify     │  │
│  │  scan state SM   │  │                  │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  faster-whisper STT ──▶ intents.py ──▶ assistant_actions.py        │
│                                    └──▶ (UNKNOWN only) llm_client  │
│                                                    └──▶ Claude API  │
│                                                                     │
│  CareMemory (data/care_memory.json)                                 │
│    medicines · schedules · dose history · events · emergencies      │
│    wellbeing reports · morning briefings · patient profile          │
│                                                                     │
│  background threads:                                                │
│    ReminderChecker — polls schedules every 30 s, fires TTS alerts  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ros2_ws/src/so101-ros-physical-ai/                                 │
│                                                                     │
│  so101_bringup        launch files (follower, leader, cameras,      │
│                        recording session)                           │
│  so101_description    URDF + STL meshes (also served to webapp)     │
│  so101_moveit_config  MoveIt2 motion planning config                │
│  so101_kinematics     FK/IK nodes, trajectory executor,             │
│                        GoToJoints / GoToPose services               │
│  so101_teleop         C++ teleoperation node (leader → follower)    │
│  so101_inference      policy inference node (gRPC/ZMQ transport)    │
│  so101_patrol         ROS2 patrol node                              │
│  so101_pick_place     pick & place ROS2 node                        │
│  so101_camera_calib   handeye + intrinsic calibration               │
│  episode_recorder     C++ episode recorder → LeRobot HDF5 dataset   │
│  feetech_ros2_driver  low-level Feetech STS3215 servo driver        │
│  policy_server        gRPC/ZMQ inference server (runs LeRobot ACT) │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  interaction/  (semantic workspace memory + LLM agent)              │
│                                                                     │
│  memory/   CLIP embeddings + ChromaDB — "where did I see Aspirin?"  │
│  llm/      streaming LLM agent, MCP tool calling                    │
│  speech/   Whisper or AWS Transcribe transcriber                    │
│  web/      FastAPI: /query/stream  /command/stream  /transcribe     │
└─────────────────────────────────────────────────────────────────────┘

  coord_server/server.c  — C HTTP server; camera sends detections,
                           robot polls /command → "hold" when person seen
```

---

## Repo layout

```
├── scripts/main.py              Elda main loop (entry point)
├── server/api_server.py         FastAPI server for the webapp
├── perception/                  Camera utilities, fall detector, YOLO, RealSense
├── behavior/
│   ├── patrol/                  Patrol mode + emergency state machine
│   ├── reminders/               Background dose reminder thread
│   ├── exploration/             CLIP-based exploration memory
│   ├── health/                  Health check (keyword → LLM escalation)
│   ├── summary/                 Daily summary + morning briefing
│   └── wellbeing/               Signal extraction + 0–100 risk score + 14-day baseline
├── assistant/
│   ├── llm_client.py            Claude API wrapper with CareContext injection
│   ├── intents.py               Keyword intent classifier
│   ├── assistant_actions.py     Deterministic handlers; fallback to LLM
│   ├── speech/                  Whisper STT listener, TTS engine, emergency phrases
│   └── memory/                  care_memory.py (JSON store) + memory_recall.py
├── manipulation/
│   ├── sorting/                 Medicine name parser, expiry parser, scan state machine
│   └── dosage_counter.py        Pill count verification
├── core/                        Shared frame buffer, app mode enum, event log
├── interaction/                 CLIP spatial memory + streaming LLM agent (adapted from DimOS)
├── coord_server/server.c        C coordination server (person detect → hold command)
├── webapp/                      Next.js 16 dashboard
├── ros2_ws/                     ROS2 workspace (SO-101 packages)
└── data/
    ├── medicine_names.json       300+ medicine name database
    └── pose_landmarker_lite.task MediaPipe pose model
```

---

## How to run

### 1. Web dashboard (no robot or camera needed)

```bash
cd webapp
npm install
npm run dev
# → http://localhost:3000
```

Set `NEXT_PUBLIC_CAREAI_URL` in `webapp/.env.local` to point at the API server:

```
NEXT_PUBLIC_CAREAI_URL=http://localhost:8000
# or over ngrok / LAN:
# NEXT_PUBLIC_CAREAI_URL=https://xxxx.ngrok.app
```

### 2. AI pipeline

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # or put it in .env at repo root
```

```bash
# Single webcam (OCR + patrol share one camera)
python scripts/main.py

# Two cameras: OCR webcam on index 1, wrist camera on index 2
python scripts/main.py --ocr-camera 1 --patrol-camera 2

# Add RealSense for pill counting (press 3 to activate DOSAGE mode)
python scripts/main.py --ocr-camera 1 --patrol-camera 2 --realsense

# Verify pill count against prescription
python scripts/main.py --realsense --expected-pills 3
```

Keys while running:

| Key | Action |
|-----|--------|
| `1` | SORTING mode (medicine scan + OCR) |
| `2` | PATROL mode (fall detection) |
| `3` | DOSAGE mode (pill count via RealSense) |
| `a` | Talk to Elda |
| `H` | Health check conversation |
| `B` | Morning briefing |
| `Y` | Daily summary |
| `R` | Check reminders now |
| `m` | Memory stats |
| `q` | Quit |

### 3. FastAPI server (connects webapp to AI pipeline)

```bash
uvicorn server.api_server:app --reload --port 8000
```

Run this alongside `scripts/main.py` so the webapp gets live camera, medicines, and chat.

### 4. Camera utilities

```bash
python perception/list_cameras.py        # find camera indices
python perception/check_cameras.py       # assert cameras are accessible
python perception/preview_camera.py --index 1
python perception/preview_realsense.py
```

### 5. ROS2 stack

```bash
cd ros2_ws
colcon build
source install/setup.bash

# Bring up the follower arm
ros2 launch so101_bringup follower.launch.py

# Teleop (leader → follower)
ros2 launch so101_bringup teleop.launch.py

# MoveIt2 demo
ros2 launch so101_bringup follower_moveit_demo.launch.py

# Record an episode for training
ros2 launch so101_bringup follower_recording.launch.py

# Run policy inference
ros2 launch so101_inference async_infer.launch.py
```

---

## Team

EuroTech × Hong Kong Hackathon · Munich · June 2026
