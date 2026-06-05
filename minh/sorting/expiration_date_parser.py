"""
Expiration Date Parser — from teammate's leRobot_EuroTechxHongKong repo.

Extracts normalized expiration dates (MM/YYYY) from OCR text.
Handles multiple formats: EXP, MHD, Haltbar bis, Use before, etc.
"""

import re
from typing import Optional


_EXP_KW = re.compile(
    r'(?:exp(?:ir(?:ation|y|es?)|\.?)'
    r'|use\s+before'
    r'|best\s+before'
    r'|valid\s+until'
    r'|mhd'
    r'|haltbar\s+bis'
    r'|verwendbar\s+bis'
    r'|ablaufdatum)',
    re.IGNORECASE,
)

_PROD_KW = re.compile(
    r'(?:mf[gd]|manufactured|production|prod\.)',
    re.IGNORECASE,
)

# Tried in order; first match wins.
_DATE_PATS = [
    # YYYYMM compact (no separator): 202609
    re.compile(r'(?<!\d)(?P<year>20\d{2})(?P<month>0[1-9]|1[0-2])(?!\d)'),
    # MM/YYYY  MM.YYYY  MM-YYYY
    re.compile(r'\b(?P<month>0[1-9]|1[0-2]|[1-9])[/.\-](?P<year>20\d{2})\b'),
    # YYYY/MM  YYYY-MM
    re.compile(r'\b(?P<year>20\d{2})[/\-](?P<month>0[1-9]|1[0-2])\b'),
    # MM/YY  MM.YY  MM-YY  (2-digit year → 20xx; restricted to 20-49)
    re.compile(r'\b(?P<month>0[1-9]|1[0-2]|[1-9])[/.\-](?P<y2>[2-4]\d)\b'),
]

_TIME_RE = re.compile(r'\b\d{1,2}[:.]\d{2}\b')


def _extract_date(text: str) -> Optional[str]:
    text = _TIME_RE.sub(' ', text)
    for pat in _DATE_PATS:
        m = pat.search(text)
        if not m:
            continue
        gd = m.groupdict()
        month = int(gd['month'])
        year = (2000 + int(gd['y2'])) if 'y2' in gd and gd['y2'] else int(gd['year'])
        if 1 <= month <= 12:
            return f"{month:02d}/{year}"
    return None


def parse_expiration_date(text: str) -> Optional[str]:
    """Return normalized expiration date MM/YYYY extracted from OCR text, or None."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    exp_idx: set[int] = set()
    prod_idx: set[int] = set()
    for i, line in enumerate(lines):
        if _EXP_KW.search(line):
            exp_idx.add(i)
        if _PROD_KW.search(line):
            prod_idx.add(i)

    # Pass 1: date in text after the exp keyword on the same line
    for i in sorted(exp_idx):
        m = _EXP_KW.search(lines[i])
        if m:
            date = _extract_date(lines[i][m.end():])
            if date:
                return date

    # Pass 2: date on the line immediately after an exp keyword line
    for i in sorted(exp_idx):
        j = i + 1
        if j < len(lines) and j not in prod_idx:
            date = _extract_date(lines[j])
            if date:
                return date

    # Pass 3: date anywhere on an exp keyword line
    for i in sorted(exp_idx):
        date = _extract_date(lines[i])
        if date:
            return date

    # Pass 4: bare date on any non-production line
    for i, line in enumerate(lines):
        if i not in prod_idx:
            date = _extract_date(line)
            if date:
                return date

    return None
