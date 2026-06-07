# Behavior

> The decision and scheduling layer of Elda — high-level loops and state machines that determine what the robot does next.

---

## Overview

`behavior/` is where Elda decides what to do. It consumes structured outputs from `perception/` and `manipulation/`, reads long-term context from `assistant/memory/`, and translates those inputs into robot actions — patrolling a room, speaking a medication reminder, or generating a care report.

**This layer owns no sensors and calls no LLMs.** Sensor access belongs in `perception/`; language model calls belong in `assistant/`. Keeping that boundary clean means every behavior module can be unit-tested with mock inputs, without hardware or API keys.

---

## Sub-modules

### `patrol/` — Active Monitoring

Elda's primary safety loop. `patrol_mode.py` runs continuously, reading camera frames and calling `perception/fall_detector.py` on each one. When a potential fall is detected, `emergency_state.py` applies a multi-detection confirmation window before escalating — preventing false positives from a single bad frame.

| File | Role |
|---|---|
| `patrol_mode.py` | Main patrol loop: captures frames, invokes fall detection, manages mode transitions |
| `emergency_state.py` | Confirmation state machine: requires N consecutive detections before declaring an emergency |

**To activate patrol mode:**
```bash
python main.py --mode patrol
# or ask Elda verbally: "Start patrol mode"
```

---

### `reminders/` — Medication Scheduling

`reminder_checker.py` runs as a background daemon thread. Every 30 seconds it reads active medication schedules from memory and fires a spoken alert via TTS when the current time matches a scheduled dose time.

A daemon thread is used so the reminder loop never blocks the main camera process. Minute-level accuracy is sufficient for medication reminders, making a 30-second polling interval the right trade-off between responsiveness and CPU usage.

**Dependency:** Reads from `assistant/memory/care_memory.py`. If no schedules are stored, the checker runs silently.

---

### `exploration/` — Spatial Memory

`exploration_memory.py` maintains a map of rooms and locations Elda has visited. Autonomous navigation routines use this to prioritise unvisited areas during a patrol sweep and avoid circling the same room repeatedly.

---

### `health/` — System Diagnostics

`health_check.py` verifies that all critical subsystems — camera, memory store, LLM client — are reachable before a session begins. Run at startup or on demand via the `--health` flag.

```bash
python main.py --health
```

---

### `summary/` — Briefings and Reports

Generates natural language summaries from the event log and care memory.

| File | Trigger | Content |
|---|---|---|
| `daily_summary.py` | End of day or on demand | Total scans, events, emergencies, and doses for the day |
| `morning_briefing.py` | Start of day or on demand | Patient profile, today's medication schedule, current wellbeing status |

---

### `wellbeing/` — Risk Scoring Pipeline

A longitudinal monitoring pipeline that surfaces care signals to caregivers. It does not diagnose — it measures observable patterns against an individual baseline and produces a scored risk assessment.

```
wellbeing_signals.py    Extract raw counts from memory
                        (falls, missed doses, voice emergencies, health concerns)
        │
        ▼
wellbeing_score.py      Map signal counts to a 0–100 risk score
                        Risk level: NORMAL · CAUTION · HIGH_RISK
        │
        ▼
wellbeing_report.py     Combine signals and score into a stored report
                        Optional: LLM-generated natural language summary
        │
        ▼
personal_baseline.py    14-day rolling baseline per patient
                        Scores are relative to the individual, not a population average
```

**Running the wellbeing tests:**

```bash
python behavior/wellbeing/test_wellbeing_score.py
python behavior/wellbeing/test_wellbeing_signals.py
python behavior/wellbeing/test_wellbeing_report.py
python behavior/wellbeing/test_personal_baseline.py
```

---

## Architecture Boundaries

| Allowed | Not Allowed |
|---|---|
| Import from `perception/` (read results) | Open camera streams or process raw frames |
| Import from `manipulation/` (read results) | Call the Claude API directly |
| Read from `assistant/memory/` | Write to memory outside of designated helpers |
| Call `assistant/speech/` for TTS output | Contain ML model inference |
