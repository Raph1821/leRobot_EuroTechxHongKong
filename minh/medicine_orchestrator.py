"""
Medicine Robot Orchestrator (MERGED VERSION)

Integrates:
- Teammate's code: PaddleOCR + fuzzy medicine name matching + expiration parsing + scan state machine
- Your code: YOLO pill detection/counting + GR00T pick-and-place policy + robot control

Full pipeline:
1. Camera captures frame
2. Teammate's OCR pipeline identifies WHAT medicine (name + expiration)
3. Your YOLO detects WHERE pills are in the frame
4. Your dose reader extracts HOW MANY pills to dispense
5. Your GR00T policy executes pick-and-place to correct slot
6. Your pill counter verifies the dispensed amount

Modes:
- scan:  Use teammate's state machine to scan medicines (identify + expiration check)
- sort:  Detect + classify + pick & place to correct slot
- dose:  Read label + count pills + verify correct dispensing
- full:  Complete pipeline (scan → sort → count → verify)

Usage:
    python -m medicine_orchestrator --mode scan --camera 0
    python -m medicine_orchestrator --mode sort --camera 0
    python -m medicine_orchestrator --mode full --image test.jpg
"""

import argparse
import logging
import multiprocessing as mp
import time
from enum import Enum
from typing import Optional

import cv2
import numpy as np
import yaml

from sorting.scan_state import MedicineScanState
from sorting.medicine_name_parser import find_medicine_name
from sorting.expiration_date_parser import parse_expiration_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OCR settings (from teammate's code)
CROP_RATIO = 0.5
MAX_CROP_WIDTH = 640
OCR_MIN_INTERVAL = 1.5


class RobotMode(Enum):
    SCAN = "scan"           # Teammate's: identify medicine + expiration
    SORT = "sort"           # Yours: detect + classify + pick & place
    DOSE = "dose"           # Yours: read label + count + verify
    FULL = "full"           # Combined: scan → sort → count → verify


def _center_crop(frame: np.ndarray) -> np.ndarray:
    """Center crop for OCR focus (from teammate's code)."""
    h, w = frame.shape[:2]
    ch, cw = int(h * CROP_RATIO), int(w * CROP_RATIO)
    y, x = (h - ch) // 2, (w - cw) // 2
    crop = frame[y:y + ch, x:x + cw]
    if cw > MAX_CROP_WIDTH:
        scale = MAX_CROP_WIDTH / cw
        crop = cv2.resize(crop, (MAX_CROP_WIDTH, int(ch * scale)))
    return crop


def _put_latest(q: mp.Queue, item) -> None:
    """Replace queue contents with item so only the latest is kept."""
    try:
        q.get_nowait()
    except Exception:
        pass
    try:
        q.put_nowait(item)
    except Exception:
        pass


def _ocr_worker(crop_queue: mp.Queue, result_queue: mp.Queue) -> None:
    """Background OCR process (from teammate's code)."""
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_textline_orientation=True, lang="en")
    last_text = None

    while True:
        try:
            crop = crop_queue.get(timeout=2.0)
        except Exception:
            continue

        t0 = time.monotonic()
        result = ocr.predict(crop)
        lines = []
        if result and result[0]:
            for item in result[0].get("rec_texts", []):
                if item:
                    lines.append(item)
        text = "\n".join(lines).strip()

        if not text or text != last_text:
            last_text = text
            _put_latest(result_queue, text)

        elapsed = time.monotonic() - t0
        remaining = OCR_MIN_INTERVAL - elapsed
        if remaining > 0:
            time.sleep(remaining)


class MedicineOrchestrator:
    """
    Merged orchestrator combining both codebases.
    """

    def __init__(self, config_path: str, mode: RobotMode = RobotMode.FULL):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.mode = mode

        # Teammate's components
        self.scan_state = MedicineScanState()

        # Your components (lazy init — only load what's needed)
        self._classifier = None
        self._counter = None
        self._dose_reader = None

    @property
    def classifier(self):
        """Lazy-load YOLO pill classifier."""
        if self._classifier is None:
            from vision.pill_classifier import PillClassifier
            pill_cfg = self.config.get("vision", {}).get("pill_detection", {})
            self._classifier = PillClassifier(
                model_path=pill_cfg.get("model_path", "yolo11n.pt"),
                confidence_threshold=pill_cfg.get("confidence_threshold", 0.5),
            )
        return self._classifier

    @property
    def counter(self):
        """Lazy-load pill counter."""
        if self._counter is None:
            from vision.pill_counter import PillCounter
            pill_cfg = self.config.get("vision", {}).get("pill_detection", {})
            self._counter = PillCounter(
                model_path=pill_cfg.get("model_path", "yolo11n.pt"),
                confidence_threshold=pill_cfg.get("confidence_threshold", 0.4),
            )
        return self._counter

    @property
    def dose_reader(self):
        """Lazy-load dose reader."""
        if self._dose_reader is None:
            from vision.dose_reader import DoseReader
            dose_cfg = self.config.get("vision", {}).get("dose_reading", {})
            self._dose_reader = DoseReader(
                use_llm=dose_cfg.get("use_llm", False),
                llm_backend=dose_cfg.get("llm_backend", "transformers"),
            )
        return self._dose_reader

    # ─────────────────────────────────────────────────────────────────────
    # SCAN MODE (teammate's state machine)
    # ─────────────────────────────────────────────────────────────────────

    def process_ocr_result(self, ocr_text: str) -> Optional[dict]:
        """
        Process OCR text through teammate's state machine.
        Returns completed scan result when both name + expiration are found.
        """
        med_name = find_medicine_name(ocr_text)
        exp_date = parse_expiration_date(ocr_text)

        scan_complete = self.scan_state.update(med_name, exp_date, ocr_text)

        if scan_complete:
            result = self.scan_state.completed_results[-1]
            logger.info(f"SCAN COMPLETE: {result['medicine_name']} (exp: {result['expiration_date']})")
            return result

        if self.scan_state.removal_detected:
            logger.info("Medicine removed. Ready for next scan.")

        return None

    # ─────────────────────────────────────────────────────────────────────
    # SORT MODE (your YOLO detection + routing)
    # ─────────────────────────────────────────────────────────────────────

    def run_sorting(self, frame: np.ndarray, medicine_name: Optional[str] = None) -> list[dict]:
        """
        Sorting mode: detect pills and generate sorting commands.
        If medicine_name is provided (from scan), uses it for smarter slot assignment.
        """
        detections = self.classifier.detect(frame)
        if not detections:
            logger.info("[Sort] No pills detected.")
            return []

        commands = self.classifier.get_sorting_commands(detections)

        # If we know the medicine name from scanning, update task descriptions
        if medicine_name:
            for cmd in commands:
                cmd["medicine_name"] = medicine_name
                cmd["task_description"] = (
                    f"Pick up the {medicine_name} and place it in slot {cmd['place_slot']}"
                )

        logger.info(f"[Sort] {len(detections)} pill(s) → {len(commands)} commands.")
        for cmd in commands:
            logger.info(f"  → {cmd['task_description']}")
        return commands

    # ─────────────────────────────────────────────────────────────────────
    # DOSE MODE (your dose reader + pill counter)
    # ─────────────────────────────────────────────────────────────────────

    def run_dose_reading(self, label_frame: np.ndarray) -> dict:
        """
        Read medicine label and extract structured dose info.
        Uses teammate's parsers for name/expiration + optional LLM for dosage.
        """
        dose_info = self.dose_reader.read_medicine(label_frame)
        logger.info(f"[Dose] {dose_info.medicine_name}: {dose_info.dosage}, {dose_info.frequency}")
        logger.info(f"[Dose] Expiration: {dose_info.expiration_date}")
        return {
            "medicine": dose_info.medicine_name,
            "dosage": dose_info.dosage,
            "frequency": dose_info.frequency,
            "timing": dose_info.timing,
            "expiration": dose_info.expiration_date,
            "warnings": dose_info.warnings,
            "confidence": dose_info.confidence,
        }

    def verify_pill_count(self, tray_frame: np.ndarray, expected_count: int) -> dict:
        """Verify correct number of pills dispensed."""
        result = self.counter.verify_dose(tray_frame, expected_count)
        logger.info(f"[Verify] {result['message']}")
        return result

    # ─────────────────────────────────────────────────────────────────────
    # FULL MODE (combined pipeline)
    # ─────────────────────────────────────────────────────────────────────

    def run_full_pipeline(self, label_frame: np.ndarray, tray_frame: np.ndarray) -> dict:
        """
        Full merged pipeline:
        1. OCR → medicine name (teammate's fuzzy match) + expiration (teammate's regex)
        2. Dosage interpretation (regex or LLM)
        3. YOLO detection → find pills in frame
        4. Sorting commands → robot pick-and-place
        5. Pill count verification
        """
        from vision.pill_counter import parse_dosage_count

        # Step 1: Identify medicine (teammate's parsers via dose_reader)
        logger.info("\n[Step 1] Identifying medicine...")
        dose_info = self.dose_reader.read_medicine(label_frame)
        logger.info(f"  → Name: {dose_info.medicine_name}")
        logger.info(f"  → Expiration: {dose_info.expiration_date}")
        logger.info(f"  → Dosage: {dose_info.dosage}, Frequency: {dose_info.frequency}")

        # Step 2: Determine pill count needed
        required_count = parse_dosage_count(dose_info.dosage)
        logger.info(f"\n[Step 2] Required pill count: {required_count}")

        # Step 3: Detect pills for sorting
        logger.info("\n[Step 3] Detecting pills...")
        detections = self.classifier.detect(tray_frame)
        commands = self.classifier.get_sorting_commands(detections[:required_count])

        # Enhance commands with medicine name
        for cmd in commands:
            cmd["medicine_name"] = dose_info.medicine_name
            cmd["task_description"] = (
                f"Pick up {dose_info.medicine_name} and place it in slot {cmd['place_slot']}"
            )

        # Step 4: Verification
        logger.info(f"\n[Step 4] Verifying ({required_count} expected)...")
        verification = self.counter.verify_dose(tray_frame, required_count)

        # Step 5: Expiration check
        expiration_warning = None
        if dose_info.expiration_date != "Unknown":
            expiration_warning = self._check_expiration(dose_info.expiration_date)

        return {
            "medicine_info": {
                "name": dose_info.medicine_name,
                "dosage": dose_info.dosage,
                "frequency": dose_info.frequency,
                "timing": dose_info.timing,
                "expiration": dose_info.expiration_date,
                "warnings": dose_info.warnings,
            },
            "required_count": required_count,
            "sorting_commands": commands,
            "verification": verification,
            "expiration_warning": expiration_warning,
        }

    def _check_expiration(self, exp_date_str: str) -> Optional[str]:
        """Check if medicine is expired or expiring soon."""
        import re
        from datetime import datetime

        match = re.match(r"(\d{2})/(\d{4})", exp_date_str)
        if not match:
            return None

        month, year = int(match.group(1)), int(match.group(2))
        exp_date = datetime(year, month, 1)
        now = datetime.now()

        if exp_date < now:
            return f"⚠️ EXPIRED: {exp_date_str} — DO NOT DISPENSE"
        elif (exp_date - now).days < 90:
            return f"⚠️ EXPIRING SOON: {exp_date_str} (less than 3 months)"
        return None

    # ─────────────────────────────────────────────────────────────────────
    # LIVE CAMERA LOOP (integrates teammate's multiprocessing OCR)
    # ─────────────────────────────────────────────────────────────────────

    def run_live(self, camera_index: int = 0):
        """
        Run live camera loop with OCR in background process.
        Integrates teammate's multiprocessing architecture.
        """
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error("Could not open camera.")
            return

        logger.info(f"Camera opened (index={camera_index}). Mode: {self.mode.value}")
        logger.info("Controls: 'q'=quit, 'r'=reset scan, 's'=sort, 'd'=dose read, 'p'=print state")

        # Start background OCR process (teammate's architecture)
        crop_queue: mp.Queue = mp.Queue(maxsize=1)
        result_queue: mp.Queue = mp.Queue(maxsize=1)
        ocr_proc = mp.Process(target=_ocr_worker, args=(crop_queue, result_queue), daemon=True)
        ocr_proc.start()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Send cropped frame to OCR worker
            _put_latest(crop_queue, _center_crop(frame))

            # Check for OCR results
            try:
                ocr_text = result_queue.get_nowait()
                self._handle_ocr_result(ocr_text, frame)
            except Exception:
                pass

            # Display
            display = self._annotate_frame(frame)
            cv2.imshow("Medicine Robot - Live", display)

            # Handle keyboard
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                self.scan_state.reset_current()
                logger.info("Scan reset.")
            elif key == ord("s"):
                # Trigger sorting on current frame
                commands = self.run_sorting(frame, self.scan_state.current_medicine_name)
                for cmd in commands:
                    print(f"  → {cmd['task_description']}")
            elif key == ord("d"):
                # Trigger dose reading on current frame
                info = self.run_dose_reading(frame)
                print(f"  → {info}")
            elif key == ord("f"):
                # Trigger full pipeline
                result = self.run_full_pipeline(frame, frame)
                print(f"  → Full result: {result}")
            elif key == ord("p"):
                self._print_state()

        ocr_proc.terminate()
        cap.release()
        cv2.destroyAllWindows()

    def _handle_ocr_result(self, ocr_text: str, frame: np.ndarray):
        """Handle incoming OCR result based on current mode."""
        if self.mode in (RobotMode.SCAN, RobotMode.FULL):
            result = self.process_ocr_result(ocr_text)
            if result:
                print("\n" + "=" * 50)
                print("MEDICINE IDENTIFIED")
                print(f"  Name:       {result['medicine_name']}")
                print(f"  Expiration: {result['expiration_date']}")
                print("=" * 50)

                # In FULL mode, automatically trigger sorting
                if self.mode == RobotMode.FULL:
                    commands = self.run_sorting(frame, result["medicine_name"])
                    if commands:
                        print(f"  Sorting: {len(commands)} command(s) generated")

    def _annotate_frame(self, frame: np.ndarray) -> np.ndarray:
        """Add status overlay to the displayed frame."""
        display = frame.copy()
        h, w = display.shape[:2]

        # Status bar
        cv2.rectangle(display, (0, 0), (w, 40), (0, 0, 0), -1)
        mode_text = f"Mode: {self.mode.value.upper()}"
        phase_text = f"| Phase: {self.scan_state.phase}"
        name_text = f"| Med: {self.scan_state.current_medicine_name or '...'}"

        cv2.putText(display, f"{mode_text} {phase_text} {name_text}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        # Show completed scans count
        count_text = f"Scanned: {len(self.scan_state.completed_results)}"
        cv2.putText(display, count_text, (w - 150, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

        return display

    def _print_state(self):
        """Print current state to console."""
        print(f"\n--- State: {self.scan_state.phase}")
        print(f"  Current name: {self.scan_state.current_medicine_name}")
        print(f"  Current exp:  {self.scan_state.current_expiration_date}")
        if self.scan_state.completed_results:
            print("  Scanned medicines:")
            for i, r in enumerate(self.scan_state.completed_results, 1):
                print(f"    {i}. {r['medicine_name']} | exp: {r['expiration_date']}")
        else:
            print("  No medicines scanned yet.")
        print("---")


def main():
    parser = argparse.ArgumentParser(description="Medicine Robot Orchestrator (Merged)")
    parser.add_argument("--config", type=str, default="medicine_robot_config.yaml")
    parser.add_argument("--mode", type=str, default="full",
                        choices=["scan", "sort", "dose", "full"])
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--image", type=str, help="Test with a static image instead of live camera")
    args = parser.parse_args()

    mode = RobotMode(args.mode)
    orchestrator = MedicineOrchestrator(config_path=args.config, mode=mode)

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Could not read: {args.image}")
            return

        if mode == RobotMode.SCAN:
            # For static image, run OCR directly (no multiprocessing needed)
            ocr_text = orchestrator.dose_reader.extract_text(frame)
            result = orchestrator.process_ocr_result(ocr_text)
            if result:
                print(f"Result: {result}")
            else:
                print(f"Partial scan — missing: {orchestrator.scan_state.get_missing_fields()}")
        elif mode == RobotMode.SORT:
            orchestrator.run_sorting(frame)
        elif mode == RobotMode.DOSE:
            orchestrator.run_dose_reading(frame)
        elif mode == RobotMode.FULL:
            result = orchestrator.run_full_pipeline(frame, frame)
            print(f"\nFull pipeline result:")
            import json
            print(json.dumps(result, indent=2, default=str))
    else:
        # Live camera mode with background OCR
        mp.set_start_method("spawn", force=True)
        orchestrator.run_live(camera_index=args.camera)


if __name__ == "__main__":
    main()
