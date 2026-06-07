from datetime import datetime, timezone
from typing import Optional


class DailySummary:
    def __init__(self, memory, llm_client=None) -> None:
        self._memory = memory
        self._llm = llm_client

    def generate_summary(self, date: Optional[str] = None) -> str:
        today = date or datetime.now().strftime("%Y-%m-%d")
        data = self._collect(today)

        llm_available = self._llm and not getattr(self._llm, "_disabled", True)
        if llm_available:
            summary = self._generate_llm(data, today)
        else:
            summary = self._generate_fallback(data, today)

        self._store(today, summary)
        return summary

    # ------------------------------------------------------------------

    def _collect(self, today: str) -> dict:
        mem = self._memory._data

        medicines = mem.get("scanned_medicines", [])
        expired_names = [
            m["name"] for m in medicines if m.get("status") == "expired"
        ]

        events_today = [
            e for e in mem.get("events", [])
            if e.get("timestamp", "").startswith(today)
        ]
        emergencies_today = [
            e for e in mem.get("emergencies", [])
            if e.get("timestamp", "").startswith(today)
        ]

        last_event: Optional[str] = None
        all_events = mem.get("events", [])
        if all_events:
            last_event = all_events[-1].get("message")

        profile = self._memory.get_profile()

        return {
            "medicines_total": len(medicines),
            "expired_names": expired_names,
            "events_count": len(events_today),
            "emergencies_count": len(emergencies_today),
            "schedules_count": len([
                s for s in mem.get("medicine_schedule", []) if s.get("active")
            ]),
            "last_event": last_event,
            "name": profile.get("name", ""),
        }

    def _generate_llm(self, data: dict, today: str) -> str:
        expired_str = ", ".join(data["expired_names"]) or "none"
        name_line = f"- Patient name: {data['name']}\n" if data.get("name") else ""
        prompt = (
            f"Generate a concise daily care summary for {today}.\n"
            f"Data:\n"
            f"{name_line}"
            f"- Medicines on record: {data['medicines_total']}\n"
            f"- Expired medicines: {expired_str}\n"
            f"- Events today: {data['events_count']}\n"
            f"- Emergencies today: {data['emergencies_count']}\n"
            f"- Active medicine schedules: {data['schedules_count']}\n"
            f"- Most recent event: {data['last_event'] or 'none'}\n\n"
            "Write a friendly, brief summary (3-4 sentences) for a care assistant. "
            "If a patient name is provided, address them by name."
        )
        try:
            return self._llm.ask(prompt)
        except Exception:
            return self._generate_fallback(data, today)

    def _generate_fallback(self, data: dict, today: str) -> str:
        name = data.get("name", "")
        header = f"Daily Care Summary for {name} ({today}):" if name else f"Daily Care Summary ({today}):"
        lines = [header]
        lines.append(f"- Medicines scanned today: {data['medicines_total']}")
        if data["expired_names"]:
            lines.append(f"- Expired medicines: {', '.join(data['expired_names'])}")
        lines.append(f"- Active reminders: {data['schedules_count']}")
        if data["emergencies_count"]:
            lines.append(f"- Emergencies today: {data['emergencies_count']}")
        if data["last_event"]:
            lines.append(f"- Recent important event: {data['last_event']}")
        return "\n".join(lines)

    def _store(self, date: str, summary: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        summaries = self._memory._data["daily_summaries"]
        for entry in summaries:
            if entry.get("date") == date:
                entry["summary"] = summary
                entry["created_at"] = now
                self._memory.save()
                return
        summaries.append({"date": date, "summary": summary, "created_at": now})
        self._memory.save()
