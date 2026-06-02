"""
Tests for the expiration date parser, medicine name parser, scan state machine,
and virtual sorter.

Run:
    python3 tests/test_medicine_parser.py
"""

import sys
from pathlib import Path

# Make `from ai.*` imports work when running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.ocr.expiration_date_parser import parse_expiration_date, get_expiration_status
from ai.ocr.medicine_text_parser import MedicineTextParser
from ai.scanner.medicine_scan_state import MedicineScanState
from ai.sorting.virtual_sorter import sort_medicine


PASS = "OK  "
FAIL = "FAIL"


def check(label: str, got, expected) -> bool:
    ok = got == expected
    print(f"[{PASS if ok else FAIL}]  {label}")
    if not ok:
        print(f"       expected: {expected!r}")
        print(f"       got:      {got!r}")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Expiration date parser
# ─────────────────────────────────────────────────────────────────────────────

def test_expiration_parser() -> int:
    print("\n=== Expiration date parser ===")
    failures = 0

    cases = [
        ("EXP 09/2026",                   "09/2026"),
        ("EXP: 09.2026",                  "09/2026"),
        ("Best before 12-25",             "12/2025"),
        ("MHD 06/2027",                   "06/2027"),
        ("EXP202609",                     "09/2026"),
        ("EXP 202609",                    "09/2026"),
        ("Lot 123 EXP 09/2026",           "09/2026"),
        ("Use before 2026/09",            "09/2026"),
        ("MFG 01/2024  EXP 09/2026",      "09/2026"),
        ("EXP 12.25",                     "12/2025"),
        ("Expiry Date: 09-2026",          "09/2026"),
        ("Verwendbar bis 06/2027",        "06/2027"),
        ("haltbar bis 08-2026",           "08/2026"),
        ("some random text 99/9999",       None),
    ]

    for text, expected in cases:
        result = parse_expiration_date([text])
        got = result.normalized_date if result else None
        if not check(f"parse({text!r})", got, expected):
            failures += 1

    print()
    ok = check("status: expired", get_expiration_status("01/2020"), "expired")
    if not ok:
        failures += 1
    ok = check("status: valid  ", get_expiration_status("01/2099"), "valid")
    if not ok:
        failures += 1
    ok = check("status: unknown", get_expiration_status(None), "unknown")
    if not ok:
        failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Medicine name parser
# ─────────────────────────────────────────────────────────────────────────────

def test_name_parser() -> int:
    print("\n=== Medicine name parser ===")
    failures = 0
    parser = MedicineTextParser()

    cases = [
        (["IBUPROFEN 400 mg Tablets"],       "Ibuprofen"),
        (["Vitamin D3 1000 IU"],             "Vitamin D3"),
        (["Paracetamol Suspension"],         "Paracetamol"),
        (["Omega-3 Fish Oil"],               "Omega 3"),
        (["ASPIRIN 81mg cardio"],            "Aspirin"),
        (["totally unrelated xyzabc"],       None),
    ]

    for lines, expected in cases:
        result = parser.extract_name(lines)
        got = result[0] if result else None
        if not check(f"name({lines[0]!r})", got, expected):
            failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Virtual sorter
# ─────────────────────────────────────────────────────────────────────────────

def test_sorter() -> int:
    print("\n=== Virtual sorter ===")
    failures = 0

    sr = sort_medicine("Ibuprofen", "09/2020")
    if not check("expired medicine → bin B", sr.recommended_action, "place_in_bin_B"):
        failures += 1
    if not check("expired status", sr.status, "expired"):
        failures += 1

    sr = sort_medicine("Ibuprofen", "09/2099")
    if not check("valid medicine → bin A", sr.recommended_action, "place_in_bin_A"):
        failures += 1
    if not check("valid status", sr.status, "valid"):
        failures += 1

    sr = sort_medicine("unknown", None)
    if not check("missing data → keep scanning", sr.recommended_action, "keep_scanning"):
        failures += 1

    sr = sort_medicine("Aspirin", None)
    if not check("missing exp → keep scanning", sr.recommended_action, "keep_scanning"):
        failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Scan state machine
# ─────────────────────────────────────────────────────────────────────────────

def test_scan_state() -> int:
    print("\n=== Scan state machine ===")
    failures = 0

    state = MedicineScanState()

    if not check("starts incomplete", state.is_complete(), False):
        failures += 1
    if not check("both fields missing", set(state.get_missing_fields()), {"medicine_name", "expiration_date"}):
        failures += 1

    # Add a frame with the medicine name
    state.add_ocr_sample(["IBUPROFEN 400 mg", "Film coated tablets"])
    if not check("still incomplete after name only", state.is_complete(), False):
        failures += 1
    missing = state.get_missing_fields()
    if not check("only expiration_date still missing", missing, ["expiration_date"]):
        failures += 1

    # Add a frame with expiration date + keyword
    state.add_ocr_sample(["Lot A1234", "EXP 08/2027"])
    if not check("complete after both fields", state.is_complete(), True):
        failures += 1
    if not check("no missing fields", state.get_missing_fields(), []):
        failures += 1

    result = state.get_scan_result()
    if not check("medicine name = Ibuprofen", result.medicine_name, "Ibuprofen"):
        failures += 1
    if not check("expiration date = 08/2027", result.expiration_date, "08/2027"):
        failures += 1
    if not check("status = valid", result.status, "valid"):
        failures += 1
    if not check("ready_for_sorting = True", result.ready_for_sorting, True):
        failures += 1

    # n-key guard: cannot proceed if not complete
    state.reset()
    if not check("reset → incomplete", state.is_complete(), False):
        failures += 1

    # Verify 'n' key logic (missing fields message)
    missing_after_reset = state.get_missing_fields()
    if not check("missing both after reset", set(missing_after_reset), {"medicine_name", "expiration_date"}):
        failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Format output
# ─────────────────────────────────────────────────────────────────────────────

def test_format_output() -> int:
    print("\n=== ScanResult.format_output ===")
    failures = 0

    state = MedicineScanState()
    state.add_ocr_sample(["Paracetamol 500mg"])
    state.add_ocr_sample(["EXP 03/2028"])

    if state.is_complete():
        output = state.get_scan_result().format_output()
        if not check("output contains medicine name", "Paracetamol" in output, True):
            failures += 1
        if not check("output contains expiration date", "03/2028" in output, True):
            failures += 1
        if not check("output contains READY", "yes" in output, True):
            failures += 1
        print()
        print(output)
    else:
        print("[FAIL]  scan did not complete — check name/date parsing")
        failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    total_failures = 0
    total_failures += test_expiration_parser()
    total_failures += test_name_parser()
    total_failures += test_sorter()
    total_failures += test_scan_state()
    total_failures += test_format_output()

    print("\n" + "=" * 48)
    if total_failures == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"FAILED: {total_failures} test(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()
