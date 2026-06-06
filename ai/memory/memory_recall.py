from datetime import datetime


class MemoryRecall:
    def __init__(self, memory) -> None:
        self._memory = memory

    def find_medicine(self, medicine_name: str) -> list[dict]:
        query = medicine_name.lower()
        return [
            m for m in self._memory._data.get("scanned_medicines", [])
            if query in m.get("name", "").lower()
        ]

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        return self._memory._data.get("events", [])[-limit:]

    def get_recent_emergencies(self, limit: int = 5) -> list[dict]:
        return self._memory._data.get("emergencies", [])[-limit:]

    def get_today_summary_data(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        mem = self._memory._data
        events_today = [
            e for e in mem.get("events", [])
            if e.get("timestamp", "").startswith(today)
        ]
        scans_today = [e for e in events_today if e.get("type") == "medicine_scanned"]
        emergencies_today = [
            e for e in mem.get("emergencies", [])
            if e.get("timestamp", "").startswith(today)
        ]
        return {
            "date": today,
            "events_count": len(events_today),
            "scans_count": len(scans_today),
            "emergencies_count": len(emergencies_today),
            "recent_events": events_today[-5:],
        }

    def get_today_schedules(self) -> list[dict]:
        return self._memory.get_active_schedules()
