"""
Medicine Name Parser — from teammate's leRobot_EuroTechxHongKong repo.

Uses fuzzy matching (rapidfuzz) against a 300+ medicine name database
to identify medicine names in OCR text.
"""

import json
import re
from pathlib import Path
from typing import Optional

from rapidfuzz import process, fuzz

_DATA_PATH = Path(__file__).parent / "data" / "medicine_names.json"
_FUZZY_THRESHOLD = 88


def _load() -> list[str]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


_NAMES: list[str] = _load()
_MAX_NAME_WORDS: int = max(len(n.split()) for n in _NAMES)


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_medicine_name(ocr_text: str) -> Optional[str]:
    """Find medicine name in OCR text using exact substring + fuzzy matching."""
    normalized = _normalize(ocr_text)
    if not normalized:
        return None

    # Exact substring match (fast path)
    for name in _NAMES:
        if name in normalized:
            return name

    # Fuzzy: slide an n-gram window over OCR words, score against all names
    words = normalized.split()
    best_score = 0.0
    best_name: Optional[str] = None

    for n in range(1, min(_MAX_NAME_WORDS, len(words)) + 1):
        for i in range(len(words) - n + 1):
            candidate = " ".join(words[i : i + n])
            match = process.extractOne(
                candidate,
                _NAMES,
                scorer=fuzz.ratio,
                score_cutoff=_FUZZY_THRESHOLD,
            )
            if match and match[1] > best_score:
                best_score = match[1]
                best_name = match[0]

    return best_name
