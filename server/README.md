# server/

Elda's HTTP backend — the API layer that connects the robot's internal modules to the web dashboard and external clients.

## Purpose

The server exposes Elda's capabilities over HTTP so the web interface (`webapp/`) and any remote client can query care data, send commands, and stream live camera frames without needing direct access to the robot's processes. All business logic stays in the other modules; `api_server.py` only translates HTTP requests into calls to `assistant/`, `core/`, and `assistant/memory/`.

## api_server.py

Built with [FastAPI](https://fastapi.tiangolo.com/). Key responsibilities:

- **Care memory endpoints** — read and write patient profile, medication schedules, scanned medicines, and event history via REST.
- **Conversation endpoint** — accepts a text query, runs intent classification, and returns Elda's response. The same pipeline used by voice interaction, accessible over HTTP.
- **Live frame streaming** — serves the latest camera frame (JPEG) from the shared frame buffer in `core/shared_frame.py`. Used by the dashboard for a live robot-eye view.
- **Mode control** — accepts requests to switch Elda between Patrol and Sorting modes.

## Running the server

From the repo root:

```bash
uvicorn server.api_server:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag watches for file changes and is suitable for development. Remove it in production.

The webapp expects the API at `http://localhost:8000` by default. Set `ANTHROPIC_API_KEY` before starting if LLM responses are needed.

## API reference

Once running, interactive docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
