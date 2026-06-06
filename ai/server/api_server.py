import sys
from pathlib import Path

# Allow imports from ai/ when running via uvicorn from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from memory.care_memory import CareMemory

app = FastAPI(title="CareAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

memory = CareMemory()


class ScheduleIn(BaseModel):
    medicine_name: str
    dose: str
    times: list[str]
    notes: str = ""


def _fresh() -> dict:
    """Reload from disk on every request so the webapp always sees current data."""
    memory._data = memory.load()
    return memory._data


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
    return _fresh().get("medicine_schedule", [])


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
