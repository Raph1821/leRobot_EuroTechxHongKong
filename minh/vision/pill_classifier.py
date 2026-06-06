"""
Pill Detection & Classification Module

Uses Ultralytics YOLO11 for real-time pill/medicine detection and classification.
This module provides the classification/routing logic for the sorting task.

Resources:
- Ultralytics Medical Pills Dataset: https://docs.ultralytics.com/datasets/detect/medical-pills/
- Pre-trained model: ultralytics/yolo11n (fine-tune on medical-pills dataset)

Usage:
    python -m vision.pill_classifier --image test_image.jpg
    python -m vision.pill_classifier --camera 0  # live camera feed

Integration with SO-ARM pick-and-place:
    classifier = PillClassifier(model_path="best.pt")
    detections = classifier.detect(frame)
    for det in detections:
        target_slot = classifier.get_target_slot(det["class_name"])
        # -> send pick-and-place command to robot with target_slot
"""

import argparse
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class PillDetection:
    """A single detected pill."""
    class_name: str       # e.g., "aspirin", "ibuprofen", "vitamin_c"
    confidence: float     # 0.0 - 1.0
    bbox: tuple           # (x1, y1, x2, y2) pixel coordinates
    center: tuple         # (cx, cy) center point for robot targeting


class PillClassifier:
    """
    YOLO-based pill detection and classification.
    
    Workflow:
    1. Detect pills in camera frame
    2. Classify each pill type
    3. Return sorted list with target placement locations
    """

    # Define sorting slots — map medicine type to physical tray position
    SORTING_MAP = {
        "morning_meds": {"slot": "A", "position": [0.15, 0.10, 0.05]},   # x, y, z in robot frame
        "afternoon_meds": {"slot": "B", "position": [0.15, 0.00, 0.05]},
        "evening_meds": {"slot": "C", "position": [0.15, -0.10, 0.05]},
        "as_needed": {"slot": "D", "position": [0.25, 0.00, 0.05]},
        "unknown": {"slot": "E", "position": [0.25, -0.10, 0.05]},
    }

    def __init__(self, model_path: str = "yolo11n.pt", confidence_threshold: float = 0.5):
        """
        Initialize the pill classifier.
        
        Args:
            model_path: Path to YOLO model weights. 
                        Use "yolo11n.pt" for base model, or your fine-tuned "best.pt".
            confidence_threshold: Minimum confidence to count a detection.
        """
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f"[PillClassifier] Loaded model: {self.model_path}")
        except ImportError:
            print("[PillClassifier] WARNING: ultralytics not installed.")
            print("  Install with: pip install ultralytics")
            self.model = None
        except Exception as e:
            print(f"[PillClassifier] ERROR loading model: {e}")
            self.model = None

    def detect(self, frame: np.ndarray) -> list[PillDetection]:
        """
        Detect and classify pills in a camera frame.
        
        Args:
            frame: BGR or RGB image as numpy array, shape (H, W, 3)
            
        Returns:
            List of PillDetection objects sorted by confidence (highest first)
        """
        if self.model is None:
            return []

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

                cls_id = int(box.cls[0])
                class_name = result.names.get(cls_id, "unknown")
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

                detections.append(PillDetection(
                    class_name=class_name,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    center=(cx, cy),
                ))

        # Sort by confidence
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def get_target_slot(self, class_name: str) -> dict:
        """
        Get the target sorting slot for a given pill class.
        
        Args:
            class_name: The detected pill class name
            
        Returns:
            Dict with 'slot' label and 'position' in robot frame
        """
        # TODO: Customize this mapping based on your medicine categories
        # For hackathon, you might map based on color, shape, or label
        return self.SORTING_MAP.get(class_name, self.SORTING_MAP["unknown"])

    def get_sorting_commands(self, detections: list[PillDetection]) -> list[dict]:
        """
        Convert detections to robot sorting commands.
        
        Returns list of commands like:
        [
            {"pick_position": (cx, cy), "place_slot": "A", "place_position": [...], "task": "..."},
            ...
        ]
        """
        commands = []
        for det in detections:
            target = self.get_target_slot(det.class_name)
            task_description = (
                f"Pick up the {det.class_name} at position "
                f"({det.center[0]:.0f}, {det.center[1]:.0f}) "
                f"and place it in slot {target['slot']}"
            )
            commands.append({
                "pick_position": det.center,
                "place_slot": target["slot"],
                "place_position": target["position"],
                "class_name": det.class_name,
                "confidence": det.confidence,
                "task_description": task_description,
            })
        return commands


def train_pill_model(data_yaml: str = "medical-pills.yaml", epochs: int = 100):
    """
    Fine-tune YOLO11 on the medical pills dataset.
    
    Run this once to get a trained model for your specific medicines.
    
    Usage:
        python -c "from vision.pill_classifier import train_pill_model; train_pill_model()"
    """
    from ultralytics import YOLO

    # Start from pre-trained YOLO11 nano (fast, good for edge)
    model = YOLO("yolo11n.pt")

    # Train on medical pills dataset
    # Download dataset: https://docs.ultralytics.com/datasets/detect/medical-pills/
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=640,
        batch=16,
        name="pill_classifier",
    )
    print(f"Training complete. Best model at: {results.save_dir}/weights/best.pt")
    return results


def main():
    parser = argparse.ArgumentParser(description="Pill Detection & Classification")
    parser.add_argument("--image", type=str, help="Path to test image")
    parser.add_argument("--camera", type=int, help="Camera index for live feed")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Model path")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--data", type=str, default="medical-pills.yaml", help="Dataset YAML for training")
    args = parser.parse_args()

    if args.train:
        train_pill_model(args.data)
        return

    classifier = PillClassifier(model_path=args.model)

    if args.image:
        import cv2
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Could not read image: {args.image}")
            return
        detections = classifier.detect(frame)
        print(f"\nDetected {len(detections)} pill(s):")
        for det in detections:
            print(f"  - {det.class_name} (conf={det.confidence:.2f}) at {det.center}")
        commands = classifier.get_sorting_commands(detections)
        print(f"\nSorting commands:")
        for cmd in commands:
            print(f"  -> {cmd['task_description']}")

    elif args.camera is not None:
        import cv2
        cap = cv2.VideoCapture(args.camera)
        print("Press 'q' to quit, 's' to show sorting commands")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            detections = classifier.detect(frame)
            # Draw detections
            for det in detections:
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{det.class_name} {det.confidence:.2f}"
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imshow("Pill Classifier", frame)
            key = cv2.waitKey(1)
            if key == ord("q"):
                break
            elif key == ord("s"):
                commands = classifier.get_sorting_commands(detections)
                for cmd in commands:
                    print(f"  -> {cmd['task_description']}")
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
