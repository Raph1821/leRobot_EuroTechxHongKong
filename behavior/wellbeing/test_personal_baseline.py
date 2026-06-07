import json
import os
import sys

from assistant.memory.care_memory import CareMemory
from behavior.wellbeing.personal_baseline import PersonalBaseline


def main() -> None:
    memory = CareMemory()
    baseline = PersonalBaseline(memory)

    print("=== Computing Personal Baseline (last 14 days) ===")
    result = baseline.update_baseline(days=14)
    print(json.dumps(result, indent=2))
    print()

    # Structural assertions
    required = [
        "daily_interactions", "weekly_health_concerns", "weekly_emergencies",
        "weekly_voice_help_requests", "weekly_missed_reminders", "last_updated",
    ]
    for key in required:
        assert key in result, f"Missing key: {key}"
        if key != "last_updated":
            assert isinstance(result[key], (int, float)), f"{key} should be numeric"
            assert result[key] >= 0, f"{key} should be non-negative"

    assert result["last_updated"] is not None

    # Verify stored in profile
    stored = memory._data["profile"]["baseline"]
    assert stored["last_updated"] == result["last_updated"]
    print("Stored in profile.baseline: OK")

    # Human-readable description
    print()
    print(baseline.describe())

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
