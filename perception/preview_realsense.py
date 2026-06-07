"""Preview the Intel RealSense color stream via pyrealsense2.

The RealSense exposes depth/IR/color streams that plain OpenCV VideoCapture
can't pick correctly. This uses the RealSense SDK to grab the COLOR stream.

Run:  python ai/preview_realsense.py
Press 'q' to close.
"""
import sys

try:
    import pyrealsense2 as rs
except ImportError:
    print("pyrealsense2 not installed. Run: pip install pyrealsense2")
    sys.exit(1)

import numpy as np
import cv2

# List connected RealSense devices
ctx = rs.context()
devices = ctx.query_devices()
if len(devices) == 0:
    print("No RealSense device detected. Check USB 3.0 connection and cable.")
    sys.exit(1)

for d in devices:
    print(f"Found: {d.get_info(rs.camera_info.name)} "
          f"(serial {d.get_info(rs.camera_info.serial_number)})")

# Configure the color stream
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

print("Starting color stream... press 'q' to quit")
pipeline.start(config)

try:
    while True:
        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        if not color_frame:
            continue
        img = np.asanyarray(color_frame.get_data())
        cv2.putText(img, "RealSense COLOR", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.imshow("RealSense color preview", img)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    pipeline.stop()
    cv2.destroyAllWindows()
