import json
import os
import sys

from assistant.memory.care_memory import CareMemory
from behavior.wellbeing.wellbeing_report import WellbeingReport


def main() -> None:
    memory = CareMemory()
    reporter = WellbeingReport(memory, llm_client=None)  # fallback path
    report = reporter.generate(days=7)

    print("=== Wellbeing Report ===")
    print(json.dumps(report, indent=2))
    print()

    # Structural assertions
    assert "risk_level" in report
    assert report["risk_level"] in ("NORMAL", "CAUTION", "HIGH_RISK")
    assert isinstance(report["score"], int)
    assert 0 <= report["score"] <= 100
    assert isinstance(report["summary"], str) and len(report["summary"]) > 0
    assert isinstance(report["reasons"], list)
    assert "created_at" in report

    # Stored in memory
    reports = memory._data.get("wellbeing_reports", [])
    assert len(reports) >= 1
    assert reports[-1]["risk_level"] == report["risk_level"]
    print(f"Stored in wellbeing_reports: {len(reports)} report(s)")

    # Summary wording guard — must not contain medical diagnosis language
    forbidden = ["disease", "diagnos", "cancer", "disorder"]
    for word in forbidden:
        assert word not in report["summary"].lower(), f"Forbidden word in summary: {word}"

    print("All assertions passed.")


if __name__ == "__main__":
    main()
