# assistant/

Elda's conversational intelligence — the LLM interface, voice I/O pipeline, intent routing, and persistent care memory.

## Purpose

This module gives Elda her voice and her memory. It is the only layer that calls the Claude API. All text the user hears or reads passes through here, and all care data the robot needs to remember is stored here. Nothing in `behavior/` or `manipulation/` should call an LLM directly — they go through this module.

## How a voice interaction flows

```
Microphone
    └── speech/speech_listener.py  →  raw transcript
            └── intents.py         →  classified intent (e.g. TODAY_SCHEDULE, WELLBEING_STATUS, UNKNOWN)
                    └── assistant_actions.py
                            ├── deterministic handler  →  direct answer (no LLM)
                            └── llm_client.py          →  Claude API call with CareContext
                                    └── speech/tts_engine.py  →  spoken response
```

## Files

### Core LLM layer

`llm_client.py` — wraps the Claude API. Builds a structured `[CareContext]` block from memory and appends it to every prompt so the model always has accurate patient data. Supports text-only and vision (image + text) requests. Requires `ANTHROPIC_API_KEY` in the environment or a `.env` file at the repo root.

`prompts.py` — defines `SYSTEM_PROMPT`, the fixed instruction set that tells the LLM who Elda is, what she can answer, and what she must never do (diagnose, invent data, give long disclaimers).

### Intent routing

`intents.py` — a keyword-based intent classifier. Tries to match user input to a named intent (e.g. `LIST_MEDICINES`, `TODAY_SCHEDULE`, `EMERGENCY_STATUS`) before falling back to the LLM. This avoids unnecessary API calls for predictable queries.

`assistant_actions.py` — maps each classified intent to a deterministic handler that reads from memory and returns a structured `ActionResult`. The LLM is only invoked for `UNKNOWN` intents.

`care_context_builder.py` — assembles the `CareContext` dictionary from live memory before each LLM call. Keeps the prompt-building logic out of `llm_client.py`.

`elda_capabilities.py` — declarative registry of all feature capabilities (medicine scanning, scheduling, wellbeing, etc.) with their required memory fields. Used for introspection and future capability negotiation.

### speech/

`speech_listener.py` — continuously transcribes microphone input using a speech-to-text engine. Emits text strings to the main loop.

`tts_engine.py` — converts text responses to spoken audio. Wraps the system TTS so the engine can be swapped without changing callers.

`emergency_phrases.py` — a curated list of trigger phrases (e.g. "help me", "I fell") that the main loop promotes directly to the emergency flow without passing through intent classification.

### memory/

`care_memory.py` — the central persistent store. Backed by a JSON file (`data/care_memory.json`). Holds scanned medicines, medication schedules, dose history, emergencies, events, wellbeing reports, briefings, and the patient profile. All writes are atomic (temp-file + rename) to avoid corruption on unexpected shutdown.

`memory_recall.py` — read-only query helpers over `CareMemory`. Used to surface specific slices of history without the caller needing to know the storage schema.

## Configuration

Set `ANTHROPIC_API_KEY` before running:

```bash
export ANTHROPIC_API_KEY=sk-...
python main.py
```

Or place it in a `.env` file at the repo root — `llm_client.py` loads it automatically.

## Running the assistant test

```bash
python assistant/test_llm_client.py   # requires ANTHROPIC_API_KEY
python assistant/memory/test_care_memory.py
```
