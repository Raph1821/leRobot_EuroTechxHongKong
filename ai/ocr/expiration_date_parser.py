"""
Expiration date parser for medicine label OCR text.

Handles many real-world label formats:
  EXP 09/2026 | EXP: 09.2026 | Best before 09-26 | MHD 09/26 | EXP202609 …

Normalises all output to MM/YYYY.
Prefers dates found near expiration keywords.
Ignores dates near production-date keywords (MFG, MFD, …).
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple


@dataclass
class ExpirationResult:
    raw_text: str       # matched string from OCR
    normalized_date: str  # MM/YYYY
    confidence: float   # 0.0 – 1.0
    near_keyword: bool


# ── keyword patterns ────────────────────────────────────────────────────────

_EXP_KW = re.compile(
    r'\b(?:'
    r'exp(?:iry|ires?|iration)?\.?\s*:?'
    r'|use\s+(?:before|by)'
    r'|best\s+(?:before|by)'
    r'|bb[de]?'
    r'|mhd'
    r'|ablaufdatum'
    r'|verw(?:endbar)?\s*\.?\s*bis'
    r'|haltbar\s+bis'
    r')\b',
    re.IGNORECASE,
)

_MFG_KW = re.compile(
    r'\b(?:mf[gd]|manufactur(?:ed|ing)?|production|prod\.?|made\s+on)\b',
    re.IGNORECASE,
)

# ── date patterns ────────────────────────────────────────────────────────────
# Each entry: (compiled_pattern, format_key)
#   group 1 = first token, group 2 = second token

_SEP = r'[\s./\-]+'

_DATE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # MM/YYYY — 4-digit year after month (most reliable)
    (re.compile(r'\b(\d{1,2})' + _SEP + r'((?:19|20)\d{2})\b'), 'MM/YYYY'),
    # YYYY/MM — 4-digit year before month
    (re.compile(r'\b((?:19|20)\d{2})' + _SEP + r'(\d{1,2})\b'), 'YYYY/MM'),
    # YYYYMM — compact 6-digit, no separator (e.g. EXP202609 or 202609)
    # Use (?<!\d) so letters immediately before (like "EXP") are fine
    (re.compile(r'(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(?!\d)'), 'YYYYMM'),
    # MM/YY — 2-digit year (lower confidence)
    (re.compile(r'\b(\d{1,2})' + _SEP + r'(\d{2})\b'), 'MM/YY'),
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _fix_ocr_digits(s: str) -> str:
    """Replace common OCR digit/letter confusions."""
    return (
        s.replace('O', '0').replace('o', '0')
         .replace('l', '1').replace('I', '1')
         .replace(',', '.')
    )


def _build_normalized(month: int, year: int) -> Optional[str]:
    if not (1 <= month <= 12):
        return None
    if not (1900 <= year <= 2099):
        return None
    return f"{month:02d}/{year}"


def _parse_match(m: re.Match, fmt: str) -> Optional[Tuple[str, str]]:
    """
    Convert a regex match to (normalized_date, raw_text).
    Returns None if the date is invalid.
    """
    raw = m.group(0)
    try:
        if fmt == 'MM/YYYY':
            month = int(_fix_ocr_digits(m.group(1)))
            year = int(_fix_ocr_digits(m.group(2)))
        elif fmt == 'YYYY/MM':
            year = int(_fix_ocr_digits(m.group(1)))
            month = int(_fix_ocr_digits(m.group(2)))
        elif fmt == 'YYYYMM':
            year = int(m.group(1))
            month = int(m.group(2))
        elif fmt == 'MM/YY':
            month = int(_fix_ocr_digits(m.group(1)))
            year = 2000 + int(_fix_ocr_digits(m.group(2)))
        else:
            return None
    except (ValueError, IndexError):
        return None

    normalized = _build_normalized(month, year)
    return (normalized, raw) if normalized else None


# ── public API ────────────────────────────────────────────────────────────────

def _keyword_confidence(date_start: int, line: str) -> Tuple[float, bool]:
    """
    Return (confidence, near_exp_keyword) for a date starting at *date_start*
    by finding the nearest keyword of any type in *line*.

    If the nearest keyword is an EXP keyword → high confidence.
    If the nearest keyword is a MFG keyword → very low confidence (likely production date).
    If no keywords at all → medium confidence.
    """
    exp_spans = [(m.start(), m.end(), "exp") for m in _EXP_KW.finditer(line)]
    mfg_spans = [(m.start(), m.end(), "mfg") for m in _MFG_KW.finditer(line)]
    all_kw = exp_spans + mfg_spans

    if not all_kw:
        return 0.50, False

    # Distance: from keyword end to date start (keyword before date is most common)
    # Also consider keyword start to date end for reverse order
    def _dist(kw_start: int, kw_end: int) -> int:
        return min(abs(date_start - kw_end), abs(date_start - kw_start))

    nearest = min(all_kw, key=lambda kw: _dist(kw[0], kw[1]))
    _, kw_end, kw_type = nearest
    distance = abs(date_start - kw_end)

    if kw_type == "mfg":
        return 0.08, False

    # Near EXP keyword
    if distance <= 15:
        return 0.97, True
    if distance <= 40:
        return 0.90, True
    if distance <= 100:
        return 0.80, True
    return 0.65, True


def parse_expiration_date(text_lines: List[str]) -> Optional[ExpirationResult]:
    """
    Parse the most confident expiration date from OCR text lines.

    Strategy:
    1. Scan each line for expiration keywords.
    2. Find all date patterns in that line.
    3. Score each date by proximity to its nearest keyword.
    4. Skip lines that contain only production-date keywords.

    Returns the highest-confidence ExpirationResult, or None.
    """
    best: Optional[ExpirationResult] = None

    def _update(candidate: ExpirationResult) -> None:
        nonlocal best
        if best is None or candidate.confidence > best.confidence:
            best = candidate

    for line in text_lines:
        if not line.strip():
            continue

        has_any_exp = bool(_EXP_KW.search(line))
        has_only_mfg = bool(_MFG_KW.search(line)) and not has_any_exp
        if has_only_mfg:
            continue  # production-date-only line

        for pat, fmt in _DATE_PATTERNS:
            for dm in pat.finditer(line):
                parsed = _parse_match(dm, fmt)
                if parsed is None:
                    continue
                normalized, raw = parsed

                confidence, near_keyword = _keyword_confidence(dm.start(), line)

                # 2-digit year is less reliable
                if fmt == "MM/YY":
                    confidence *= 0.85

                _update(ExpirationResult(
                    raw_text=raw,
                    normalized_date=normalized,
                    confidence=confidence,
                    near_keyword=near_keyword,
                ))

    return best


def get_expiration_status(normalized_date: Optional[str]) -> str:
    """Return 'valid', 'expired', or 'unknown' for a MM/YYYY date string."""
    if not normalized_date:
        return "unknown"
    try:
        month, year = map(int, normalized_date.split("/"))
        exp = datetime(year, month, 1)
        now = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return "expired" if exp < now else "valid"
    except ValueError:
        return "unknown"
