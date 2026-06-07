# behavior/

Elda's decision and scheduling layer — the high-level loops and state machines that determine what the robot does next.

## Purpose

Behavior modules consume data produced by `perception/` and `manipulation/`, query `assistant/memory/` for context, and decide which actions to take. They own the "what should the robot be doing right now?" question. No raw sensor data enters here; no LLM calls are made here (those belong in `assistant/`).

## Sub-modules

### patrol/

The robot's active monitoring mode. `patrol_mode.py` runs a continuous loop that reads camera frames, calls `perception/fall_detector.py` to check for falls, and manages the emergency confirmation flow via `emergency_state.py`.

- **Why a separate emergency state machine?** Confirming an emergency requires multiple consecutive detections to avoid false positives. `emergency_state.py` owns that logic independently so it can be unit-tested without a live camera.
- **How to trigger patrol mode:** Pass `--mode patrol` to `main.py`, or ask Elda verbally to switch.

### reminders/

`reminder_checker.py` runs as a background daemon thread. Every 30 seconds it reads active medication schedules from memory and fires a spoken alert (via TTS) when the current time matches a scheduled dose.

- **Why a daemon thread?** The reminder check must not block the main camera loop. A lightweight thread with a 30-second sleep cycle is sufficient for minute-level reminder accuracy.
- **Dependency:** Reads from `assistant/memory/care_memory.py`. If memory is empty, the checker runs silently.

### exploration/

`exploration_memory.py` maintains a spatial map of rooms and locations the robot has visited. Used by autonomous navigation routines to decide where to patrol next and to avoid revisiting the same room consecutively.

### health/

`health_check.py` provides a lightweight diagnostic ping — verifies that critical subsystems (camera, memory, LLM client) are reachable before a session starts. Run at startup or triggered via the `--health` CLI flag.

### summary/

Generates human-readable summaries built from the event log and memory.

| File | When it runs | Output |
|---|---|---|
| `daily_summary.py` | End of day, or on demand | Counts of scans, events, emergencies, and doses for the day |
| `morning_briefing.py` | Start of day, or on demand | Patient profile overview, today's schedule, and current wellbeing status |

### wellbeing/

A risk-scoring pipeline that observes long-term patterns in memory and flags concerns to caregivers. It does not diagnose — it surfaces signals.

```
wellbeing_signals.py   →  extract raw counts from memory (falls, missed doses, emergencies)
wellbeing_score.py     →  map signal counts to a 0-100 risk score and NORMAL / CAUTION / HIGH_RISK level
wellbeing_report.py    →  combine signals + score into a stored report, with optional LLM-generated summary
personal_baseline.py   →  compute a 14-day rolling baseline per patient so the score accounts for individual norms
```

To run the wellbeing tests:

```bash
python behavior/wellbeing/test_wellbeing_score.py
python behavior/wellbeing/test_wellbeing_signals.py
python behavior/wellbeing/test_wellbeing_report.py
python behavior/wellbeing/test_personal_baseline.py
```
