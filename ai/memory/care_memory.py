import json
import os
import uuid
from datetime import datetime, timezone

_EMPTY: dict = {
    "scanned_medicines": [],
    "events": [],
    "emergencies": [],
    "medicine_schedule": [],
    "daily_summaries": [],
}


def _empty_profile() -> dict:
    return {
        "name": "",
        "age": None,
        "caregiver_name": "",
        "caregiver_contact": "",
        "reminder_voice_enabled": True,
        "notes": [],
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
                data.setdefault("profile", {})
                profile = data["profile"]
                for k, v in _empty_profile().items():
                    profile.setdefault(k, v)
                return data
            except (json.JSONDecodeError, OSError):
                pass
        fresh = {k: list(v) for k, v in _EMPTY.items()}
        fresh["profile"] = _empty_profile()
        return fresh

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

    def add_medicine_schedule(
        self,
        medicine_name: str,
        dose: str,
        times: list[str],
        notes: str = "",
    ) -> str:
        schedule_id = str(uuid.uuid4())[:8]
        self._data["medicine_schedule"].append({
            "id": schedule_id,
            "medicine_name": medicine_name,
            "dose": dose,
            "times": list(times),
            "notes": notes,
            "active": True,
            "created_at": _now(),
        })
        self.save()
        return schedule_id

    def get_active_schedules(self) -> list[dict]:
        return [s for s in self._data["medicine_schedule"] if s.get("active")]

    def remove_medicine_schedule(self, schedule_id: str) -> bool:
        before = len(self._data["medicine_schedule"])
        self._data["medicine_schedule"] = [
            s for s in self._data["medicine_schedule"] if s["id"] != schedule_id
        ]
        if len(self._data["medicine_schedule"]) < before:
            self.save()
            return True
        return False

    def mark_schedule_inactive(self, schedule_id: str) -> bool:
        for s in self._data["medicine_schedule"]:
            if s["id"] == schedule_id:
                s["active"] = False
                self.save()
                return True
        return False

    def get_profile(self) -> dict:
        return self._data["profile"]

    def update_profile(self, **kwargs) -> None:
        allowed = {"name", "age", "caregiver_name", "caregiver_contact", "reminder_voice_enabled"}
        profile = self._data["profile"]
        for key, value in kwargs.items():
            if key in allowed:
                profile[key] = value
        self.save()

    def add_profile_note(self, note: str) -> None:
        self._data["profile"]["notes"].append(note)
        self.save()

    def get_context(self) -> dict:
        return {
            "scanned_medicines": list(self._data["scanned_medicines"]),
            "recent_events": self._data["events"][-20:],
            "recent_emergencies": self._data["emergencies"][-10:],
            "profile": self.get_profile(),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
