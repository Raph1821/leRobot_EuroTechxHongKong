import asyncio
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from assistant.memory.care_memory import CareMemory
from assistant.llm_client import LLMClient
from assistant.care_context_builder import CareContextBuilder
from assistant.intents import classify_intent, SWITCH_TO_PATROL, SWITCH_TO_SORTING
from core.shared_frame import get_latest_frame

app = FastAPI(title="Elda API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

memory = CareMemory()
llm = LLMClient()

_READ_ONLY_MSG = (
    "This web assistant is currently read-only. "
    "I can answer questions, but I cannot change system state yet."
)
_ACTION_INTENTS = {SWITCH_TO_PATROL, SWITCH_TO_SORTING}
_ACTION_KEYWORDS = [
    "switch to patrol", "start patrol", "patrol mode",
    "switch to sorting", "sorting mode",
    "delete schedule", "remove schedule", "add schedule", "create schedule",
    "change profile", "update profile", "trigger reminder",
]

def _is_action_request(message: str) -> bool:
    if classify_intent(message)["intent"] in _ACTION_INTENTS:
        return True
    text = message.lower()
    return any(kw in text for kw in _ACTION_KEYWORDS)


# ── Web-assistant intent detection ────────────────────────────────────────────
# Separate from the terminal assistant intents — the web UI has its own
# vocabulary and will grow its own handlers over time.

WEB_NEXT_DOSE        = "NEXT_DOSE"
WEB_TAKEN_TODAY      = "TAKEN_TODAY"
WEB_TODAY_SCHEDULE   = "TODAY_SCHEDULE"
WEB_WEEK_SCHEDULE    = "WEEK_SCHEDULE"
WEB_LIST_MEDICATIONS = "LIST_MEDICATIONS"
WEB_RECENT_EVENTS    = "RECENT_EVENTS"
WEB_WELLBEING        = "WELLBEING_STATUS"
WEB_NON_HEALTH       = "NON_HEALTH"
WEB_UNKNOWN          = "UNKNOWN"

# Ordered longest-first within each group so "next dose" beats "dose".
_WEB_RULES: list[tuple[str, list[str]]] = [
    (WEB_NEXT_DOSE,        ["next dose", "when do i take", "what do i take next",
                             "time to take", "upcoming dose"]),
    (WEB_TAKEN_TODAY,      ["taken today", "did i take", "have i taken",
                             "already taken", "medicines today"]),
    (WEB_WEEK_SCHEDULE,    ["plan for the week", "weekly plan", "schedule for the week",
                             "following week", "this week's schedule", "this week"]),
    (WEB_TODAY_SCHEDULE,   ["today's schedule", "today schedule", "what should i take",
                             "scheduled today", "plan for today", "today's plan",
                             "what is my plan today", "what should i do today",
                             "schedule today"]),
    (WEB_LIST_MEDICATIONS, ["what medicines", "list medicines", "my medicines",
                             "which medicines", "all medicines", "medications do i have",
                             "what do i have"]),
    (WEB_RECENT_EVENTS,    ["what happened", "recent events", "events today",
                             "activity", "what happened today"]),
    (WEB_WELLBEING,        ["how am i doing", "wellbeing", "health concerns",
                             "am i okay", "am i ok", "any risks",
                             "overall status", "care status"]),
    (WEB_NON_HEALTH,       ["weather", "news", "sports", "stock", "recipe",
                             "joke", "movie", "music", "politics"]),
]


_INVALID_NAMES = {"?", "unknown", "", "none", "null"}
_NON_HEALTH_ANSWER = (
    "I'm focused on care, medicines, wellbeing, and emergency support. "
    "I can help with your medication schedule, scanned medicines, "
    "reminders, emergencies, or wellbeing status."
)


def _answer_list_medications(data: dict) -> str:
    # Scheduled medicines (active only)
    scheduled = {
        s["medicine_name"].strip().lower(): s
        for s in data.get("medicine_schedule", [])
        if s.get("active") and s.get("medicine_name", "").strip().lower() not in _INVALID_NAMES
    }

    # Scanned medicines (valid status, valid name)
    scanned = [
        m for m in data.get("scanned_medicines", [])
        if m.get("name", "").strip().lower() not in _INVALID_NAMES
        and m.get("status") != "expired"
    ]

    if not scheduled and not scanned:
        return "I don't have any medicines on record yet."

    lines = []

    if scheduled:
        lines.append("Scheduled medicines:")
        for s in scheduled.values():
            times_str = ", ".join(s["times"])
            lines.append(f"  - {s['medicine_name'].title()} — {s['dose']} at {times_str}")

    if scanned:
        lines.append("Scanned medicines:")
        for m in scanned:
            lines.append(f"  - {m['name'].title()} (exp. {m.get('expiration_date', '?')}, {m.get('status', 'unknown')})")

    return "\n".join(lines)


def _answer_today_schedule(data: dict) -> str:
    active = [s for s in data.get("medicine_schedule", []) if s.get("active")]
    if not active:
        return "You have no active medicine schedules for today."
    lines = ["Your scheduled doses for today:"]
    for s in active:
        times_str = ", ".join(s["times"])
        line = f"- {s['medicine_name'].title()} — {s['dose']} at {times_str}"
        if s.get("notes"):
            line += f" ({s['notes']})"
        lines.append(line)
    return "\n".join(lines)


def _answer_taken_today(data: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    taken = [
        r for r in data.get("dose_history", [])
        if r.get("status") == "taken"
        and r.get("recorded_at", "").startswith(today)
    ]
    if not taken:
        return "I don't have any confirmed taken doses today."
    lines = ["Today you took:"]
    for r in taken:
        time_str = r.get("scheduled_time") or r.get("recorded_at", "")[:16]
        lines.append(f"- {r.get('medicine_name', '?').title()} at {time_str}")
    return "\n".join(lines)


def _answer_next_dose(data: dict) -> str:
    active = [s for s in data.get("medicine_schedule", []) if s.get("active")]
    candidates = [(t, s) for s in active for t in s.get("times", [])]
    if not candidates:
        return "I don't see any upcoming scheduled doses."

    now_hhmm = datetime.now().strftime("%H:%M")
    future = [(t, s) for t, s in candidates if t > now_hhmm]
    t, s = min(future, key=lambda x: x[0]) if future else min(candidates, key=lambda x: x[0])

    answer = f"Your next dose is {s['medicine_name'].title()} at {t}: {s['dose']}."
    if s.get("notes"):
        answer += f" {s['notes'].capitalize()}."
    return answer


def _answer_recent_events(data: dict) -> str:
    events = data.get("events", [])[-10:]
    if not events:
        return "No recent events recorded."
    lines = ["Recent activity:"]
    for e in events[-5:]:
        lines.append(f"- {e.get('message', e.get('type', '?'))}")
    return "\n".join(lines)


def _answer_wellbeing(data: dict) -> str:
    reports = data.get("wellbeing_reports", [])
    if not reports:
        return "No wellbeing report available yet."
    last = reports[-1]
    level = last.get("risk_level", "unknown")
    score = last.get("score")
    reasons = last.get("reasons", [])
    lines = [f"Wellbeing status: {level} (score {score}/100)."]
    if reasons:
        lines.append("Observed: " + "; ".join(r.lower() for r in reasons) + ".")
    else:
        lines.append("No significant risk signals detected.")
    if level == "HIGH_RISK":
        lines.append("Consider contacting a caregiver or healthcare professional.")
    return "\n".join(lines)


def _answer_week_schedule(data: dict) -> str:
    active = [s for s in data.get("medicine_schedule", []) if s.get("active")]
    if not active:
        return "You have no active medicine schedules this week."
    lines = ["This week's medication plan (daily recurring):"]
    for s in active:
        times_str = ", ".join(s["times"])
        line = f"- {s['medicine_name'].title()} — {s['dose']} at {times_str}"
        if s.get("notes"):
            line += f" ({s['notes']})"
        lines.append(line)
    return "\n".join(lines)


def _classify_web_intent(message: str) -> str:
    """Return first matching intent (single-intent path, kept for logging)."""
    text = message.lower().strip()
    for intent, phrases in _WEB_RULES:
        for phrase in phrases:
            if phrase in text:
                return intent
    return WEB_UNKNOWN


def _classify_all_web_intents(message: str) -> list[str]:
    """Return all matching intents. NON_HEALTH / UNKNOWN only if nothing else matched."""
    text = message.lower().strip()
    matched = []
    non_health = False
    for intent, phrases in _WEB_RULES:
        if intent == WEB_NON_HEALTH:
            non_health = any(p in text for p in phrases)
            continue
        if intent == WEB_UNKNOWN:
            continue
        if any(p in text for p in phrases):
            matched.append(intent)
    if not matched:
        return [WEB_NON_HEALTH] if non_health else [WEB_UNKNOWN]
    return matched


class AskIn(BaseModel):
    message: str


class ScheduleIn(BaseModel):
    medicine_name: str
    dose: str
    times: list[str]
    notes: str = ""


def _fresh() -> dict:
    """Reload from disk on every request so the webapp always sees current data."""
    memory._data = memory.load()
    return memory._data


@app.get("/doses/history")
def doses_history(days: int = 7):
    _fresh()
    return memory.get_dose_history(days=days)


@app.get("/doses/dispensed/last7days")
def doses_dispensed_last7days():
    _fresh()
    records = memory.get_doses_dispensed_last_7_days()

    from datetime import timedelta, date as _date
    today = datetime.now().date()
    day_counts: dict[str, int] = {}
    for offset in range(6, -1, -1):  # 6 days ago → today
        d = today - timedelta(days=offset)
        day_counts[d.isoformat()] = 0

    for r in records:
        date_str = r.get("recorded_at", "")[:10]
        if date_str in day_counts:
            day_counts[date_str] += 1

    DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days_out = [
        {"day": DAY_LABELS[_date.fromisoformat(d).weekday()], "count": c}
        for d, c in day_counts.items()
    ]

    taken_doses = len(records)
    active_schedules = [s for s in memory._data.get("medicine_schedule", []) if s.get("active")]
    scheduled_doses = sum(len(s.get("times", [])) for s in active_schedules) * 7

    if scheduled_doses > 0:
        on_time_pct = min(100, round(taken_doses / scheduled_doses * 100))
    elif taken_doses > 0:
        on_time_pct = 100
    else:
        on_time_pct = 0

    print("=== DOSE ANALYTICS ===")
    print(f"scheduled_doses={scheduled_doses}")
    print(f"taken_doses={taken_doses}")
    print(f"on_time_pct={on_time_pct}")
    print(f"daily_counts={dict(day_counts)}")
    print("======================")

    return {"days": days_out, "total": taken_doses, "on_time_pct": on_time_pct}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/state")
def state():
    data = _fresh()
    return {
        "profile": data.get("profile", {}),
        "scanned_medicines": data.get("scanned_medicines", []),
        "events": data.get("events", []),
        "emergencies": data.get("emergencies", []),
        "medicine_schedule": data.get("medicine_schedule", []),
    }


@app.get("/medicines")
def medicines():
    return _fresh().get("scanned_medicines", [])


@app.get("/events")
def events():
    return _fresh().get("events", [])


@app.get("/schedule")
def schedule_list():
    all_schedules = _fresh().get("medicine_schedule", [])
    return [s for s in all_schedules if s.get("active", True)]


@app.get("/schedule/next")
def schedule_next():
    _fresh()
    active = [s for s in memory._data.get("medicine_schedule", []) if s.get("active")]
    candidates = [(t, s) for s in active for t in s.get("times", [])]
    if not candidates:
        return {"has_next": False}

    now_hhmm = datetime.now().strftime("%H:%M")
    future = [(t, s) for t, s in candidates if t > now_hhmm]
    t, s = min(future, key=lambda x: x[0]) if future else min(candidates, key=lambda x: x[0])

    return {
        "has_next": True,
        "medicine_name": s["medicine_name"],
        "dose": s["dose"],
        "time": t,
        "notes": s.get("notes", ""),
    }


@app.post("/schedule")
def schedule_add(body: ScheduleIn):
    _fresh()
    sid = memory.add_medicine_schedule(
        medicine_name=body.medicine_name,
        dose=body.dose,
        times=body.times,
        notes=body.notes,
    )
    entry = next(s for s in memory._data["medicine_schedule"] if s["id"] == sid)
    return {"success": True, "schedule": entry}


@app.delete("/schedule/{schedule_id}")
def schedule_delete(schedule_id: str):
    _fresh()
    removed = memory.remove_medicine_schedule(schedule_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True, "schedule_id": schedule_id}


@app.get("/camera/stream")
async def camera_stream():
    async def generate():
        while True:
            frame = get_latest_frame()
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
            await asyncio.sleep(1 / 15)  # 15 fps cap

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/camera/snapshot")
def camera_snapshot():
    frame = get_latest_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="No frame available yet")
    return Response(content=frame, media_type="image/jpeg")


_DETERMINISTIC: dict[str, object] = {
    WEB_NEXT_DOSE:        lambda d: _answer_next_dose(d),
    WEB_TODAY_SCHEDULE:   lambda d: _answer_today_schedule(d),
    WEB_WEEK_SCHEDULE:    lambda d: _answer_week_schedule(d),
    WEB_TAKEN_TODAY:      lambda d: _answer_taken_today(d),
    WEB_LIST_MEDICATIONS: lambda d: _answer_list_medications(d),
    WEB_RECENT_EVENTS:    lambda d: _answer_recent_events(d),
    WEB_WELLBEING:        lambda d: _answer_wellbeing(d),
    WEB_NON_HEALTH:       lambda _: _NON_HEALTH_ANSWER,
}


@app.post("/assistant/ask")
def assistant_ask(body: AskIn):
    if _is_action_request(body.message):
        return {"answer": _READ_ONLY_MSG}

    intents = _classify_all_web_intents(body.message)
    print(f"assistant_intent={','.join(intents)}")

    _fresh()
    parts: list[str] = []
    needs_llm = False

    for intent in intents:
        handler = _DETERMINISTIC.get(intent)
        if handler:
            parts.append(handler(memory._data))
        else:
            needs_llm = True

    if needs_llm:
        context = CareContextBuilder(memory).build_context()
        try:
            llm_answer = llm.ask(body.message, context=context)
            parts.append(llm_answer)
        except Exception as exc:
            if not parts:
                parts.append(f"Elda is unavailable right now. ({exc})")

    return {"answer": "\n\n".join(parts)}
