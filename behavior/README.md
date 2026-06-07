# behavior/

High-level robot behaviors and state machines.

## What belongs here

- Patrol mode and emergency response (`patrol/`)
- Medication reminder scheduler (`reminders/`)
- Spatial exploration memory (`exploration/`)
- Health monitoring (`health/`)
- Daily summaries and morning briefing (`summary/`)
- Wellbeing scoring and reporting (`wellbeing/`)

## Sub-modules

| Module | Purpose |
|---|---|
| `patrol/patrol_mode.py` | Pose-based patrol loop with fall/emergency detection |
| `patrol/emergency_state.py` | Emergency confirmation state machine |
| `reminders/reminder_checker.py` | Background thread for medication reminder alerts |
| `exploration/exploration_memory.py` | Map of explored locations for autonomous navigation |
| `health/health_check.py` | Lightweight health status checks |
| `summary/daily_summary.py` | End-of-day event summary generation |
| `summary/morning_briefing.py` | Morning status briefing |
| `wellbeing/wellbeing_signals.py` | Extract wellbeing signals from memory |
| `wellbeing/wellbeing_score.py` | Score and classify risk level |
| `wellbeing/wellbeing_report.py` | Generate a full wellbeing report |
| `wellbeing/personal_baseline.py` | Compute and store individual baseline metrics |
