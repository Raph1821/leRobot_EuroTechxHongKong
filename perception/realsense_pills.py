"""RealSense D405 → YOLO pill detection (Track B).

Streams the RealSense color feed and runs YOLO detection on each frame,
drawing bounding boxes. This is the overhead camera for the sorting /
dosage task.

Run:
    python ai/realsense_pills.py
    python ai/realsense_pills.py --model path/to/best.pt   # fine-tuned model

Press 'q' to quit, 's' to print sorting commands for current detections.

NOTE: the default yolo11n.pt is the GENERIC base model — it detects everyday
objects, not specific medicines. For real pill classification, fine-tune on
the medical-pills dataset (see minh/vision/pill_classifier.py train_pill_model).
"""
import argparse
import sys

import numpy as np
import cv2

try:
    import pyrealsense2 as rs
except ImportError:
    print("pyrealsense2 not installed. Run: pip install pyrealsense2")
    sys.exit(1)

# Import the existing classifier from the minh module
sys.path.insert(0, "minh")
from vision.pill_classifier import PillClassifier


def main():
    parser = argparse.ArgumentParser(description="RealSense + YOLO pill detection")
    parser.add_argument("--model", type=str, default="yolo11n.pt",
                        help="YOLO model path (default: yolo11n.pt base model)")
    parser.add_argument("--conf", type=float, default=0.4,
                        help="Confidence threshold")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    classifier = PillClassifier(model_path=args.model, confidence_threshold=args.conf)
    if classifier.model is None:
        print("YOLO model failed to load. Install ultralytics: pip install ultralytics")
        return

    # Confirm RealSense present
    ctx = rs.context()
    if len(ctx.query_devices()) == 0:
        print("No RealSense detected. Check USB 3.0 connection.")
        return
    dev = ctx.query_devices()[0]
    print(f"Using: {dev.get_info(rs.camera_info.name)}")

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, args.width, args.height, rs.format.bgr8, 30)
    pipeline.start(config)
    print("Streaming RealSense → YOLO. Press 'q' to quit, 's' for sorting commands.")

    try:
        while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue
            frame = np.asanyarray(color_frame.get_data())

            detections = classifier.detect(frame)
            for det in detections:
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{det.class_name} {det.confidence:.2f}"
                cv2.putText(frame, label, (x1, max(y1 - 8, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.putText(frame, f"Detections: {len(detections)}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            cv2.imshow("RealSense Pill Detection", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                commands = classifier.get_sorting_commands(detections)
                print(f"\n{len(commands)} sorting command(s):")
                for cmd in commands:
                    print(f"  -> {cmd['task_description']}")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
