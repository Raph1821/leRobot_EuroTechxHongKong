"""
CareBot AI Medicine Scanner — live camera demo.

Usage:
    python ai/vision/webcam_medicine_scanner.py [--camera INDEX]

Keyboard controls:
    q  quit
    s  force OCR scan of current frame
    r  reset current medicine
    n  confirm and move to next medicine  (only allowed when BOTH fields are found)
    p  print debug / accumulated OCR state
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ── project root on sys.path so that  `from ai.*`  imports work ──────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ai.ocr.paddle_ocr_reader import PaddleOCRReader
from ai.scanner.medicine_scan_state import MedicineScanState, ScanResult
from ai.vision.camera_utils import open_camera, read_frame
from ai.vision.medicine_object_detector import DetectionResult, MedicineObjectDetector

logging.basicConfig(level=logging.WARNING)

# ── timing ────────────────────────────────────────────────────────────────────
_OCR_MIN = 0.8
_OCR_MAX = 1.2

# ── BGR colour palette ────────────────────────────────────────────────────────
_C = {
    "green":   (0,   210,  0),
    "yellow":  (0,   210, 210),
    "red":     (0,    30, 210),
    "white":   (255, 255, 255),
    "black":   (0,     0,   0),
    "dark":    (18,   18,  18),
    "panel":   (28,   22,  52),
    "good_bg": (0,    55,   0),
    "warn_bg": (50,   40,   0),
    "cyan":    (210, 210,   0),
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


# ── drawing helpers ───────────────────────────────────────────────────────────

def _text_size(text: str, scale: float, thickness: int) -> Tuple[int, int]:
    (w, h), baseline = cv2.getTextSize(text, _FONT, scale, thickness)
    return w, h + baseline


def draw_panel(
    frame: np.ndarray,
    lines: List[str],
    x: int,
    y: int,
    *,
    scale: float = 0.54,
    thickness: int = 1,
    pad: int = 8,
    line_gap: int = 4,
    fg: Tuple[int, int, int] = _C["white"],
    bg: Tuple[int, int, int] = _C["panel"],
    alpha: float = 0.82,
) -> int:
    """
    Draw a semi-transparent text panel at (x, y).
    Returns the y coordinate of the panel's bottom edge.
    """
    if not lines:
        return y

    widths = [_text_size(ln, scale, thickness)[0] for ln in lines]
    lh = _text_size("Ag", scale, thickness)[1]
    box_w = max(widths) + pad * 2
    box_h = (lh + line_gap) * len(lines) + pad

    x = max(0, min(x, frame.shape[1] - box_w))
    y = max(0, y)

    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + box_w, y + box_h), bg, cv2.FILLED)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    ty = y + pad + lh - 2
    for line in lines:
        cv2.putText(frame, line, (x + pad, ty), _FONT, scale, fg, thickness, cv2.LINE_AA)
        ty += lh + line_gap

    return y + box_h


def draw_bbox(
    frame: np.ndarray,
    detection: DetectionResult,
    complete: bool,
) -> None:
    if not detection.detected or detection.bbox is None:
        return
    x, y, w, h = detection.bbox
    colour = _C["green"] if complete else _C["yellow"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), colour, 2)
    label = f"[{detection.method}  {detection.confidence:.0%}]"
    ly = max(y - 6, 16)
    cv2.putText(frame, label, (x, ly), _FONT, 0.46, colour, 1, cv2.LINE_AA)


def draw_overlay(
    frame: np.ndarray,
    detection: DetectionResult,
    partial: ScanResult,
    complete: bool,
    missing: List[str],
) -> None:
    h, w = frame.shape[:2]

    # ── title bar ─────────────────────────────────────────────────────────────
    draw_panel(
        frame, ["  CareBot AI Medicine Scanner  "],
        10, 8,
        scale=0.62, bg=(40, 20, 80),
    )

    # ── scan info panel ───────────────────────────────────────────────────────
    det_label = "YES" if detection.detected else "NO "
    name_disp = partial.medicine_name if partial.medicine_name != "unknown" else "scanning..."
    exp_disp  = partial.expiration_date or "scanning..."
    stat_disp = partial.status if partial.expiration_date else "..."

    info_lines = [
        f"Object:   {det_label} ({detection.method})",
        f"Medicine: {name_disp}",
        f"EXP Date: {exp_disp}",
        f"Status:   {stat_disp}",
    ]
    if complete:
        info_lines += [
            f"Category: {partial.sort_category}",
            f"Action:   {partial.recommended_action}",
        ]

    bottom = draw_panel(frame, info_lines, 10, 58)

    # ── ready / scanning status ───────────────────────────────────────────────
    if complete:
        ready_line = "READY FOR SORTING  --  press [n] for next medicine"
        ready_fg   = _C["green"]
        ready_bg   = _C["good_bg"]
    elif missing:
        ready_line = f"Keep scanning  |  still need: {' + '.join(missing)}"
        ready_fg   = _C["yellow"]
        ready_bg   = _C["warn_bg"]
    else:
        ready_line = "Processing..."
        ready_fg   = _C["cyan"]
        ready_bg   = _C["dark"]

    draw_panel(
        frame, [ready_line],
        10, bottom + 5,
        fg=ready_fg, bg=ready_bg,
    )

    # ── controls (bottom of frame) ────────────────────────────────────────────
    ctrl_lines = [
        "q=quit   s=force scan   r=reset   n=next (needs name+EXP)   p=debug",
    ]
    if not complete:
        ctrl_lines.append("Keep showing package until name and EXP date are found.")
    draw_panel(frame, ctrl_lines, 10, h - 62, scale=0.43, bg=_C["dark"])

    # ── bounding box ──────────────────────────────────────────────────────────
    draw_bbox(frame, detection, complete)


# ── main loop ─────────────────────────────────────────────────────────────────

def run_scanner(camera_index: int = 0) -> None:
    print("\n=== CareBot AI Medicine Scanner ===")

    # ── camera ────────────────────────────────────────────────────────────────
    print(f"Opening camera {camera_index}...")
    try:
        cap = open_camera(camera_index)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    # ── OCR engine ────────────────────────────────────────────────────────────
    print("Loading OCR engine (first run downloads model ~100 MB, please wait)...")
    try:
        ocr = PaddleOCRReader()
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        cap.release()
        sys.exit(1)

    # ── object detector ───────────────────────────────────────────────────────
    detector = MedicineObjectDetector()
    state    = MedicineScanState()

    last_ocr_time    = 0.0
    next_ocr_gap     = random.uniform(_OCR_MIN, _OCR_MAX)
    last_detection   = DetectionResult(detected=False, method="none")
    medicine_count   = 0
    was_complete     = False

    print("\nScanner running.  Hold a medicine package in front of the camera.")
    print("Controls:  q=quit  s=scan  r=reset  n=next  p=debug\n")

    while True:
        frame = read_frame(cap)
        if frame is None:
            time.sleep(0.03)
            continue

        # ── detect object ─────────────────────────────────────────────────────
        last_detection = detector.detect(frame)
        crop = (
            last_detection.crop
            if last_detection.detected and last_detection.crop is not None
            else frame
        )

        # ── OCR on timed interval ─────────────────────────────────────────────
        now = time.time()
        if now - last_ocr_time >= next_ocr_gap:
            last_ocr_time = now
            next_ocr_gap  = random.uniform(_OCR_MIN, _OCR_MAX)
            lines = ocr.read_frame(crop)
            if lines:
                state.add_ocr_sample(lines)

        # ── query state ───────────────────────────────────────────────────────
        complete = state.is_complete()
        partial  = state.get_partial_result()
        missing  = state.get_missing_fields()

        # ── announce completion once ──────────────────────────────────────────
        if complete and not was_complete:
            was_complete   = True
            medicine_count += 1
            result = state.get_scan_result()
            print(f"\n--- Medicine #{medicine_count} ---")
            print(result.format_output())

        # ── draw ──────────────────────────────────────────────────────────────
        display = frame.copy()
        draw_overlay(display, last_detection, partial, complete, missing)
        cv2.imshow("CareBot AI Medicine Scanner", display)

        # ── keyboard ──────────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            print("\nQuitting.")
            break

        elif key == ord("s"):
            print("[FORCE SCAN] Running OCR on current frame...")
            lines = ocr.read_frame(crop)
            if lines:
                state.add_ocr_sample(lines)
                print("OCR text:", lines)
            else:
                print("No text detected.")
            last_ocr_time = time.time()

        elif key == ord("r"):
            print("\n[RESET] Clearing current medicine scan.\n")
            state.reset()
            was_complete = False

        elif key == ord("n"):
            if state.is_complete():
                print("\nScan confirmed. Ready for next medicine.\n")
                state.reset()
                was_complete = False
            else:
                fields = " / ".join(state.get_missing_fields())
                print(
                    f"\nCannot move to next medicine yet. "
                    f"Missing: {fields}\n"
                )

        elif key == ord("p"):
            print(state.get_debug_info())

    cap.release()
    cv2.destroyAllWindows()
    print("Scanner closed.")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CareBot AI Medicine Scanner")
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index (0 = built-in MacBook camera, default)",
    )
    args = parser.parse_args()
    run_scanner(camera_index=args.camera)
