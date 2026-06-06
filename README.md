# Carebot SO-101 — AI Medicine Management Robot

**EuroTech x Hong Kong Hackathon · Munich, June 2026 · AI & Robotics Track**

---

## What the Robot Does (Summary)

The SO-101 is a **stationary robotic care arm** that helps elderly patients manage their medications autonomously. It sits on a table and performs these tasks:

| # | Task | How |
|---|------|-----|
| 1 | **Identify medicines** | Wrist camera + PaddleOCR → fuzzy match against 300+ medicine database |
| 2 | **Check expiration dates** | Regex parser (EU/US/German formats) → alert if expired |
| 3 | **Sort medicines** | YOLO11 pill detection → GR00T N1.7 pick & place → slots A–E |
| 4 | **Verify dosage** | Pill counter confirms correct number dispensed |
| 5 | **Patrol workspace** | Rotate wrist camera, detect falls/anomalies via frame differencing |
| 6 | **Emergency alerts** | Voice "help" detection → notify hospital + relatives + send photo |
| 7 | **Voice/text interaction** | Whisper STT + LLM agent (Claude/OpenAI) → understands natural language |
| 8 | **Reminders & schedule** | Timed medication alerts, morning briefings, daily reports |
| 9 | **Health check** | Detects health concern keywords in conversation → escalates |
| 10 | **Memory** | Remembers scanned medicines, events, emergencies (persistent JSON + CLIP spatial) |

---

## Global Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WEBSITE (webapp/)                                │
│                                                                         │
│  ┌────────────┐ ┌───────────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │  Overview   │ │ Simulation &      │ │  Camera    │ │  Interaction │  │
│  │  Dashboard  │ │ Manual Control    │ │  Live Feed │ │  Chat (LLM)  │  │
│  └────────────┘ └───────────────────┘ └────────────┘ └──────────────┘  │
│  ┌────────────┐ ┌───────────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │  Schedule / │ │  Medications      │ │  Reports & │ │  Emergency   │  │
│  │  Calendar   │ │  Inventory        │ │  Alerts    │ │  Map (112)   │  │
│  └────────────┘ └───────────────────┘ └────────────┘ └──────────────┘  │
│                                                                         │
│  Next.js 16 · React · Three.js (3D SO-101 viewer) · TailwindCSS        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ WebSocket ws://localhost:9090
┌──────────────────────────────────▼──────────────────────────────────────┐
│                     ROS2 WebSocket Bridge                                │
│           so_arm_100_web_bridge (joint cmds, camera, teleop)            │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ ROS2 Topics & Actions
        ┌──────────────┬───────────┼───────────┬──────────────┐
        │  Gazebo Sim  │  SO-101   │  MoveIt2  │  Isaac Sim   │
        │  (Harmonic)  │  Hardware │ (planning)│  (optional)  │
        └──────────────┴───────────┴───────────┴──────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        AI PIPELINE (ai/)                                 │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ CORE LOOP (main.py)                                                │ │
│  │  Camera → OCR → Medicine Name + Expiration → Scan State Machine    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐   │
│  │ patrol/      │  │ speech/      │  │ sorting/                    │   │
│  │ • fall detect│  │ • STT listen │  │ • medicine_name_parser      │   │
│  │ • frame diff │  │ • emergency  │  │ • expiration_date_parser    │   │
│  │ • anomaly    │  │   phrases    │  │ • scan_state (state machine)│   │
│  └──────────────┘  └──────────────┘  └─────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐   │
│  │ assistant/   │  │ health/      │  │ memory/                     │   │
│  │ • intents    │  │ • health     │  │ • care_memory (JSON persist)│   │
│  │ • actions    │  │   check      │  │ • memory_recall             │   │
│  │ • LLM client │  │ • keywords   │  │                             │   │
│  │ • prompts    │  │              │  │                             │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐                                    │
│  │ reminders/   │  │ summary/     │                                    │
│  │ • scheduler  │  │ • daily      │                                    │
│  │ • timed dose │  │ • morning    │                                    │
│  │   alerts     │  │   briefing   │                                    │
│  └──────────────┘  └──────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    INTERACTION MODULE (interaction/)                      │
│                                                                         │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────────┐   │
│  │ llm/         │  │ memory/          │  │ speech/                 │   │
│  │ • agent.py   │  │ • spatial_memory │  │ • transcriber.py        │   │
│  │   (MCP loop) │  │   (CLIP+ChromaDB)│  │   (Whisper / AWS)       │   │
│  │ • provider.py│  │ • embedding.py   │  │                         │   │
│  │   (Anthropic/│  │ • visual_memory  │  │                         │   │
│  │    Bedrock/  │  │ • vector_db      │  │                         │   │
│  │    OpenAI)   │  │                  │  │                         │   │
│  └──────────────┘  └──────────────────┘  └─────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ web/endpoints.py — FastAPI: /query/stream, /command/stream,      │   │
│  │                              /transcribe                          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (minh/)                                   │
│                                                                         │
│  medicine_orchestrator.py — Full pipeline: scan → sort → dose → verify  │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐   │
│  │ vision/      │  │ policy/      │  │ dds/                        │   │
│  │ • YOLO11 pill│  │ • GR00T N1.7 │  │ • publisher/subscriber      │   │
│  │   detection  │  │   pick&place │  │ • IDL schemas (soarm, cam)  │   │
│  │ • pill count │  │ • runners    │  │                             │   │
│  │ • dose reader│  │              │  │                             │   │
│  └──────────────┘  └──────────────┘  └─────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐                                    │
│  │ training/    │  │ holoscan/    │                                    │
│  │ • hdf5→lrbt │  │ • real-time  │                                    │
│  │ • GR00T fine │  │   inference  │                                    │
│  │   tune       │  │   operators  │                                    │
│  └──────────────┘  └──────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    ROS2 PACKAGES (so101_* / so_arm_100_*)                │
│                                                                         │
│  so101_description ─── URDF + meshes                                    │
│  so101_bringup ─────── Launch files (sim + hardware)                    │
│  so101_moveit_config ── MoveIt2 motion planning                         │
│  so101_kinematics ───── Forward/inverse kinematics service              │
│  so101_teleop ───────── Teleoperation node                              │
│  so101_inference ────── Policy inference (GR00T via ROS)                 │
│  so101_camera_calib ─── Camera calibration                              │
│  episode_recorder ───── Record episodes for training                    │
│  policy_server ──────── gRPC/ZMQ policy inference server                │
│  so_arm_100_web_bridge ─ WebSocket ↔ ROS2 bridge                        │
│  so_arm_100_description ─ Gazebo xacro                                  │
│  so_arm_100_isaac_sim ── Isaac Sim integration                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Website Pages (webapp/)

| Page | URL | What it does |
|------|-----|--------------|
| **Overview** | `/` | Dashboard with status cards, robot mini-viewer |
| **Simulation & Control** | `/control` | 3D SO-101 viewer + joint sliders (Manual Control tab) + Gazebo diagnostics (Simulator tab). Moving sliders moves the real robot. |
| **Camera** | `/camera` | Live camera feeds (front, gripper, top, room) |
| **Interaction** | `/interaction` | Text/voice chat with LLM agent (Ask mode = read-only, Agent mode = can move arm) |
| **Schedule** | `/schedule` | Weekly prescription calendar (when to take what) |
| **Medications** | `/medications` | Inventory: stock levels, expiration tracking, add/remove |
| **Reports & Alerts** | `/reports` | Stats (doses on time, pick&place ops), alerts (low stock, expiring), emergency routing |
| **Emergency** | `/emergency` | Munich hospital map (Overpass API), nearest hospital, call 112, trigger emergency flow |
| **Settings** | `/settings` | Robot config (safe mode, collision guard), notification preferences (Gmail, relatives) |

---

## Task Checklist

### ✅ Done
- [x] Medicine identification (PaddleOCR + fuzzy match)
- [x] Expiration date parsing (regex, multilingual)
- [x] Scan state machine (accumulate partial results)
- [x] Fall detection + patrol mode
- [x] Voice emergency detection ("help", "I fell")
- [x] Speech-to-text (Whisper local)
- [x] LLM interaction (Claude / OpenAI / Ollama)
- [x] Semantic spatial memory (CLIP + ChromaDB, adapted for arm)
- [x] Web dashboard with 3D SO-101 viewer
- [x] Manual control → real robot via WebSocket bridge
- [x] Gazebo simulation support
- [x] Medication inventory UI
- [x] Schedule/calendar UI
- [x] Emergency map (Munich hospitals, Overpass API)
- [x] Reports & alerts UI
- [x] Health check (keyword detection + LLM response)
- [x] Care memory (persistent JSON: medicines, events, emergencies)
- [x] Reminder system (timed dose alerts)
- [x] Daily summary / morning briefing
- [x] Assistant intent classification + actions
- [x] YOLO11 pill detection pipeline
- [x] GR00T N1.7 pick & place policy
- [x] DDS communication layer

### 🔧 In Progress
- [ ] Expiration date → save to server → medicine management system
- [ ] Emergency → call ambulance (nearest hospital + relatives via email)
- [ ] GPS/location sharing for emergency routing
- [ ] Reminder & schedule → doctor prescription input portal
- [ ] Speaker integration (TTS output)
- [ ] Fine-tune YOLO on actual medicine set
- [ ] Calibrate sorting slot positions on physical setup

### 📋 Planned
- [ ] Gmail notification integration
- [ ] Statistical report generation (PDF/email)
- [ ] Multi-camera stream selector on web
- [ ] Real-time WebSocket connection status on web

---

## Quick Start

### Web Dashboard (no robot needed)
```bash
cd webapp
npm install
npx next dev
# → http://localhost:3000
```

### AI Pipeline (needs webcam)
```bash
pip install -r requirements.txt
python ai/main.py
```

### Full ROS2 Stack (Docker)
```bash
docker compose up
# Web bridge: ws://localhost:9090
# Web UI: http://localhost:8080
```

---

## Folder Map

```
leRobot_EuroTechxHongKong/
├── ai/                    # Vision + speech + assistant + memory + reminders
├── interaction/           # LLM agent + spatial memory + STT + FastAPI
├── minh/                  # Orchestrator + YOLO + GR00T + DDS + training
├── webapp/                # Next.js web dashboard (runs standalone)
├── so101_*/               # ROS2 packages for SO-101 arm
├── so_arm_100_*/          # ROS2 packages (Gazebo, bridge, Isaac)
├── policy_server/         # gRPC/ZMQ inference server
├── episode_recorder/      # Training data recording
├── web_interface/         # Legacy Vite UI (ROS2 bridge test client)
├── Dockerfile             # Full stack container
├── docker-compose.yaml    # Orchestrated services
└── requirements.txt       # Python dependencies
```

---

## Team

Built for the EuroTech x Hong Kong Hackathon, Munich, June 2026.
