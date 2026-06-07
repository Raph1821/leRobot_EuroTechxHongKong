# Perception

> The sensory layer of Elda — everything the robot sees and interprets from the physical world before any decision is made.

---

## Overview

`perception/` is the exclusive owner of all hardware-facing vision code. Camera streams, pixel buffers, depth frames, and ML inference calls are handled here and nowhere else. The rest of the system — `behavior/`, `manipulation/`, `assistant/` — receives clean, structured results from this layer and remains independent of any specific camera or model.

This boundary means new sensors can be integrated, models can be swapped, and hardware can be mocked for testing without touching a single line of behavioral or conversational code.

---

## Components

### Fall Detection

**`fall_detector.py`**

Detects whether a person has fallen or is lying down using MediaPipe pose landmarks. Receives a raw camera frame and returns a boolean classification. It lives in `perception/` because it is a pure visual classification task — the decision to respond to a fall is made upstream in `behavior/patrol/`.

### Medicine & Pill Detection

**`pill_detect_yolo.py`**

Runs a YOLO object detection model over an RGB frame to locate pill regions. Returns bounding boxes and confidence scores for downstream use by the manipulation pipeline.

**`realsense_pills.py`**

Extends YOLO detection with Intel RealSense depth data to produce 3D position estimates for each detected pill. Used when the robot needs physical precision for pick-and-place tasks.

### Camera Utilities

| Script | Purpose |
|---|---|
| `list_cameras.py` | Enumerate all connected cameras and their OpenCV indices |
| `check_cameras.py` | Assert that expected cameras are accessible before starting the robot |
| `preview_camera.py` | Open a live preview window from any indexed camera |
| `preview_realsense.py` | Live RGB and depth preview from the RealSense sensor |

---

## Usage

All scripts run from the **repository root**:

```bash
# Enumerate connected cameras
python perception/list_cameras.py

# Verify camera availability before launch
python perception/check_cameras.py

# Live preview — adjust --index to the camera you want to inspect
python perception/preview_camera.py --index 0

# RealSense depth + RGB preview
python perception/preview_realsense.py
```

---

## Architecture Boundaries

```
Hardware (camera / RealSense)
        │
        ▼
  perception/              ← raw frames IN, structured data OUT
        │
        ├── fall_detector.py      →  bool: person fallen
        ├── pill_detect_yolo.py   →  list[BoundingBox]
        └── realsense_pills.py    →  list[Position3D]
        │
        ▼
manipulation/ · behavior/ · server/
```

**Rule:** Nothing outside `perception/` imports `cv2` frame data or calls inference models directly. If a new sensor or model is needed elsewhere, expose a function here and call that.

---

## Extending This Module

New detectors — barcode scanners, face recognition, skeleton tracking — belong here. Each detector should be:

- **Stateless** — takes a frame, returns a result, holds no internal state between calls
- **Single-purpose** — one classification concern per file
- **Decoupled** — no imports from `behavior/`, `assistant/`, or `manipulation/`
