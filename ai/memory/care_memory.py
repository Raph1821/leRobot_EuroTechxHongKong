import json
import os
from datetime import datetime, timezone

_EMPTY: dict = {
    "scanned_medicines": [],
    "events": [],
    "emergencies": [],
    "medicine_schedule": [],
    "daily_summaries": [],
}


class CareMemory:
    def __init__(self, path: str = "ai/data/care_memory.json") -> None:
        self._path = path
        self._data = self.load()

    def load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key in _EMPTY:
                    data.setdefault(key, [])
                return data
            except (json.JSONDecodeError, OSError):
                pass
        return {k: list(v) for k, v in _EMPTY.items()}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def add_medicine(
        self,
        medicine_name: str,
        expiration_date: str,
        status: str | None = None,
    ) -> None:
        for entry in self._data["scanned_medicines"]:
            if entry["name"] == medicine_name and entry["expiration_date"] == expiration_date:
                return
        self._data["scanned_medicines"].append({
            "name": medicine_name,
            "expiration_date": expiration_date,
            "status": status,
            "scanned_at": _now(),
        })
        self.save()

    def add_event(
        self,
        event_type: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        self._data["events"].append({
            "type": event_type,
            "message": message,
            "data": data,
            "timestamp": _now(),
        })
        self.save()

    def add_emergency(
        self,
        source: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        self._data["emergencies"].append({
            "source": source,
            "message": message,
            "data": data,
            "timestamp": _now(),
        })
        self.save()

    def get_context(self) -> dict:
        return {
            "scanned_medicines": list(self._data["scanned_medicines"]),
            "recent_events": self._data["events"][-20:],
            "recent_emergencies": self._data["emergencies"][-10:],
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
