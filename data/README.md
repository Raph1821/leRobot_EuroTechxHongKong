# Data

> Static assets bundled with the repository — reference files that Elda reads at runtime but never writes to.

---

## Overview

`data/` holds the static, version-controlled files that the system needs to function: ML model weights, reference vocabularies, and example fixtures. Keeping them here, separate from code, means they can be updated, reviewed, or replaced without modifying any Python.

**Elda never writes to this directory at runtime.** Runtime state — the patient's care memory, session logs, generated reports — is stored outside the repository at the path configured in `assistant/memory/care_memory.py` (default: `data/care_memory.json`, which is gitignored).

---

## Files

### `medicine_names.json`

The canonical vocabulary used by `manipulation/sorting/medicine_name_parser.py` to match OCR output against known medicine names.

**Format:** a JSON array of lowercase strings, one entry per recognised medicine name.

**To add a new medicine:** append its name (and common OCR misspellings) to this file. No code changes are required — the parser loads the list on startup.

---

### `pose_landmarker_lite.task`

The MediaPipe Pose Landmarker model file consumed by `perception/fall_detector.py` and `behavior/patrol/patrol_mode.py` to estimate full-body pose from a camera frame.

This is the **lite** variant of the model — optimised for real-time inference on CPU at the cost of some accuracy. If higher precision is required (e.g. for research or clinical validation), replace this file with the full model and update the `_MODEL_PATH` constant in `behavior/patrol/patrol_mode.py`.

| Variant | Accuracy | Latency | Use case |
|---|---|---|---|
| Lite *(current)* | Good | Low | Real-time patrol on embedded hardware |
| Full | High | Higher | Offline analysis, validation |

---

### `test_doses_api.json`

A sample medication schedule payload used for testing the `/doses` API endpoint and developing against the server without a live patient profile. Follows the same schema as a real schedule stored in `care_memory.json`.

---

## What Does Not Belong Here

| Item | Where it goes instead |
|---|---|
| Runtime care memory (`care_memory.json`) | Outside the repo — path set via environment or defaults |
| Session logs and generated reports | Outside the repo |
| Large model weights (> a few MB) | Git LFS or an external model registry |
| Environment-specific configuration | `.env` file at the repository root |
