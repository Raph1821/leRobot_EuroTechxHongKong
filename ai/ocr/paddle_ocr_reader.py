"""
PaddleOCR wrapper — compatible with PaddleOCR 2.x and 3.x.

PaddleOCR 3.x (installed) changes:
  - Removed: show_log, use_gpu, use_angle_cls  (use_angle_cls → use_textline_orientation)
  - predict() returns objects with result["rec_texts"] / result["rec_scores"] lists
  - ocr() still exists but is deprecated; we call predict() directly

On first run, PaddleOCR downloads its English model (~100 MB).
Requires: paddleocr  paddlepaddle  (see requirements.txt)
"""

from __future__ import annotations

import logging
import os
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR as _PaddleOCR
    import paddleocr as _paddleocr_mod
    _PADDLE_AVAILABLE = True
    _PADDLE_VERSION = getattr(_paddleocr_mod, "__version__", "2")
    _IS_V3 = int(str(_PADDLE_VERSION).split(".")[0]) >= 3
except ImportError:
    _PADDLE_AVAILABLE = False
    _IS_V3 = False


class PaddleOCRReader:
    """Wraps PaddleOCR 2.x / 3.x with a stable interface for frame-level inference."""

    def __init__(self, lang: str = "en") -> None:
        if not _PADDLE_AVAILABLE:
            raise RuntimeError(
                "PaddleOCR is not installed.  Run:  pip install paddleocr paddlepaddle"
            )

        os.environ.setdefault("GLOG_minloglevel", "2")
        os.environ.setdefault("FLAGS_logtostderr", "0")

        if _IS_V3:
            # PaddleOCR 3.x: device='cpu' replaces use_gpu; use_textline_orientation
            # replaces use_angle_cls; show_log does not exist.
            self._ocr = _PaddleOCR(
                lang=lang,
                use_textline_orientation=True,
                device="cpu",
            )
        else:
            # PaddleOCR 2.x legacy API
            self._ocr = _PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                show_log=False,
                use_gpu=False,
            )

        logger.info("PaddleOCR %s initialised (lang=%s)", _PADDLE_VERSION, lang)

    # ── public ────────────────────────────────────────────────────────────────

    def read_frame(self, frame: np.ndarray) -> List[str]:
        """Run OCR on *frame* and return recognised text lines (confidence ≥ 0.30)."""
        return [text for text, _ in self.read_with_confidence(frame)]

    def read_with_confidence(self, frame: np.ndarray) -> List[Tuple[str, float]]:
        """Run OCR and return ``[(text, confidence), …]`` pairs."""
        if frame is None or frame.size == 0:
            return []
        try:
            if _IS_V3:
                raw = self._ocr.predict(frame)
            else:
                raw = self._ocr.ocr(frame, cls=True)
        except Exception as exc:
            logger.warning("OCR inference error: %s", exc)
            return []
        return self._parse_result(raw)

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_result(raw) -> List[Tuple[str, float]]:
        """
        Parse PaddleOCR output into (text, confidence) pairs.

        PaddleOCR 3.x:  list of dict-like objects with keys
                         ``rec_texts`` (list[str]) and ``rec_scores`` (list[float])

        PaddleOCR 2.x:  ``[[  [bbox, (text, conf)], …  ]]``
                     or ``[   [bbox, (text, conf)], …   ]``
        """
        if not raw:
            return []

        results: List[Tuple[str, float]] = []

        # ── 3.x format: list of result objects ───────────────────────────────
        first = raw[0] if raw else None
        if first is not None and hasattr(first, "__getitem__") and not isinstance(first, list):
            # dict-like OCRResult objects
            for res in raw:
                try:
                    texts  = res["rec_texts"]
                    scores = res["rec_scores"]
                except (KeyError, TypeError):
                    continue
                for text, score in zip(texts, scores):
                    text = str(text).strip()
                    if text and float(score) >= 0.30:
                        results.append((text, float(score)))
            return results

        # ── 2.x format: nested lists ──────────────────────────────────────────
        lines = (
            raw[0]
            if raw and isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], list)
            else raw
        )
        for item in lines:
            if item is None or len(item) < 2:
                continue
            text_info = item[1]
            if not (isinstance(text_info, (list, tuple)) and len(text_info) >= 2):
                continue
            try:
                text = str(text_info[0]).strip()
                conf = float(text_info[1])
            except (TypeError, ValueError):
                continue
            if text and conf >= 0.30:
                results.append((text, conf))

        return results
