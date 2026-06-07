# Core

> Elda's shared infrastructure — low-level primitives used across every module in the system.

---

## Overview

`core/` provides the utilities that multiple modules need but that belong to no single domain. It exists to prevent circular imports and duplicated boilerplate.

**The rule is strict:** modules inside `core/` may only import from the standard library and third-party packages. They must never import from `perception/`, `manipulation/`, `behavior/`, `assistant/`, or `server/`. This keeps `core/` dependency-free and makes it trivial to test in isolation.

---

## Components

### `event_log.py` — Structured Event Logger

Centralised event recording for all significant runtime moments: medicines scanned, mode switches, emergencies detected, reminders fired. Every event is timestamped in ISO 8601 format and written to `assistant/memory/care_memory.py` so it appears in the history available to `behavior/summary/` and `behavior/wellbeing/`.

Using a single `EventLog` instance across all modules ensures a consistent event schema and a queryable, chronological record of everything Elda observed during a session.

---

### `shared_frame.py` — Process-Safe Frame Buffer

A single-slot shared frame buffer that allows the camera process and the HTTP server to run in separate processes without shared memory or inter-process queues.

**How it works:**

```
Camera process                      API server process
      │                                     │
      ▼                                     ▼
set_latest_frame(frame)           get_latest_frame()
      │                                     │
      └──▶  /tmp/elda_frame.jpg  ◀──────────┘
            (atomic write via temp file + os.replace)
```

The atomic write — encode to a temp file, then `os.replace` — guarantees the server never reads a partially written frame. On POSIX systems, `os.replace` is a single kernel call and cannot be interrupted mid-write.

---

### `modes.py` — Application Mode Enum

Defines the `AppMode` enum: `PATROL`, `SORTING`, `IDLE`, and any future operating modes. Centralising this constant means `main.py`, `behavior/patrol/`, and `server/api_server.py` all reference the same values without importing from each other.

---

## When to Add Something Here

Add to `core/` only when **both** conditions are true:

1. The utility is used by two or more top-level modules
2. It contains no domain logic — no care decisions, no LLM calls, no sensor access

If only one module uses a utility today, keep it in that module. Move it here when a second module genuinely needs it.
