# core/

Elda's shared infrastructure — low-level utilities used by every other module.

## Purpose

`core/` exists to avoid circular imports and repeated boilerplate. Anything that two or more modules need but that carries no domain logic of its own belongs here. Modules in `core/` must not import from `perception/`, `manipulation/`, `behavior/`, `assistant/`, or `server/`.

## Files

### event_log.py

Central structured event logger. All significant runtime events (medicines scanned, mode switches, emergencies detected, reminders fired) are written through `EventLog` so they appear in the care memory's event history. Using a single logger ensures consistent timestamp formatting and makes the event stream queryable by `behavior/summary/` and `behavior/wellbeing/`.

### shared_frame.py

A process-safe single-slot frame buffer. The camera process encodes the latest frame as a JPEG and atomically writes it to `/tmp/elda_frame.jpg`. The API server reads from the same path to serve live frames over HTTP. The atomic write (temp file + `os.replace`) prevents the server from ever reading a partially written frame.

This design avoids shared memory or queues between processes while keeping latency low — the frame is always either the last complete one or one update behind.

### modes.py

`AppMode` enum — defines the operating modes Elda can be in (`PATROL`, `SORTING`, `IDLE`, etc.). Kept here so that `main.py`, `behavior/patrol/`, and the API server all reference the same constants without any of them depending on each other.

## Guidelines for adding to core/

Add a utility here only if:
1. It is used by two or more top-level modules, and
2. It contains no domain logic (no care decisions, no LLM calls, no sensor access).

If in doubt, put it in the module that owns it first, and move it here only when a second module needs it.
