# perception/

Sensor processing and scene understanding.

## What belongs here

- Object detection (pills, bottles, labels)
- Fall detection (`fall_detector.py`)
- Person detection
- OCR pipelines
- Camera utilities (`check_cameras.py`, `list_cameras.py`, `preview_*.py`)
- RealSense depth-camera scripts

## Modules

| File | Purpose |
|---|---|
| `fall_detector.py` | Pose-landmark-based fall / lying detection |
| `pill_detect_yolo.py` | YOLO-based pill detection |
| `realsense_pills.py` | Pill detection using RealSense depth data |
| `check_cameras.py` | Verify camera availability |
| `list_cameras.py` | Enumerate connected cameras |
| `preview_camera.py` | Live camera preview |
| `preview_realsense.py` | Live RealSense preview |
