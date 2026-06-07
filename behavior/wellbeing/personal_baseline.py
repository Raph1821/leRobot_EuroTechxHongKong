from datetime import datetime, timedelta, timezone


class PersonalBaseline:
    def __init__(self, memory) -> None:
        self._memory = memory

    def compute(self, days: int = 14) -> dict:
        """
        Compute averages from the last `days` days of memory.
        Returns a baseline dict with per-day and per-week averages.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        weeks = max(days / 7, 1)
        mem = self._memory._data

        events = [e for e in mem.get("events", []) if e.get("timestamp", "") >= cutoff]
        emergencies = [e for e in mem.get("emergencies", []) if e.get("timestamp", "") >= cutoff]
        dose_history = [d for d in mem.get("dose_history", []) if d.get("timestamp", "") >= cutoff]

        # Daily interactions: all events logged in the period
        daily_interactions = _round(len(events) / max(days, 1))

        # Weekly health concerns
        health_concerns = [e for e in events if "health_concern" in e.get("type", "").lower()]
        weekly_health_concerns = _round(len(health_concerns) / weeks)

        # Weekly emergencies (all sources)
        weekly_emergencies = _round(len(emergencies) / weeks)

        # Weekly voice help requests
        voice = [e for e in emergencies if "voice" in e.get("source", "").lower()]
        weekly_voice_help_requests = _round(len(voice) / weeks)

        # Weekly missed reminders (from dose_history if it exists)
        missed = [d for d in dose_history if d.get("status") == "missed"]
        weekly_missed_reminders = _round(len(missed) / weeks)

        return {
            "daily_interactions": daily_interactions,
            "weekly_health_concerns": weekly_health_concerns,
            "weekly_emergencies": weekly_emergencies,
            "weekly_voice_help_requests": weekly_voice_help_requests,
            "weekly_missed_reminders": weekly_missed_reminders,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def update_baseline(self, days: int = 14) -> dict:
        """Compute baseline and store it in the profile."""
        baseline = self.compute(days=days)
        self._memory._data.setdefault("profile", {})
        self._memory._data["profile"]["baseline"] = baseline
        self._memory.save()
        return baseline

    def get_baseline(self) -> dict:
        """Return stored baseline, or a blank one if not yet computed."""
        return self._memory._data.get("profile", {}).get("baseline", {})

    def describe(self) -> str:
        """Return a short human-readable description of the stored baseline."""
        b = self.get_baseline()
        if not b or b.get("last_updated") is None:
            return "No personal baseline has been established yet."

        lines = ["Personal baseline (normal patterns for this person):"]
        lines.append(f"  - Daily interactions logged:    {b['daily_interactions']} per day")
        lines.append(f"  - Health concerns:              {b['weekly_health_concerns']} per week")
        lines.append(f"  - Emergency events:             {b['weekly_emergencies']} per week")
        lines.append(f"  - Voice help requests:          {b['weekly_voice_help_requests']} per week")
        lines.append(f"  - Missed medicine reminders:    {b['weekly_missed_reminders']} per week")
        lines.append(f"  - Last updated: {b['last_updated'][:10]}")
        return "\n".join(lines)


def _round(value: float) -> float:
    return round(value, 1)
