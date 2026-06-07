from dataclasses import dataclass
from typing import Any, Optional

from assistant.intents import (
    EMERGENCY_STATUS, EXPIRE_SOON, FIND_MEDICINE, HELP, LAST_EMERGENCY,
    LIST_MEDICINES, RECENT_EVENTS, SWITCH_TO_PATROL, SWITCH_TO_SORTING,
    TODAY_SCHEDULE, UNKNOWN, WELLBEING_STATUS,
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
    profile: Optional[dict] = None,
    active_schedules: Optional[list] = None,
    recent_emergencies: Optional[list] = None,
    wellbeing_reporter: Any = None,
) -> ActionResult:
    if intent == LIST_MEDICINES:
        return _list_medicines(scanned_medicines)
    if intent == EXPIRE_SOON:
        return _expire_soon(scanned_medicines)
    if intent == RECENT_EVENTS:
        return _recent_events(recent_events)
    if intent == EMERGENCY_STATUS:
        return _emergency_status(patrol_status, recent_events)
    if intent == FIND_MEDICINE:
        return _find_medicine(scanned_medicines, user_message)
    if intent == TODAY_SCHEDULE:
        return _today_schedule(active_schedules or [])
    if intent == LAST_EMERGENCY:
        return _last_emergency(recent_emergencies or [])
    if intent == WELLBEING_STATUS:
        return _wellbeing_status(wellbeing_reporter)
    if intent == SWITCH_TO_PATROL:
        return ActionResult("Switched to patrol mode.", switch_mode="PATROL")
    if intent == SWITCH_TO_SORTING:
        return ActionResult("Switched to sorting mode.", switch_mode="SORTING")
    if intent == HELP:
        return _help()
    # UNKNOWN — fall back to Claude
    return _ask_claude(
        llm_client, user_message, scanned_medicines, recent_events,
        patrol_status, current_mode, profile, active_schedules, recent_emergencies,
    )


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
    from behavior.patrol.emergency_state import EMERGENCY_CONFIRMED
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
        "- Have I scanned Vitamin D?\n"
        "- What should I take today?\n"
        "- What expires soon?\n"
        "- What happened today?\n"
        "- When was the last emergency?\n"
        "- Was there an emergency?\n"
        "- Start patrol mode / Switch to sorting mode\n"
        "- How am I doing? / Wellbeing status\n"
        "- Anything else (answered by Elda)"
    )


def _wellbeing_status(wellbeing_reporter) -> ActionResult:
    if not wellbeing_reporter:
        return ActionResult("Wellbeing reporting is not available right now.")
    try:
        report = wellbeing_reporter.generate()
        level = report["risk_level"]
        score = report["score"]
        reasons = report["reasons"]

        lines = [f"Current wellbeing status: {level} (score {score}/100)."]

        if reasons:
            lines.append("Elda noticed: " + "; ".join(r.lower() for r in reasons) + ".")
        else:
            lines.append("No significant wellbeing risk signals detected.")

        if level == "HIGH_RISK":
            lines.append(
                "This is not a diagnosis. Please consider contacting a caregiver "
                "or healthcare professional."
            )
        elif level == "CAUTION":
            lines.append(
                "This is not a diagnosis — these are observed patterns. "
                "Consider checking in with a caregiver."
            )
        else:
            lines.append("Keep up the good routine.")

        return ActionResult("\n".join(lines))
    except Exception as exc:
        return ActionResult(f"Could not generate wellbeing report. ({exc})")


def _find_medicine(medicines: list[dict], user_message: str) -> ActionResult:
    if not medicines:
        return ActionResult("I don't have that information yet.")
    text = user_message.lower()
    matches = [m for m in medicines if m["medicine_name"].lower() in text]
    if matches:
        m = matches[0]
        status = m.get("status", "unknown")
        return ActionResult(
            f"Yes, {m['medicine_name'].title()} is in your records "
            f"(expires {m.get('expiration_date', '?')}, {status})."
        )
    # No specific name found in query — list all
    return _list_medicines(medicines)


def _today_schedule(schedules: list[dict]) -> ActionResult:
    if not schedules:
        return ActionResult("No medicines scheduled for today.")
    lines = ["Today's medicine schedule:"]
    for s in schedules:
        times_str = ", ".join(s["times"])
        lines.append(f"- {s['medicine_name'].title()} — {s['dose']} at {times_str}")
    return ActionResult("\n".join(lines))


def _last_emergency(emergencies: list[dict]) -> ActionResult:
    if not emergencies:
        return ActionResult("I don't have any emergency records.")
    last = emergencies[-1]
    ts = last.get("timestamp", "")
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts).astimezone()
        ts_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        ts_str = ts[:16]
    return ActionResult(f"Last emergency: {last.get('message', '?')} ({ts_str}).")


def _ask_claude(llm_client, user_message, medicines, events, patrol_status, current_mode, profile=None, active_schedules=None, recent_emergencies=None) -> ActionResult:
    if not llm_client:
        return ActionResult("I'm not sure how to help with that.")
    try:
        context = {
            "current_mode": current_mode,
            "scanned_medicines": medicines,
            "recent_events": events,
            "patrol_status": patrol_status,
        }
        if profile:
            context["profile"] = profile
        if active_schedules:
            context["active_schedules"] = active_schedules
        if recent_emergencies:
            context["recent_emergencies"] = recent_emergencies
        return ActionResult(llm_client.ask(user_message, context=context))
    except Exception as exc:
        return ActionResult(f"Elda error: {exc}")
