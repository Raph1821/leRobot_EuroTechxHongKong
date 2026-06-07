import os
import sys

from assistant.memory.care_memory import CareMemory
from behavior.wellbeing.wellbeing_signals import WellbeingSignals
from behavior.wellbeing.wellbeing_score import WellbeingScore


def _check(label: str, signals: dict, expected_level: str) -> None:
    result = WellbeingScore().calculate(signals)
    ok = result["risk_level"] == expected_level
    print(f"[{'OK' if ok else 'FAIL'}] {label}: score={result['score']} level={result['risk_level']}")
    for r in result["reasons"]:
        print(f"       - {r}")
    assert ok, f"Expected {expected_level}, got {result['risk_level']} (score={result['score']})"


def _base(**overrides) -> dict:
    base = {
        "period_days": 7,
        "health_concern_count": 0,
        "voice_emergency_count": 0,
        "camera_emergency_count": 0,
        "fall_event_count": 0,
        "missed_reminder_count": 0,
        "medicine_scanned_count": 2,
        "expired_medicine_count": 0,
    }
    base.update(overrides)
    return base


def main() -> None:
    print("=== Unit tests ===")

    # 0 pts → NORMAL
    _check("All clear", _base(), "NORMAL")

    # 15 pts → NORMAL  (1 concern = 15)
    _check("One health concern", _base(health_concern_count=1), "NORMAL")

    # 30 pts → CAUTION  (2 concerns = 30)
    _check("Two health concerns", _base(health_concern_count=2), "CAUTION")

    # 25 pts → NORMAL  (1 voice = 25)
    _check("One voice emergency", _base(voice_emergency_count=1), "NORMAL")

    # 55 pts → CAUTION  (1 voice=25 + 2 concerns=30)
    _check("Voice + 2 concerns", _base(voice_emergency_count=1, health_concern_count=2), "CAUTION")

    # 55 pts → CAUTION  (fall=30 + 1 missed=10 + 3 expired=15)
    _check("Fall + missed + expired", _base(camera_emergency_count=1, missed_reminder_count=1, expired_medicine_count=3), "CAUTION")

    # 60 pts → HIGH_RISK  (fall=30 + 1 voice=25 + 1 concern=15 = 70, capped...)
    _check("Fall + voice + concern", _base(camera_emergency_count=1, voice_emergency_count=1, health_concern_count=1), "HIGH_RISK")

    # Max cap at 100
    result = WellbeingScore().calculate(_base(
        camera_emergency_count=1, voice_emergency_count=3,
        health_concern_count=3, missed_reminder_count=3, expired_medicine_count=3
    ))
    assert result["score"] <= 100, "Score exceeded 100"
    assert result["risk_level"] == "HIGH_RISK"
    print(f"[OK] Score cap: score={result['score']} level={result['risk_level']}")

    # --- Live memory ---
    print("\n=== Live memory ===")
    memory = CareMemory()
    signals = WellbeingSignals(memory).extract(days=7)
    result = WellbeingScore().calculate(signals)

    print(f"Risk level : {result['risk_level']}")
    print(f"Score      : {result['score']}/100")
    print("Reasons    :")
    if result["reasons"]:
        for r in result["reasons"]:
            print(f"  - {r}")
    else:
        print("  (none — all clear)")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
