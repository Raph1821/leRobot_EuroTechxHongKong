# data/

Static assets required at runtime — reference data that ships with the repository and does not change during a session.

## Purpose

Separating static data from code makes it easy to update medicine lists, swap ML model files, or inspect reference configs without touching any Python. Files here are read-only at runtime; Elda never writes back to this directory.

## Files

### medicine_names.json

The canonical list of medicine names that `manipulation/sorting/medicine_name_parser.py` matches OCR output against. To add a new medicine to Elda's recognition vocabulary, add its name (and common misspellings) to this file — no code changes required.

Format: a JSON array of lowercase strings.

### pose_landmarker_lite.task

The MediaPipe Pose Landmarker model file used by `perception/fall_detector.py` and `behavior/patrol/patrol_mode.py` to estimate full-body pose from camera frames. This is the "lite" variant — lower accuracy than the full model but fast enough to run at real-time frame rates on CPU. If you need higher accuracy, replace this file with the full model and update the path reference in `patrol_mode.py`.

### test_doses_api.json

Example medication schedule payload for testing the `/doses` API endpoint without a live database. Used by `server/api_server.py` integration tests and during local development when a real patient profile is not available.

## What does NOT belong here

- Runtime-generated files (`care_memory.json`, logs, session state) — these live outside the repo
- Trained model weights that are too large for git — use `git lfs` or a model registry
- Environment-specific configuration — use `.env` files or environment variables
