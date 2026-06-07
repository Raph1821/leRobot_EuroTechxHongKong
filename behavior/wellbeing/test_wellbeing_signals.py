import json
import os
import sys

from assistant.memory.care_memory import CareMemory
from behavior.wellbeing.wellbeing_signals import WellbeingSignals


def main() -> None:
    memory = CareMemory()
    signals = WellbeingSignals(memory)
    result = signals.extract(days=7)

    print("=== Wellbeing Signals (last 7 days) ===")
    print(json.dumps(result, indent=2))
    print()

    # Basic structural assertions
    required_keys = [
        "period_days", "health_concern_count", "voice_emergency_count",
        "camera_emergency_count", "fall_event_count", "missed_reminder_count",
        "medicine_scanned_count", "recent_health_concerns",
        "recent_emergencies", "recent_events",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"
    assert result["period_days"] == 7
    assert isinstance(result["recent_events"], list)
    assert isinstance(result["recent_emergencies"], list)
    assert isinstance(result["recent_health_concerns"], list)

    print("All assertions passed.")


if __name__ == "__main__":
    main()
