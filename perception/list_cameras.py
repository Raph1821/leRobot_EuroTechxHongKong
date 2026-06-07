"""Quick camera scanner — lists which camera indexes are available.

Run:  python ai/list_cameras.py
Then point each one to see which is the wrist cam vs the clear webcam.
"""
import cv2
import platform

system = platform.system()

def _open(i):
    if system == "Darwin":
        return cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
    elif system == "Windows":
        return cv2.VideoCapture(i, cv2.CAP_DSHOW)
    return cv2.VideoCapture(i)

print("Scanning camera indexes 0-5...\n")
found = []
for i in range(6):
    cap = _open(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"  [{i}] AVAILABLE  ({w}x{h})")
            found.append(i)
        cap.release()
    else:
        print(f"  [{i}] not available")

print(f"\nFound {len(found)} camera(s): {found}")
print("\nTip: open each index to identify which is the wrist cam and which is the clear webcam:")
print("  python -c \"import cv2; c=cv2.VideoCapture(0);\")")
print("\nThen run:")
print("  python ai/main.py --ocr-camera <clear_webcam> --patrol-camera <wrist_cam>")
