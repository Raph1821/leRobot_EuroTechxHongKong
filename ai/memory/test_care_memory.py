import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ai.memory.care_memory import CareMemory

DATA_PATH = "ai/data/care_memory.json"


def main() -> None:
    memory = CareMemory(DATA_PATH)

    memory.add_medicine("Aspirin", "2026-12-31", status="valid")
    memory.add_medicine("Aspirin", "2026-12-31", status="valid")  # duplicate — should be ignored
    memory.add_medicine("Ibuprofen", "2025-03-01", status="expired")

    memory.add_event("scan", "Scanned medicine shelf", {"count": 2})
    memory.add_emergency("voice", "User said: help me")

    ctx = memory.get_context()

    print("=== CareMemory context ===")
    print(f"Medicines ({len(ctx['scanned_medicines'])}):")
    for m in ctx["scanned_medicines"]:
        print(f"  {m['name']} exp={m['expiration_date']} status={m['status']}")

    print(f"Events ({len(ctx['recent_events'])}):")
    for e in ctx["recent_events"]:
        print(f"  [{e['type']}] {e['message']}")

    print(f"Emergencies ({len(ctx['recent_emergencies'])}):")
    for em in ctx["recent_emergencies"]:
        print(f"  [{em['source']}] {em['message']}")

    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    assert len(raw["scanned_medicines"]) == 2, "duplicate not filtered"
    assert len(raw["events"]) >= 1
    assert len(raw["emergencies"]) >= 1
    print(f"\nFile written: {DATA_PATH}")
    print("All assertions passed.")


if __name__ == "__main__":
    main()
