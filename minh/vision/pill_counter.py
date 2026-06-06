"""
Pill Counting Module

Uses YOLO detection to count individual pills in a frame.
Can be combined with the dose_reader to verify correct pill quantities.

Usage:
    python -m vision.pill_counter --image pills_on_tray.jpg
    python -m vision.pill_counter --camera 0  # live counting

Integration:
    counter = PillCounter()
    count = counter.count_pills(frame)
    
    # Combined with dose info:
    dose_info = dose_reader.read_medicine(label_image)
    required_count = parse_dosage_count(dose_info.dosage)  # e.g., "2 tablets" -> 2
    actual_count = counter.count_pills(tray_image)
    if actual_count == required_count:
        # Proceed with dispensing
"""

import argparse
from dataclasses import dataclass

import numpy as np


@dataclass
class CountResult:
    """Result of pill counting."""
    total_count: int
    detections: list          # list of (bbox, confidence) tuples
    frame_annotated: object   # annotated image (optional)


class PillCounter:
    """
    Count pills using YOLO object detection.
    
    Strategy:
    - Each individual pill = one detection
    - Use instance segmentation or detection to count
    - Filter by confidence threshold
    """

    def __init__(self, model_path: str = "yolo11n.pt", confidence_threshold: float = 0.4):
        """
        Args:
            model_path: Path to YOLO model (fine-tuned on pills preferred)
            confidence_threshold: Minimum confidence for counting
        """
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f"[PillCounter] Model loaded: {self.model_path}")
        except ImportError:
            print("[PillCounter] WARNING: ultralytics not installed.")
            print("  Install with: pip install ultralytics")
        except Exception as e:
            print(f"[PillCounter] ERROR: {e}")

    def count_pills(self, frame: np.ndarray, annotate: bool = False) -> CountResult:
        """
        Count pills in a frame.
        
        Args:
            frame: BGR/RGB image as numpy array
            annotate: If True, draw detections on a copy of the frame
            
        Returns:
            CountResult with total count and detection details
        """
        if self.model is None:
            return CountResult(total_count=0, detections=[], frame_annotated=None)

        results = self.model(frame, verbose=False)
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                bbox = box.xyxy[0].tolist()
                detections.append((bbox, conf))

        annotated = None
        if annotate:
            annotated = frame.copy()
            for bbox, conf in detections:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                import cv2
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f"{conf:.2f}", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            # Draw total count
            cv2.putText(annotated, f"Count: {len(detections)}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

        return CountResult(
            total_count=len(detections),
            detections=detections,
            frame_annotated=annotated,
        )

    def verify_dose(self, frame: np.ndarray, expected_count: int) -> dict:
        """
        Verify that the correct number of pills has been dispensed.
        
        Args:
            frame: Image of the dispensing tray
            expected_count: How many pills should be there
            
        Returns:
            Dict with verification result
        """
        result = self.count_pills(frame)
        is_correct = result.total_count == expected_count

        return {
            "expected": expected_count,
            "actual": result.total_count,
            "is_correct": is_correct,
            "status": "OK" if is_correct else (
                "TOO_FEW" if result.total_count < expected_count else "TOO_MANY"
            ),
            "message": (
                f"Correct: {result.total_count} pills dispensed."
                if is_correct else
                f"WARNING: Expected {expected_count}, found {result.total_count}."
            ),
        }


def parse_dosage_count(dosage_text: str) -> int:
    """
    Parse a dosage string to get the number of pills.
    
    Examples:
        "1 tablet" -> 1
        "2 capsules" -> 2
        "500mg (1 tablet)" -> 1
        "Take 2" -> 2
    """
    import re

    # Look for explicit count
    patterns = [
        r"(\d+)\s*(?:tablet|capsule|pill|cap|tab)",
        r"take\s*(\d+)",
        r"(\d+)\s*(?:times|x)",
    ]

    for pattern in patterns:
        match = re.search(pattern, dosage_text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Default: 1 pill if not specified
    return 1


def main():
    parser = argparse.ArgumentParser(description="Pill Counter")
    parser.add_argument("--image", type=str, help="Path to image")
    parser.add_argument("--camera", type=int, help="Camera index")
    parser.add_argument("--model", type=str, default="yolo11n.pt")
    parser.add_argument("--expected", type=int, default=None, help="Expected pill count for verification")
    args = parser.parse_args()

    counter = PillCounter(model_path=args.model)

    if args.image:
        import cv2
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Could not read: {args.image}")
            return

        result = counter.count_pills(frame, annotate=True)
        print(f"\nPill Count: {result.total_count}")

        if args.expected is not None:
            verification = counter.verify_dose(frame, args.expected)
            print(f"Verification: {verification['message']}")

        if result.frame_annotated is not None:
            cv2.imshow("Pill Count", result.frame_annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    elif args.camera is not None:
        import cv2
        cap = cv2.VideoCapture(args.camera)
        print("Press 'q' to quit, 'v' to verify count")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            result = counter.count_pills(frame, annotate=True)
            if result.frame_annotated is not None:
                cv2.imshow("Pill Counter", result.frame_annotated)
            key = cv2.waitKey(1)
            if key == ord("q"):
                break
            elif key == ord("v") and args.expected:
                verification = counter.verify_dose(frame, args.expected)
                print(verification["message"])
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
