"""
Stateful accumulator for medicine scan results across multiple OCR frames.

Rules for stabilisation
────────────────────────
Medicine name becomes stable when:
  • An exact match is seen at least once (confidence ≥ 0.99), OR
  • A fuzzy match is seen at least 2 times with confidence ≥ 0.75

Expiration date becomes stable when:
  • The same normalised date appears at least once near an EXP keyword, OR
  • The same normalised date appears at least 2 times regardless of keyword

Scan is COMPLETE only when BOTH fields are stable.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ai.ocr.expiration_date_parser import parse_expiration_date
from ai.ocr.medicine_text_parser import MedicineTextParser
from ai.sorting.virtual_sorter import SortResult, sort_medicine

_NAMES_FILE = Path(__file__).resolve().parent.parent / "data" / "medicine_names.json"

# ── stabilisation thresholds ─────────────────────────────────────────────────
_EXACT_NAME_OCCURRENCES = 1
_FUZZY_NAME_OCCURRENCES = 2
_FUZZY_NAME_CONFIDENCE = 0.75
_EXP_KEYWORD_OCCURRENCES = 1
_EXP_BARE_OCCURRENCES = 2


@dataclass
class ScanResult:
    medicine_name: str                 # canonical name or "unknown"
    expiration_date: Optional[str]     # "MM/YYYY" or None
    status: str                        # valid | expired | unknown
    sort_category: str
    recommended_action: str
    ready_for_sorting: bool

    def format_output(self) -> str:
        exp_str = self.expiration_date or "unknown"
        lines = [
            "================ MEDICINE SCAN ================",
            f"Medicine name:      {self.medicine_name}",
            f"Expiration date:    {exp_str}",
            "",
            f"Status:             {self.status}",
            f"Sort category:      {self.sort_category}",
            f"Recommended action: {self.recommended_action}",
            f"Ready for sorting:  {'yes' if self.ready_for_sorting else 'no'}",
            "===============================================",
        ]
        return "\n".join(lines)


class MedicineScanState:
    """
    Accumulates per-frame OCR results and determines when both medicine name
    and expiration date have been confidently identified.
    """

    def __init__(self) -> None:
        self._parser = MedicineTextParser(_NAMES_FILE)
        self._reset_state()

    # ── public API ────────────────────────────────────────────────────────────

    def add_ocr_sample(self, text_lines: List[str]) -> None:
        """Process one round of OCR output and update internal counts."""
        if not text_lines:
            return

        self._ocr_samples.append(text_lines)
        self._scan_count += 1

        # ── medicine name ──────────────────────────────────────────────────
        name_hit = self._parser.extract_name(text_lines)
        if name_hit:
            name, conf = name_hit
            self._name_counts[name] += 1
            self._name_conf[name] = max(self._name_conf.get(name, 0.0), conf)

        # ── expiration date ────────────────────────────────────────────────
        exp_hit = parse_expiration_date(text_lines)
        if exp_hit:
            date = exp_hit.normalized_date
            self._exp_counts[date] += 1
            if exp_hit.near_keyword:
                self._exp_kw_counts[date] += 1

        self._try_stabilise()

    def is_complete(self) -> bool:
        return self._scan_complete

    def get_missing_fields(self) -> List[str]:
        missing = []
        if self._stable_name is None:
            missing.append("medicine_name")
        if self._stable_exp is None:
            missing.append("expiration_date")
        return missing

    def get_scan_result(self) -> ScanResult:
        """Return the definitive result.  Call only when is_complete() is True."""
        return self._build_result(
            name=self._stable_name or "unknown",
            exp=self._stable_exp,
            complete=self._scan_complete,
        )

    def get_partial_result(self) -> ScanResult:
        """Return the best-guess result even if scanning is not complete."""
        name = self._stable_name
        if name is None and self._name_counts:
            name = self._name_counts.most_common(1)[0][0]

        exp = self._stable_exp
        if exp is None and self._exp_counts:
            exp = self._exp_counts.most_common(1)[0][0]

        return self._build_result(
            name=name or "unknown",
            exp=exp,
            complete=self._scan_complete,
        )

    def reset(self) -> None:
        """Clear all state so scanning can begin for the next medicine."""
        self._reset_state()

    def get_debug_info(self) -> str:
        elapsed = time.time() - self._started_at
        lines = [
            "=== DEBUG STATE ===",
            f"OCR samples : {self._scan_count}",
            f"Elapsed     : {elapsed:.1f}s",
            f"Name counts : {dict(self._name_counts.most_common(5))}",
            f"Name conf   : {self._name_conf}",
            f"Exp counts  : {dict(self._exp_counts.most_common(5))}",
            f"Exp kw hits : {dict(self._exp_kw_counts)}",
            f"Stable name : {self._stable_name}",
            f"Stable exp  : {self._stable_exp}",
            f"Complete    : {self._scan_complete}",
            "==================",
        ]
        return "\n".join(lines)

    # ── private ───────────────────────────────────────────────────────────────

    def _reset_state(self) -> None:
        self._ocr_samples: List[List[str]] = []
        self._name_counts: Counter[str] = Counter()
        self._name_conf: Dict[str, float] = {}
        self._exp_counts: Counter[str] = Counter()
        self._exp_kw_counts: Counter[str] = Counter()
        self._stable_name: Optional[str] = None
        self._stable_exp: Optional[str] = None
        self._scan_complete: bool = False
        self._scan_count: int = 0
        self._started_at: float = time.time()

    def _try_stabilise(self) -> None:
        # ── name stabilisation ─────────────────────────────────────────────
        if self._stable_name is None:
            for name, count in self._name_counts.most_common():
                conf = self._name_conf.get(name, 0.0)
                if conf >= 0.99 and count >= _EXACT_NAME_OCCURRENCES:
                    self._stable_name = name
                    break
                if conf >= _FUZZY_NAME_CONFIDENCE and count >= _FUZZY_NAME_OCCURRENCES:
                    self._stable_name = name
                    break

        # ── expiration stabilisation ───────────────────────────────────────
        if self._stable_exp is None:
            for date, count in self._exp_counts.most_common():
                if self._exp_kw_counts.get(date, 0) >= _EXP_KEYWORD_OCCURRENCES:
                    self._stable_exp = date
                    break
                if count >= _EXP_BARE_OCCURRENCES:
                    self._stable_exp = date
                    break

        # ── completion check ───────────────────────────────────────────────
        if self._stable_name is not None and self._stable_exp is not None:
            self._scan_complete = True

    @staticmethod
    def _build_result(name: str, exp: Optional[str], complete: bool) -> ScanResult:
        sr: SortResult = sort_medicine(name, exp)
        return ScanResult(
            medicine_name=name,
            expiration_date=exp,
            status=sr.status,
            sort_category=sr.sort_category,
            recommended_action=sr.recommended_action,
            ready_for_sorting=complete,
        )
