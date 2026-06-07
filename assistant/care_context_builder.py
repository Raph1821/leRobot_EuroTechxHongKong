import json
import os
from datetime import datetime

_INVALID = {"", "?", "unknown", "none", "null"}

_DEMO_SCHEDULE = {
    "id": "demo",
    "medicine_name": "Vitamin D",
    "dose": "1 tablet",
    "times": ["09:00"],
    "notes": "take with food",
    "active": True,
    "source": "demo_mock",
}


class CareContextBuilder:
    def __init__(self, memory) -> None:
        self._memory = memory

    def build_context(self) -> dict:
        mem = self._memory._data
        now = datetime.now()

        medicine_schedule = self._active_schedules(mem)

        context = {
            "current_date": now.strftime("%Y-%m-%d"),
            "profile": self._memory.get_profile(),
            "scanned_medicines": self._valid_scanned(mem),
            "medicine_schedule": medicine_schedule,
            "next_dose": self._next_dose(medicine_schedule, now),
            "dose_history": mem.get("dose_history", []),
            "taken_today": self._taken_today(mem, now),
            "active_reminders": [],
            "emergencies": mem.get("emergencies", [])[-10:],
            "recent_events": mem.get("events", [])[-10:],
            "wellbeing_status": self._wellbeing_status(mem),
            "wellbeing_reports": mem.get("wellbeing_reports", [])[-5:],
            "health_concerns": self._health_concerns(mem),
            "daily_summaries": mem.get("daily_summaries", [])[-3:],
            "morning_briefings": mem.get("briefings", [])[-3:],
        }

        if os.environ.get("CAREAI_DEBUG_CONTEXT", "").lower() == "true":
            print("\n=== CARE CONTEXT ===")
            print(json.dumps(context, indent=2, default=str))
            print("====================\n")

        return context

    def debug_print(self) -> None:
        ctx = self.build_context()
        print("\n=== CARE CONTEXT ===")
        print(json.dumps(ctx, indent=2, default=str))
        print("====================\n")

    # ------------------------------------------------------------------

    def _active_schedules(self, mem: dict) -> list[dict]:
        raw = mem.get("medicine_schedule")
        # Add demo mock only if the key is completely absent from memory
        if raw is None:
            return [_DEMO_SCHEDULE]
        return [
            s for s in raw
            if s.get("active")
            and s.get("medicine_name", "").strip().lower() not in _INVALID
        ]

    def _valid_scanned(self, mem: dict) -> list[dict]:
        return [
            m for m in mem.get("scanned_medicines", [])
            if m.get("name", "").strip().lower() not in _INVALID
        ]

    def _next_dose(self, active_schedules: list[dict], now: datetime) -> dict:
        candidates = [(t, s) for s in active_schedules for t in s.get("times", [])]
        if not candidates:
            return {"has_next": False}
        now_hhmm = now.strftime("%H:%M")
        future = [(t, s) for t, s in candidates if t > now_hhmm]
        t, s = min(future, key=lambda x: x[0]) if future else min(candidates, key=lambda x: x[0])
        return {
            "has_next": True,
            "medicine_name": s["medicine_name"],
            "dose": s["dose"],
            "time": t,
            "notes": s.get("notes", ""),
        }

    def _taken_today(self, mem: dict, now: datetime) -> list[dict]:
        today = now.strftime("%Y-%m-%d")
        return [
            r for r in mem.get("dose_history", [])
            if r.get("status") == "taken"
            and r.get("recorded_at", "").startswith(today)
        ]

    def _wellbeing_status(self, mem: dict) -> dict:
        reports = mem.get("wellbeing_reports", [])
        if reports:
            last = reports[-1]
            return {
                "risk_level": last.get("risk_level"),
                "score": last.get("score"),
                "reasons": last.get("reasons", []),
                "created_at": last.get("created_at"),
            }
        return {"risk_level": None, "score": None, "reasons": [], "created_at": None}

    def _health_concerns(self, mem: dict) -> list[str]:
        reports = mem.get("wellbeing_reports", [])
        if not reports:
            return []
        return reports[-1].get("reasons", [])
