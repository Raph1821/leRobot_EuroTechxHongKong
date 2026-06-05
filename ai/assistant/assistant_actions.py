from dataclasses import dataclass
from typing import Any, Optional

from assistant.intents import (
    EMERGENCY_STATUS, EXPIRE_SOON, HELP, LIST_MEDICINES,
    RECENT_EVENTS, SWITCH_TO_PATROL, SWITCH_TO_SORTING, UNKNOWN,
)


@dataclass
class ActionResult:
    message: str
    switch_mode: Optional[str] = None  # "PATROL" | "SORTING" | None


def handle_intent(
    intent: str,
    scanned_medicines: list[dict],
    recent_events: list[dict],
    patrol_status: str,
    current_mode: str,
    llm_client: Any = None,
    user_message: str = "",
) -> ActionResult:
    if intent == LIST_MEDICINES:
        return _list_medicines(scanned_medicines)
    if intent == EXPIRE_SOON:
        return _expire_soon(scanned_medicines)
    if intent == RECENT_EVENTS:
        return _recent_events(recent_events)
    if intent == EMERGENCY_STATUS:
        return _emergency_status(patrol_status, recent_events)
    if intent == SWITCH_TO_PATROL:
        return ActionResult("Switched to patrol mode.", switch_mode="PATROL")
    if intent == SWITCH_TO_SORTING:
        return ActionResult("Switched to sorting mode.", switch_mode="SORTING")
    if intent == HELP:
        return _help()
    # UNKNOWN — fall back to Claude
    return _ask_claude(llm_client, user_message, scanned_medicines, recent_events, patrol_status, current_mode)


# ---------------------------------------------------------------------------

def _list_medicines(medicines: list[dict]) -> ActionResult:
    if not medicines:
        return ActionResult("No medicines scanned yet.")
    lines = ["You currently have:"]
    for m in medicines:
        lines.append(f"- {m['medicine_name'].title()} ({m.get('status', 'unknown')})")
    return ActionResult("\n".join(lines))


def _expire_soon(medicines: list[dict]) -> ActionResult:
    if not medicines:
        return ActionResult("No medicines scanned yet.")

    expired = [m for m in medicines if m.get("status") == "expired"]
    valid   = [m for m in medicines if m.get("status") == "valid"]

    parts = []
    if expired:
        names = ", ".join(m["medicine_name"].title() for m in expired)
        parts.append(f"Expired: {names}.")
    if valid:
        def _sort_key(m: dict) -> tuple:
            try:
                mo, yr = m["expiration_date"].split("/")
                return (int(yr), int(mo))
            except Exception:
                return (9999, 99)
        first = min(valid, key=_sort_key)
        parts.append(f"{first['medicine_name'].title()} expires first ({first['expiration_date']}).")
    if not parts:
        return ActionResult("No expiration data available.")
    return ActionResult(" ".join(parts))


def _recent_events(events: list[dict]) -> ActionResult:
    if not events:
        return ActionResult("No recent events.")
    lines = ["Recent events:"]
    for e in events[-5:]:
        lines.append(f"- {e.get('message', e.get('event_type', '?'))}")
    return ActionResult("\n".join(lines))


def _emergency_status(patrol_status: str, events: list[dict]) -> ActionResult:
    from patrol.emergency_state import EMERGENCY_CONFIRMED
    if patrol_status == EMERGENCY_CONFIRMED:
        return ActionResult("Active emergency confirmed by patrol system.")
    emergency_events = [
        e for e in events
        if e.get("event_type") in ("voice_emergency", "camera_emergency")
    ]
    if emergency_events:
        return ActionResult(f"Last emergency: {emergency_events[-1].get('message', '?')}")
    return ActionResult("No active emergency.")


def _help() -> ActionResult:
    return ActionResult(
        "You can ask:\n"
        "- What medicines do I have?\n"
        "- What expires soon?\n"
        "- What happened today?\n"
        "- Was there an emergency?\n"
        "- Start patrol mode / Switch to sorting mode\n"
        "- Anything else (answered by CareAI)"
    )


def _ask_claude(llm_client, user_message, medicines, events, patrol_status, current_mode) -> ActionResult:
    if not llm_client:
        return ActionResult("I'm not sure how to help with that.")
    try:
        context = {
            "current_mode": current_mode,
            "scanned_medicines": medicines,
            "recent_events": events,
            "patrol_status": patrol_status,
        }
        return ActionResult(llm_client.ask(user_message, context=context))
    except Exception as exc:
        return ActionResult(f"CareAI error: {exc}")
