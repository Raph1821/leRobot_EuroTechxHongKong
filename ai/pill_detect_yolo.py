"""Pill detection + dose counting with a trained YOLOv8 model (Track B).

Uses a pre-trained pills model (seblful/pills-detection, classes: tablets,
capsules) on the Intel RealSense D405 overhead stream. Detects and counts
individual pills for dose verification.

Model: ai/data/pills_yolov8.onnx  (YOLOv8, ~91% mAP on tablets/capsules)

Run:
    python ai/pill_detect_yolo.py                  # count live (RealSense)
    python ai/pill_detect_yolo.py --expected 2     # verify against prescription
    python ai/pill_detect_yolo.py --webcam 2       # use a normal webcam
    python ai/pill_detect_yolo.py --conf 0.3       # lower threshold (detect more)

Keys (in the window):
    +/-  raise/lower confidence threshold
    v    print verification result
    q    quit
"""
import argparse
import os
import sys

import numpy as np
import cv2

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "data", "pills_yolov8.onnx")
_BATCH = 8  # this ONNX was exported with a fixed batch size of 8


def load_model(model_path=_MODEL_PATH):
    from ultralytics import YOLO
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        print("Download: curl -L -o ai/data/pills_yolov8.onnx "
              "https://github.com/seblful/pills-detection/raw/main/best_model.onnx")
        sys.exit(1)
    return YOLO(model_path, task="detect")


def detect_pills(model, frame, conf=0.4):
    """Return list of (class_name, confidence, (x1,y1,x2,y2)).

    This ONNX was exported with a fixed batch size of 8, so we replicate the
    frame into a batch of 8 and use the first result.
    """
    batch = [frame] * _BATCH
    results = model(batch, conf=conf, verbose=False)
    dets = []
    r = results[0]  # first image of the batch
    if r.boxes is not None:
        for b in r.boxes:
            cls = int(b.cls[0])
            name = r.names.get(cls, str(cls))
            c = float(b.conf[0])
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            dets.append((name, c, (x1, y1, x2, y2)))
    return dets


def draw(frame, dets):
    out = frame.copy()
    colors = {"tablets": (0, 255, 0), "capsules": (255, 160, 0)}
    counts = {"tablets": 0, "capsules": 0}
    for name, conf, (x1, y1, x2, y2) in dets:
        counts[name] = counts.get(name, 0) + 1
        col = colors.get(name, (0, 255, 255))
        cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), col, 2)
        cv2.putText(out, f"{name} {conf:.2f}", (int(x1), int(max(y1 - 6, 12))),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
    return out, counts


def realsense_frames(width=640, height=480):
    import pyrealsense2 as rs
    ctx = rs.context()
    if len(ctx.query_devices()) == 0:
        print("No RealSense detected.")
        return
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, 30)
    pipeline.start(config)
    try:
        while True:
            frames = pipeline.wait_for_frames()
            cf = frames.get_color_frame()
            if not cf:
                continue
            yield np.asanyarray(cf.get_data())
    finally:
        pipeline.stop()


def webcam_frames(index):
    import platform
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"Could not open webcam {index}")
        return
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            yield frame
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description="YOLO pill detection + dose counting")
    parser.add_argument("--expected", type=int, default=None,
                        help="Prescribed pill count to verify against")
    parser.add_argument("--webcam", type=int, default=None,
                        help="Use a normal webcam index instead of the RealSense")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    args = parser.parse_args()

    model = load_model()
    conf = args.conf

    source = webcam_frames(args.webcam) if args.webcam is not None else realsense_frames()
    src = f"webcam {args.webcam}" if args.webcam is not None else "RealSense"
    print(f"Pill detection from {src}. Keys: +/- conf, v verify, q quit")

    for frame in source:
        dets = detect_pills(model, frame, conf=conf)
        out, counts = draw(frame, dets)
        total = len(dets)

        cv2.putText(out, f"TOTAL PILLS: {total}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 2)
        cv2.putText(out, f"tablets: {counts.get('tablets', 0)}  "
                         f"capsules: {counts.get('capsules', 0)}", (10, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
        if args.expected is not None:
            ok = total == args.expected
            cv2.putText(out, f"Expected {args.expected} -> {'OK' if ok else 'MISMATCH'}",
                        (10, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 200, 0) if ok else (0, 0, 255), 2)
        cv2.putText(out, f"conf={conf:.2f}", (10, out.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("Pill Detection (YOLOv8)", out)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key in (ord("+"), ord("=")):
            conf = min(0.95, conf + 0.05)
        elif key in (ord("-"), ord("_")):
            conf = max(0.05, conf - 0.05)
        elif key == ord("v"):
            if args.expected is not None:
                ok = total == args.expected
                print(f"Verify: expected {args.expected}, counted {total} -> "
                      f"{'CORRECT' if ok else 'MISMATCH'}")
            else:
                print(f"Counted {total} pills "
                      f"(tablets={counts.get('tablets',0)}, capsules={counts.get('capsules',0)})")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
