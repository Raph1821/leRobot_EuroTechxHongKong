# Server

> Elda's HTTP backend — the API layer that bridges the robot's internal modules with the web dashboard and external clients.

---

## Overview

`server/` exposes Elda's capabilities over HTTP. The web interface (`webapp/`) and any authorised remote client can query care data, issue commands, and receive a live camera stream without direct access to the robot's internal processes.

`api_server.py` contains no business logic of its own — it translates HTTP requests into calls to `assistant/`, `core/`, and `assistant/memory/`, then serialises the results for the caller. All intelligence stays in the domain modules.

---

## Stack

Built with **[FastAPI](https://fastapi.tiangolo.com/)** and served by **[Uvicorn](https://www.uvicorn.org/)**.

---

## API Capabilities

| Endpoint group | What it does |
|---|---|
| **Memory** | Read and write the patient profile, medication schedules, scanned medicines, and event history |
| **Conversation** | Accept a text query, run intent classification, and return Elda's response — the same pipeline as voice interaction, over HTTP |
| **Live frame** | Stream the latest camera frame (JPEG) from `core/shared_frame.py` for the dashboard's robot-eye view |
| **Mode control** | Switch Elda between Patrol Mode and Sorting Mode |

---

## Running the Server

From the **repository root**:

```bash
# Development (auto-reload on file change)
uvicorn server.api_server:app --reload --host 0.0.0.0 --port 8000

# Production (no reload, bind to all interfaces)
uvicorn server.api_server:app --host 0.0.0.0 --port 8000 --workers 1
```

The webapp expects the API at `http://localhost:8000` by default.  
Set `ANTHROPIC_API_KEY` before starting if conversational responses are required.

---

## Interactive API Documentation

FastAPI generates live documentation automatically. Once the server is running:

| Interface | URL |
|---|---|
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| OpenAPI schema (JSON) | `http://localhost:8000/openapi.json` |

---

## Architecture Boundaries

`server/` is a thin HTTP adapter. It must not:

- Contain business logic or care decisions
- Import from `behavior/` or `manipulation/` directly
- Maintain its own persistent state — all state lives in `assistant/memory/`
