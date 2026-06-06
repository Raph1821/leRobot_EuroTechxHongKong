import asyncio
import sys
from pathlib import Path

# Allow imports from ai/ when running via uvicorn from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from memory.care_memory import CareMemory
from assistant.llm_client import LLMClient
from core.shared_frame import get_latest_frame

app = FastAPI(title="CareAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

memory = CareMemory()
llm = LLMClient()


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


@app.post("/assistant/ask")
def assistant_ask(body: AskIn):
    _fresh()
    context = memory.get_context()
    try:
        answer = llm.ask(body.message, context=context)
    except Exception as exc:
        answer = f"CareAI is unavailable right now. ({exc})"
    return {"answer": answer}
