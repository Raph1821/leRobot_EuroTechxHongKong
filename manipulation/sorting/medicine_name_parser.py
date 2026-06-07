import json
import re
from pathlib import Path
from typing import Optional

from rapidfuzz import process, fuzz

_DATA_PATH = Path(__file__).parent.parent / "data" / "medicine_names.json"
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


def _run_tests() -> None:
    cases: list[tuple[str, Optional[str]]] = [
        ("IBUPROFEN 400mg tablets",       "ibuprofen"),
        ("Paracetamol 500 MG",            "paracetamol"),
        ("Vitamin D3 1000 IU",            "vitamin d3"),
        ("Omega 3 Fish Oil Softgels",     "omega 3"),
        ("MELATONIN 5mg",                 "melatonin"),
        ("Zinc Gluconate tablets",        "zinc gluconate"),
        ("Magnesium Glycinate 400mg",     "magnesium glycinate"),
        ("PROBIOTICS 10 billion CFU",     "probiotics"),
        ("Calcium Citrate supplement",    "calcium citrate"),
        ("Ferrous Sulfate 325mg",         "ferrous sulfate"),
        ("AMOXICILLIN 500mg capsules",    "amoxicillin"),
        ("Atorvastatin 20 mg",            "atorvastatin"),
        ("Salbutamol inhaler",            "salbutamol"),
        ("Fluoxetine hydrochloride",      "fluoxetine"),
        ("totally unrelated text here",   None),
    ]

    passed = failed = 0
    for text, expected in cases:
        result = find_medicine_name(text)
        if result == expected:
            passed += 1
            print(f"  PASS  {text!r:45s} → {result!r}")
        else:
            failed += 1
            print(f"  FAIL  {text!r:45s} → got {result!r}, expected {expected!r}")

    print(f"\n{passed} passed, {failed} failed out of {len(cases)} tests")


if __name__ == "__main__":
    _run_tests()
