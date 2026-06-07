"""Camera diagnostic — identify every camera and confirm it streams.

This is the FIRST thing to run before launching the app, especially after
plugging/unplugging cameras (Windows reassigns indexes each time).

It will:
  1. List physical camera devices by NAME (Windows)
  2. Probe OpenCV indexes 0-7 and report which actually deliver real frames
  3. Detect the Intel RealSense separately (it needs pyrealsense2)
  4. Print a ready-to-use launch command

Run:
    python ai/check_cameras.py
"""
import platform
import subprocess
import sys
import time

import numpy as np
import cv2


def list_device_names():
    """List physical camera names on Windows via PowerShell."""
    if platform.system() != "Windows":
        return []
    try:
        out = subprocess.check_output(
            ["powershell", "-Command",
             "Get-CimInstance Win32_PnPEntity | "
             "Where-Object { $_.PNPClass -eq 'Camera' -or $_.Service -eq 'usbvideo' } | "
             "Select-Object -ExpandProperty Name"],
            text=True, stderr=subprocess.DEVNULL, timeout=15,
        )
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:
        return []


def open_index(i):
    """Open an index with the platform-appropriate backend."""
    system = platform.system()
    if system == "Darwin":
        return cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
    if system == "Windows":
        return cv2.VideoCapture(i, cv2.CAP_DSHOW)
    return cv2.VideoCapture(i)


def probe_index(i):
    """Return 'streaming' / 'black' / 'unavailable' for an OpenCV index."""
    cap = open_index(i)
    if not cap.isOpened():
        cap.release()
        return "unavailable", None
    # Warm up: cheap USB cams send black frames for ~1s
    status, res = "black", None
    t0 = time.time()
    while time.time() - t0 < 2.0:
        ret, frame = cap.read()
        if ret and frame is not None:
            res = f"{frame.shape[1]}x{frame.shape[0]}"
            if frame.mean() > 2:
                status = "streaming"
                break
        time.sleep(0.05)
    cap.release()
    return status, res


def check_realsense():
    """Check for an Intel RealSense via pyrealsense2."""
    try:
        import pyrealsense2 as rs
    except ImportError:
        return None  # SDK not installed
    ctx = rs.context()
    devs = ctx.query_devices()
    if len(devs) == 0:
        return "none"
    return [d.get_info(rs.camera_info.name) for d in devs]


def main():
    print("=" * 60)
    print("CAMERA DIAGNOSTIC")
    print("=" * 60)

    names = list_device_names()
    if names:
        print("\nPhysical cameras detected (by name):")
        for n in names:
            print(f"  - {n}")

    print("\nProbing OpenCV indexes 0-7...")
    streaming = []
    for i in range(8):
        status, res = probe_index(i)
        if status == "streaming":
            print(f"  [{i}] STREAMING  {res}")
            streaming.append(i)
        elif status == "black":
            print(f"  [{i}] opens but BLACK ({res}) — ghost/duplicate or needs replug")
        # skip 'unavailable' for brevity

    print("\nIntel RealSense:")
    rs_status = check_realsense()
    if rs_status is None:
        print("  pyrealsense2 not installed (pip install pyrealsense2)")
    elif rs_status == "none":
        print("  No RealSense detected — check USB 3.0 cable/port")
    else:
        for n in rs_status:
            print(f"  - {n}  (use --realsense flag, NOT an OpenCV index)")

    print("\n" + "=" * 60)
    print("NEXT STEP — identify each streaming index visually:")
    for i in streaming:
        print(f"    python ai/preview_camera.py {i}")
    print("\nThen launch with YOUR identified indexes, e.g.:")
    rs_flag = " --realsense" if (rs_status and rs_status not in ("none", None)) else ""
    print(f"    python ai/main.py --ocr-camera <logitech> --patrol-camera <wrist>{rs_flag}")
    print("=" * 60)


if __name__ == "__main__":
    main()
