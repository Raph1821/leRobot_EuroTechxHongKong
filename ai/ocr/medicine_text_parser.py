"""
Extracts medicine names from OCR text using exact then fuzzy matching
against ai/data/medicine_names.json.

OCR normalization applied before matching:
  - lowercase
  - punctuation stripped
  - common OCR digit/letter confusions corrected (0→o, 1→i in alpha context)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz, process as rf_process
    _RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher  # type: ignore[assignment]
    _RAPIDFUZZ = False

_DEFAULT_NAMES_FILE = Path(__file__).resolve().parent.parent / "data" / "medicine_names.json"

# Minimum fuzzy score (0–1) required to report a match
_FUZZY_THRESHOLD = 0.72

_RE_PUNCT = re.compile(r"[^\w\s]")
_RE_0_IN_WORD = re.compile(r"(?<=[a-z])0(?=[a-z])")
_RE_1_IN_WORD = re.compile(r"(?<=[a-z])1(?=[a-z])")
_RE_SPACES = re.compile(r"\s+")


class MedicineTextParser:
    """Match OCR text lines against the medicine name database."""

    def __init__(self, names_file: Optional[Path] = None) -> None:
        path = names_file or _DEFAULT_NAMES_FILE
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self._names: List[str] = data["medicines"]
        # lowercase → original casing
        self._lower_to_orig: Dict[str, str] = {n.lower(): n for n in self._names}
        self._lower_list: List[str] = list(self._lower_to_orig.keys())

    # ── public ───────────────────────────────────────────────────────────────

    def extract_name(self, text_lines: List[str]) -> Optional[Tuple[str, float]]:
        """
        Extract a medicine name from a list of OCR text lines.

        Returns ``(canonical_name, confidence)`` where confidence is 0–1,
        or ``None`` if no match meets the threshold.
        Exact matches always win over fuzzy matches.
        """
        best_fuzzy: Optional[Tuple[str, float]] = None

        for line in text_lines:
            norm = self._normalize(line)
            if not norm:
                continue

            exact = self._exact_match(norm)
            if exact:
                return exact  # exact match is definitive

            fuzzy = self._fuzzy_match(norm)
            if fuzzy and (best_fuzzy is None or fuzzy[1] > best_fuzzy[1]):
                best_fuzzy = fuzzy

        return best_fuzzy

    # ── private ──────────────────────────────────────────────────────────────

    def _normalize(self, text: str) -> str:
        text = text.lower()
        text = _RE_PUNCT.sub(" ", text)
        text = _RE_0_IN_WORD.sub("o", text)
        text = _RE_1_IN_WORD.sub("i", text)
        return _RE_SPACES.sub(" ", text).strip()

    def _exact_match(self, norm: str) -> Optional[Tuple[str, float]]:
        for name_lower, name_orig in self._lower_to_orig.items():
            # Require whole-word boundary so "iron" doesn't match "environ"
            pattern = r"\b" + re.escape(name_lower) + r"\b"
            if re.search(pattern, norm):
                return name_orig, 1.0
        return None

    def _fuzzy_match(self, norm: str) -> Optional[Tuple[str, float]]:
        words = norm.split()
        best_name: Optional[str] = None
        best_score = 0.0

        # Try n-gram chunks from longest to shortest (prefer multi-word names)
        max_n = min(4, len(words))
        for n in range(max_n, 0, -1):
            for i in range(len(words) - n + 1):
                chunk = " ".join(words[i : i + n])
                if len(chunk) < 3:
                    continue

                if _RAPIDFUZZ:
                    hit = rf_process.extractOne(
                        chunk,
                        self._lower_list,
                        scorer=fuzz.ratio,
                        score_cutoff=int(_FUZZY_THRESHOLD * 100),
                    )
                    if hit:
                        score = hit[1] / 100.0
                        if score > best_score:
                            best_score = score
                            best_name = self._lower_to_orig[hit[0]]
                else:
                    for name_lower in self._lower_list:
                        ratio = SequenceMatcher(None, chunk, name_lower).ratio()
                        if ratio > best_score and ratio >= _FUZZY_THRESHOLD:
                            best_score = ratio
                            best_name = self._lower_to_orig[name_lower]

        if best_name and best_score >= _FUZZY_THRESHOLD:
            return best_name, best_score
        return None
