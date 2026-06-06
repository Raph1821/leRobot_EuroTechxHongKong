from datetime import datetime, timedelta, timezone


class WellbeingSignals:
    def __init__(self, memory) -> None:
        self._memory = memory

    def extract(self, days: int = 7) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        mem = self._memory._data

        events = mem.get("events", [])
        emergencies = mem.get("emergencies", [])

        recent_events = [e for e in events if e.get("timestamp", "") >= cutoff_str]
        recent_emergencies = [e for e in emergencies if e.get("timestamp", "") >= cutoff_str]

        # Health concerns
        health_concerns = [
            e for e in recent_events
            if "health_concern" in e.get("type", "").lower()
        ]

        # Voice emergencies
        voice_emergencies = [
            e for e in recent_emergencies
            if "voice" in e.get("source", "").lower()
            or "voice" in e.get("message", "").lower()
        ]

        # Camera / fall emergencies
        fall_keywords = ("camera", "fall", "patrol")
        camera_emergencies = [
            e for e in recent_emergencies
            if any(kw in e.get("source", "").lower() or kw in e.get("message", "").lower()
                   for kw in fall_keywords)
        ]

        # Medicine scans
        medicine_scanned = [
            e for e in recent_events
            if e.get("type", "") == "medicine_scanned"
        ]

        # Missed reminders — only if dose_history exists in memory
        dose_history = mem.get("dose_history", [])
        missed_reminders = [
            d for d in dose_history
            if d.get("status") == "missed"
            and d.get("timestamp", "") >= cutoff_str
        ]

        # Expired medicines in memory (not period-filtered — reflects current stock)
        all_medicines = mem.get("scanned_medicines", [])
        expired_medicines = [m for m in all_medicines if m.get("status") == "expired"]

        return {
            "period_days": days,
            "health_concern_count": len(health_concerns),
            "voice_emergency_count": len(voice_emergencies),
            "camera_emergency_count": len(camera_emergencies),
            "fall_event_count": len(camera_emergencies),
            "missed_reminder_count": len(missed_reminders),
            "medicine_scanned_count": len(medicine_scanned),
            "expired_medicine_count": len(expired_medicines),
            "recent_health_concerns": [_slim_event(e) for e in health_concerns[-5:]],
            "recent_emergencies": [_slim_emergency(e) for e in recent_emergencies[-5:]],
            "recent_events": [_slim_event(e) for e in recent_events[-10:]],
        }


def _slim_event(e: dict) -> dict:
    return {
        "type": e.get("type", ""),
        "message": e.get("message", ""),
        "timestamp": e.get("timestamp", ""),
    }


def _slim_emergency(e: dict) -> dict:
    return {
        "source": e.get("source", ""),
        "message": e.get("message", ""),
        "timestamp": e.get("timestamp", ""),
    }
