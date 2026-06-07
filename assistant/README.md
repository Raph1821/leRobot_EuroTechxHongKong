# Assistant

> Elda's conversational intelligence — the LLM interface, voice I/O pipeline, intent router, and persistent care memory.

---

## Overview

`assistant/` is the only module in Elda that communicates with an external AI API. It owns two orthogonal concerns that are deliberately kept together: **speech** (how Elda talks and listens) and **memory** (what Elda knows and remembers). Everything the user hears passes through here; everything the robot needs to recall is stored here.

`behavior/` and `manipulation/` must never call an LLM directly — they invoke functions in this module and receive structured results.

---

## Voice Interaction Pipeline

```
Microphone input
        │
        ▼
speech/speech_listener.py       Transcribe audio to text
        │
        ▼
intents.py                      Classify intent
        │                       (LIST_MEDICINES · TODAY_SCHEDULE · EMERGENCY_STATUS · UNKNOWN · …)
        ▼
assistant_actions.py
        ├── Known intent  ──▶   Deterministic handler (no API call)
        └── UNKNOWN       ──▶   llm_client.py  ──▶  Claude API
                                      │
                                      ▼
                              speech/tts_engine.py    Speak the response
```

Intent classification happens first. Only `UNKNOWN` intents reach the LLM, reducing API latency and cost for common, predictable queries.

---

## Components

### LLM Layer

| File | Responsibility |
|---|---|
| `llm_client.py` | Wraps the Claude API. Builds a `[CareContext]` block from live memory and appends it to every prompt. Supports text and vision (image + text) requests. |
| `prompts.py` | Defines `SYSTEM_PROMPT` — the fixed instruction set that establishes Elda's identity, scope, and hard limits (no diagnosis, no invented data). |
| `care_context_builder.py` | Assembles the structured context dictionary from memory before each API call, keeping prompt-building logic separate from the HTTP client. |
| `elda_capabilities.py` | Declarative registry of all features with their required memory fields. Used for introspection and capability negotiation. |

### Intent Routing

| File | Responsibility |
|---|---|
| `intents.py` | Keyword-based classifier that maps user input to a named intent constant before attempting an LLM call. |
| `assistant_actions.py` | Maps each intent to a deterministic handler. Returns a typed `ActionResult`. Falls back to `llm_client.py` only for `UNKNOWN`. |

### `speech/` — Voice I/O

| File | Responsibility |
|---|---|
| `speech_listener.py` | Continuously transcribes microphone input and emits text strings to the main loop. |
| `tts_engine.py` | Converts text to speech. The engine backend can be swapped without changing any caller. |
| `emergency_phrases.py` | Curated list of trigger phrases (e.g. *"help me"*, *"I fell"*) that bypass intent classification and go directly to the emergency flow. |

### `memory/` — Persistent Care Store

| File | Responsibility |
|---|---|
| `care_memory.py` | Central JSON-backed store. Holds medicines, schedules, dose history, emergencies, events, wellbeing reports, briefings, and the patient profile. All writes are atomic (temp file + `os.replace`) to prevent corruption on shutdown. |
| `memory_recall.py` | Read-only query helpers over `CareMemory`. Surfaces named slices of history without exposing the storage schema to callers. |

**Default storage path:** `data/care_memory.json`

---

## Configuration

Elda's LLM features require an Anthropic API key.

```bash
# Option 1 — environment variable
export ANTHROPIC_API_KEY=sk-ant-...

# Option 2 — .env file at the repository root
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

`llm_client.py` loads the `.env` file automatically on import. If the key is missing, LLM calls are disabled and Elda falls back to deterministic responses only.

---

## Running the Tests

```bash
# Test the LLM client end-to-end (requires ANTHROPIC_API_KEY)
python assistant/test_llm_client.py

# Test the care memory store (no API key required)
python assistant/memory/test_care_memory.py
```

---

## Architecture Boundaries

- **Only this module calls the Claude API.** No other module may import an Anthropic SDK directly.
- `memory/` is readable by `behavior/` modules (e.g., `reminders/`, `wellbeing/`) but must never be written to from outside `assistant/`.
- `speech/` is called by `behavior/` modules for TTS output, but speech transcription runs only from the main loop.
