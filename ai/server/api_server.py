import sys
from pathlib import Path

# Allow imports from ai/ when running via uvicorn from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from memory.care_memory import CareMemory

app = FastAPI(title="CareAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

memory = CareMemory()


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
def schedule():
    return _fresh().get("medicine_schedule", [])
