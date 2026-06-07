# server/

Backend API server for CareAI.

## What belongs here

- FastAPI REST endpoints (`api_server.py`)
- Coordination server integrations
- Dashboard backends

## Running

```bash
uvicorn server.api_server:app --reload --host 0.0.0.0 --port 8000
```
