# Camera Testing Guide (Track A + B)

> **Golden rule:** Windows reassigns camera indexes every time you plug/unplug
> a USB camera. **Always re-run the diagnostic after any replug.**

## Our 3 cameras

| Device name (Windows) | Role | Mode | How it's accessed |
|----------------------|------|------|-------------------|
| **Logitech StreamCam** | clear webcam | SORTING (medicine OCR) | OpenCV index |
| **HBV HD CAMERA** | wrist cam | PATROL (fall detection) | OpenCV index (rotated 270°) |
| **Intel RealSense D405** | overhead | DOSAGE (pill counting) | `--realsense` flag (pyrealsense2) |

---

## Step 1 — Always start with the diagnostic

```
python ai/check_cameras.py
```

This shows:
- Physical cameras by **name**
- Which OpenCV indexes actually **stream** (vs. black/ghost indexes)
- Whether the RealSense is detected
- A ready-to-use launch command

## Step 2 — Identify which index is which

For each STREAMING index the diagnostic reported, preview it:

```
python ai/preview_camera.py 0
python ai/preview_camera.py 1
python ai/preview_camera.py 2
```

Look at the window:
- **Sharp, wide view** → Logitech (use as `--ocr-camera`)
- **Lower quality, gripper view** → HBV wrist cam (use as `--patrol-camera`)
- **Laptop's own view** → Integrated webcam (ignore)

## Step 3 — Test the RealSense separately

```
python ai/preview_realsense.py
```

Should print "Intel RealSense D405" and show a color window.

## Step 4 — Launch with your identified indexes

```
python ai/main.py --ocr-camera 2 --patrol-camera 1 --realsense
```

Switch modes with keys: `1`=sorting, `2`=patrol, `3`=dosage, `q`=quit.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Camera went dark after replug | Index shifted | Re-run `python ai/check_cameras.py` |
| Index "opens but BLACK" | Ghost/duplicate index OR needs replug | Use a different index, or unplug-replug the camera |
| Wrist cam upside down / sideways | Mismounted | Already auto-rotated 270°; override with `--patrol-rotate 0/90/180` |
| RealSense not detected | USB 2.0 port or bad cable | Use a blue USB 3.0 port + the original cable |
| Two USB cams won't run together | USB bandwidth limit | Use a powered USB 3.0 hub, or different USB controllers/ports |
| `pyrealsense2 not installed` | SDK missing | `pip install pyrealsense2` |

---

## Quick reference — standalone test scripts

| Script | Purpose |
|--------|---------|
| `python ai/check_cameras.py` | **Run first** — full diagnostic |
| `python ai/preview_camera.py <i>` | Preview one OpenCV camera |
| `python ai/preview_realsense.py` | Preview the RealSense color stream |
| `python ai/pill_detect_yolo.py` | Test pill detection/counting (RealSense) |
| `python ai/pill_detect_yolo.py --expected 2` | Test dose verification |
| `python ai/main.py --ocr-camera 2 --patrol-camera 1 --realsense` | Full 3-camera app |
