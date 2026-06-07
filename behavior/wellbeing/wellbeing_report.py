from datetime import datetime, timezone

from .wellbeing_signals import WellbeingSignals
from .wellbeing_score import WellbeingScore

_CAREGIVER_SUFFIX = "Consider checking in with a caregiver."
_EMERGENCY_SUFFIX = "Please contact a caregiver or healthcare professional promptly."


class WellbeingReport:
    def __init__(self, memory, llm_client=None) -> None:
        self._memory = memory
        self._llm = llm_client

    def generate(self, days: int = 7) -> dict:
        signals = WellbeingSignals(self._memory).extract(days=days)
        score_result = WellbeingScore().calculate(signals)

        summary = self._build_summary(signals, score_result)

        report = {
            "risk_level": score_result["risk_level"],
            "score": score_result["score"],
            "summary": summary,
            "reasons": score_result["reasons"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._store(report)
        return report

    # ------------------------------------------------------------------

    def _build_summary(self, signals: dict, score_result: dict) -> str:
        llm_available = self._llm and not getattr(self._llm, "_disabled", True)
        if llm_available:
            return self._llm_summary(signals, score_result)
        return self._fallback_summary(signals, score_result)

    def _llm_summary(self, signals: dict, score_result: dict) -> str:
        reasons_str = "; ".join(score_result["reasons"]) or "no significant signals"
        prompt = (
            f"Write a short (2-3 sentence) wellbeing status summary for an elderly care app.\n"
            f"Risk level: {score_result['risk_level']} (score {score_result['score']}/100)\n"
            f"Signals from the last {signals['period_days']} days: {reasons_str}\n\n"
            "Rules:\n"
            "- Do not diagnose or predict disease.\n"
            "- Use careful, non-alarming language.\n"
            "- Refer to the system as 'Elda'.\n"
            "- If risk is HIGH_RISK or CAUTION, recommend contacting a caregiver.\n"
            "- If all clear, say so warmly."
        )
        try:
            return self._llm.ask(prompt)
        except Exception:
            return self._fallback_summary(signals, score_result)

    def _fallback_summary(self, signals: dict, score_result: dict) -> str:
        level = score_result["risk_level"]
        reasons = score_result["reasons"]
        period = signals["period_days"]

        if level == "NORMAL" and not reasons:
            return (
                f"Current wellbeing status is NORMAL. "
                f"Elda detected no significant concerns over the last {period} days."
            )

        parts = [f"Current wellbeing status is {level}."]

        if reasons:
            parts.append(f"Elda noticed: {'; '.join(r.lower() for r in reasons)}.")

        if level == "HIGH_RISK":
            parts.append(_EMERGENCY_SUFFIX)
        elif level == "CAUTION":
            parts.append(_CAREGIVER_SUFFIX)

        return " ".join(parts)

    def _store(self, report: dict) -> None:
        self._memory._data.setdefault("wellbeing_reports", [])
        self._memory._data["wellbeing_reports"].append(report)
        self._memory.save()
