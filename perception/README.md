# perception/

Elda's sensory layer — everything the robot sees and interprets from the physical world before any decision is made.

## Purpose

Perception is the boundary between raw hardware input and structured data that the rest of the system can act on. Nothing outside this module should touch camera streams, pixel buffers, or depth frames directly. By keeping all sensor-facing code here, the rest of Elda's stack (behavior, assistant, manipulation) can be tested and evolved without depending on specific hardware.

## Contents

### Fall & person detection

`fall_detector.py` uses MediaPipe pose landmarks to determine whether a person is lying down or has fallen. It is called from the patrol loop but lives here because it is fundamentally a visual classification task with no behavioral logic of its own.

### Pill & medicine detection

`pill_detect_yolo.py` runs a YOLO model over RGB frames to locate pill regions.  
`realsense_pills.py` pairs the RGB detection with Intel RealSense depth data to estimate 3D pill positions — used when physical pick-and-place precision matters.

### Camera utilities

| Script | When to use |
|---|---|
| `check_cameras.py` | Verify that the expected cameras are accessible before starting the robot |
| `list_cameras.py` | Enumerate all connected cameras with their OpenCV indices |
| `preview_camera.py` | Open a live window from any indexed camera — useful for alignment and focus checks |
| `preview_realsense.py` | Live RGB + depth preview from the RealSense — use to confirm depth calibration |

## How to run the utilities

All scripts are self-contained and run from the repo root:

```bash
python perception/list_cameras.py
python perception/check_cameras.py
python perception/preview_camera.py --index 0
python perception/preview_realsense.py
```

## Adding new sensors

New detectors (skeleton tracking, face recognition, barcode scanning) belong here. Keep each detector stateless and focused on a single classification concern. Pass structured results up to `behavior/` or `manipulation/` — do not embed decision logic inside perception code.
