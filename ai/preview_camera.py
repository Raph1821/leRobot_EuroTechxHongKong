"""Preview a single camera so you can identify it (wrist / webcam / laptop).

Run:  python ai/preview_camera.py 0
      python ai/preview_camera.py 1
      ... try each index

A window opens showing the live feed with the index number on it.
Press 'q' (with the window focused) to close and try the next index.

Some USB cameras return black/empty frames for the first second — this tool
warms up by grabbing several frames before showing the window.
"""
import sys
import time
import cv2
import platform

if len(sys.argv) < 2:
    print("Usage: python ai/preview_camera.py <index>")
    sys.exit(1)

index = int(sys.argv[1])
system = platform.system()
if system == "Darwin":
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
elif system == "Windows":
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
else:
    cap = cv2.VideoCapture(index)

if not cap.isOpened():
    print(f"Camera {index} could not be opened.")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Camera {index}: {w}x{h}  — warming up...")

# Warm-up: grab frames for up to 2 seconds until we get a non-empty one
got_frame = False
t0 = time.time()
while time.time() - t0 < 2.0:
    ret, frame = cap.read()
    if ret and frame is not None and frame.mean() > 1:  # not pure black
        got_frame = True
        break
    time.sleep(0.05)

if not got_frame:
    print(f"Camera {index}: opened but returns black/empty frames (likely a ghost/duplicate index).")
    cap.release()
    sys.exit(0)

print(f"Camera {index}: streaming — press 'q' to close")
while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.putText(frame, f"CAMERA {index}  ({w}x{h})", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    cv2.imshow(f"Camera {index} preview", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
