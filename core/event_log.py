from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    timestamp: datetime
    event_type: str
    message: str
    data: Optional[dict] = field(default=None)


class EventLog:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def add_event(self, event_type: str, message: str, data: Optional[dict] = None) -> None:
        self._events.append(Event(
            timestamp=datetime.now(),
            event_type=event_type,
            message=message,
            data=data,
        ))

    def print_recent_events(self, limit: int = 10) -> None:
        recent = self._events[-limit:]
        print("\n================ RECENT EVENTS ================")
        if not recent:
            print("  (no events yet)")
        for e in recent:
            ts = e.timestamp.strftime("%H:%M:%S")
            print(f"[{ts}] {e.event_type}: {e.message}")
        print("==============================================\n")

    def get_all_events(self) -> list[Event]:
        return list(self._events)
