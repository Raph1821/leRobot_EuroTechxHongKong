# Minh's Workspace — Medicine Robot (Merged)

## Overview

Merged codebase combining:
- **Teammate's work** (`leRobot_EuroTechxHongKong`): PaddleOCR + fuzzy name matching + expiration parsing + scan state machine
- **Your work**: YOLO pill detection/counting + GR00T pick-and-place + dose interpretation + robot control

Target: **Elderly home care robot** — SO-101 arm (leRobot platform), EuroTech x Hong Kong hackathon.

## Architecture (Merged)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CAMERA FEED                                   │
│                    (wrist + room cameras)                             │
└──────────────┬──────────────────────────────────┬───────────────────┘
               │                                  │
    ┌──────────▼──────────┐            ┌──────────▼──────────┐
    │  PaddleOCR (bg proc) │            │  YOLO11 Detection   │
    │  (teammate's code)   │            │  (your code)        │
    └──────────┬───────────┘            └──────────┬──────────┘
               │                                   │
    ┌──────────▼───────────┐            ┌──────────▼──────────┐
    │ Medicine Name Parser  │            │ Pill Classifier     │
    │ (fuzzy, 300+ DB)     │            │ (bbox + class)      │
    │ + Expiration Parser   │            │ + Pill Counter      │
    │ (regex, multilingual) │            │ (count + verify)    │
    └──────────┬───────────┘            └──────────┬──────────┘
               │                                   │
    ┌──────────▼───────────┐                       │
    │  Scan State Machine   │                       │
    │  (accumulate results) │                       │
    └──────────┬───────────┘                       │
               │                                   │
               └──────────────┬────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  ORCHESTRATOR       │
                   │  (decision logic)   │
                   │  - Which slot?      │
                   │  - How many pills?  │
                   │  - Expired?         │
                   └──────────┬──────────┘
                              │
                   ┌──────────▼──────────┐
                   │  GR00T N1.7 Policy  │
                   │  (pick & place)     │
                   └──────────┬──────────┘
                              │
                   ┌──────────▼──────────┐
                   │  SO-101 Robot Arm   │
                   │  (via DDS/leRobot)  │
                   └─────────────────────┘
```

## Folder Structure

```
Minh/
├── README.md                         # This file
├── requirements.txt                  # Merged dependencies
├── medicine_robot_config.yaml        # All configuration
├── medicine_orchestrator.py          # MAIN ENTRY POINT — ties everything together
│
├── sorting/                          # From teammate's code
│   ├── medicine_name_parser.py       # Fuzzy matching against 300+ medicine database
│   ├── expiration_date_parser.py     # Robust regex for exp dates (EU/US/German)
│   ├── scan_state.py                 # State machine: SCANNING → WAITING_FOR_REMOVAL
│   └── data/
│       └── medicine_names.json       # 300+ medicine name database
│
├── vision/                           # Your code
│   ├── pill_classifier.py            # YOLO11 detection + sorting slot routing
│   ├── pill_counter.py               # Count pills + verify dispensed amount
│   └── dose_reader.py                # MERGED: OCR + teammate's parsers + optional LLM
│
├── policy/                           # From SO-ARM Starter (adapted)
│   ├── run_medicine_policy.py        # GR00T inference with medicine task descriptions
│   └── gr00tn1_7/runners.py          # GR00T N1.7 model wrapper
│
├── dds/                              # DDS communication layer
│   ├── publisher.py / subscriber.py
│   └── schemas/
│
└── holoscan_apps/                    # Real hardware deployment
    ├── gr00t_inference_app.py
    └── operators/
```

## Quick Start

```bash
# Install merged dependencies
pip install -r requirements.txt

# Run in SCAN mode (teammate's OCR pipeline — identify medicines)
python -m medicine_orchestrator --mode scan --camera 0

# Run in SORT mode (your YOLO detection + robot commands)
python -m medicine_orchestrator --mode sort --camera 0

# Run in DOSE mode (read label + count pills)
python -m medicine_orchestrator --mode dose --image label.jpg

# Run FULL pipeline (scan → sort → count → verify)
python -m medicine_orchestrator --mode full --camera 0

# Test with static image
python -m medicine_orchestrator --mode full --image test_medicine.jpg
```

## Keyboard Controls (Live Camera Mode)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reset current scan |
| `s` | Trigger sorting on current frame |
| `d` | Trigger dose reading on current frame |
| `f` | Trigger full pipeline |
| `p` | Print current state and all scanned medicines |

## How the Merge Works

### Medicine Identification (teammate's code, fast & offline)
- PaddleOCR extracts text in a background process (non-blocking)
- `medicine_name_parser.py` fuzzy-matches against 300+ names (rapidfuzz, 88% threshold)
- `expiration_date_parser.py` regex-extracts dates (handles EXP, MHD, Haltbar bis, etc.)
- `scan_state.py` accumulates partial results across frames until both name + exp are confirmed

### Pill Detection & Sorting (your code)
- YOLO11 detects pill locations in the frame (bounding boxes)
- Classifier assigns each pill to a sorting slot (A/B/C/D/E)
- Pill counter verifies correct dispensing count

### Dose Interpretation (merged)
- `dose_reader.py` now uses teammate's parsers for name + expiration (fast, offline)
- Optionally uses LLM (Phi-3) for dosage frequency/timing interpretation (set `use_llm: true`)
- Falls back to regex for dosage parsing if LLM unavailable

### Robot Execution (your code)
- GR00T N1.7 policy takes task description + camera images → joint actions
- DDS/Holoscan pipeline sends actions to SO-101 arm

## What Each Person Should Focus On Next

### You (Minh) — Pick & Place + Integration
- Fine-tune YOLO11 on your actual medicine set (see pill_classifier.py `train_pill_model()`)
- Calibrate sorting slot positions in `medicine_robot_config.yaml`
- Test GR00T policy with different task descriptions
- Wire the orchestrator's sorting commands into the GR00T policy loop

### Teammate — OCR + Scanning
- Expand `medicine_names.json` with medicines used in the demo
- Tune OCR crop ratio and confidence thresholds for demo lighting
- Handle edge cases in expiration parsing for demo medicines
