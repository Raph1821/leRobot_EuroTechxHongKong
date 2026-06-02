"""
Medicine object detector.

Detection priority:
1. YOLO (ultralytics) — detects bottles (COCO class 39) and other container-like objects.
2. Contour-based fallback — finds the largest plausible rectangular object.
3. Centre-crop fallback — always succeeds; used when no clear object is found.

The detector is intentionally lenient for demo use: it will always return
a crop so that OCR can run even if the object boundary is imprecise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO as _YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False

# COCO class IDs that plausibly contain medicine labels
_MEDICINE_COCO_IDS = {
    39,   # bottle
    73,   # book (flat rectangular packages)
    26,   # handbag (box-like)
    28,   # suitcase (large box)
    84,   # book (variant index)
}

# Contour-detection tuning
_MIN_AREA_RATIO = 0.04   # contour must cover ≥ 4 % of frame
_MAX_AREA_RATIO = 0.88   # … and ≤ 88 %
_MIN_ASPECT = 0.12       # width / height
_MAX_ASPECT = 9.0
_CENTER_CROP_RATIO = 0.65


@dataclass
class DetectionResult:
    detected: bool
    bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h in frame coords
    crop: Optional[np.ndarray] = None
    confidence: float = 0.0
    method: str = "none"  # yolo | contour | center_crop | none


class MedicineObjectDetector:
    """
    Detects medicine containers (bottles, boxes, blister packs) in camera frames.
    Falls back gracefully when YOLO is unavailable.
    """

    def __init__(self, yolo_model: str = "yolov8n.pt", use_yolo: bool = True) -> None:
        self._yolo: Optional[object] = None

        if use_yolo and _YOLO_AVAILABLE:
            try:
                self._yolo = _YOLO(yolo_model)
                logger.info("YOLO detector loaded: %s", yolo_model)
            except Exception as exc:
                logger.warning("YOLO load failed (%s) — using contour fallback", exc)
        elif not _YOLO_AVAILABLE:
            logger.info(
                "ultralytics not installed — using contour-based object detection. "
                "Install with:  pip install ultralytics"
            )

    # ── public ────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Return a DetectionResult for the most prominent medicine object in *frame*.
        Always returns a result (falls back to centre crop).
        """
        if frame is None or frame.size == 0:
            return DetectionResult(detected=False, method="none")

        if self._yolo is not None:
            result = self._detect_yolo(frame)
            if result.detected:
                return result

        result = self._detect_contour(frame)
        if result.detected:
            return result

        return self._center_crop(frame)

    # ── private ───────────────────────────────────────────────────────────────

    def _detect_yolo(self, frame: np.ndarray) -> DetectionResult:
        try:
            yolo_results = self._yolo(frame, verbose=False, conf=0.30)
            best_conf = 0.0
            best_xyxy: Optional[Tuple[int, int, int, int]] = None

            for r in yolo_results:
                for box in r.boxes:
                    cls_id = int(box.cls.item())
                    conf = float(box.conf.item())
                    if cls_id not in _MEDICINE_COCO_IDS:
                        continue
                    if conf > best_conf:
                        best_conf = conf
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        best_xyxy = (x1, y1, x2, y2)

            if best_xyxy is not None:
                x1, y1, x2, y2 = best_xyxy
                return self._make_result(frame, x1, y1, x2 - x1, y2 - y1, best_conf, "yolo")

        except Exception as exc:
            logger.debug("YOLO detection error: %s", exc)

        return DetectionResult(detected=False)

    def _detect_contour(self, frame: np.ndarray) -> DetectionResult:
        fh, fw = frame.shape[:2]
        frame_area = fh * fw

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 25, 90)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_score = 0.0
        best_bbox: Optional[Tuple[int, int, int, int]] = None

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (frame_area * _MIN_AREA_RATIO <= area <= frame_area * _MAX_AREA_RATIO):
                continue

            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / bh if bh > 0 else 0
            if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT):
                continue

            # Prefer objects near the centre of the frame
            cx, cy = bx + bw // 2, by + bh // 2
            dist = ((cx - fw // 2) ** 2 + (cy - fh // 2) ** 2) ** 0.5
            max_dist = (fw ** 2 + fh ** 2) ** 0.5 / 2
            centre_score = 1.0 - dist / max_dist

            score = area * (0.4 + 0.6 * centre_score)
            if score > best_score:
                best_score = score
                best_bbox = (bx, by, bw, bh)

        if best_bbox is not None:
            x, y, w, h = best_bbox
            conf = min(0.85, best_score / (frame_area * _MAX_AREA_RATIO))
            return self._make_result(frame, x, y, w, h, conf, "contour")

        return DetectionResult(detected=False)

    def _center_crop(self, frame: np.ndarray) -> DetectionResult:
        fh, fw = frame.shape[:2]
        cw, ch = int(fw * _CENTER_CROP_RATIO), int(fh * _CENTER_CROP_RATIO)
        x, y = (fw - cw) // 2, (fh - ch) // 2
        crop = frame[y : y + ch, x : x + cw]
        return DetectionResult(
            detected=True,
            bbox=(x, y, cw, ch),
            crop=crop,
            confidence=0.30,
            method="center_crop",
        )

    @staticmethod
    def _make_result(
        frame: np.ndarray,
        x: int, y: int, w: int, h: int,
        confidence: float,
        method: str,
        pad: int = 18,
    ) -> DetectionResult:
        fh, fw = frame.shape[:2]
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(fw - x, w + 2 * pad)
        h = min(fh - y, h + 2 * pad)
        crop = frame[y : y + h, x : x + w]
        return DetectionResult(
            detected=True,
            bbox=(x, y, w, h),
            crop=crop,
            confidence=confidence,
            method=method,
        )
