# manipulation/

Elda's physical interaction layer — algorithms that turn perceived objects into structured decisions about what to do with them.

## Purpose

Manipulation bridges perception and behavior. Perception answers "what is there?"; manipulation answers "what is it, is it safe to use, and how many are there?". This module should contain no camera code and no LLM calls — it receives already-extracted data (OCR text, bounding boxes, depth values) and produces clean structured results.

## Contents

### sorting/

The medicine scanning and classification pipeline. Used during Sorting Mode when the robot reads medicine labels and assesses their status.

| File | What it does | Why it is here |
|---|---|---|
| `expiration_date_parser.py` | Extracts expiration dates from raw OCR strings using regex and fuzzy matching | Pure text transformation — no camera, no LLM |
| `medicine_name_parser.py` | Matches OCR output against `data/medicine_names.json` to identify the medicine | Deterministic lookup, belongs at the data-processing layer |
| `scan_state.py` | State machine that coordinates a full scan cycle: waiting → reading → confirmed → done | Orchestrates the sorting flow without owning any I/O |

### dosage_counter.py

Counts the number of pills visible in a frame using contour detection. Takes a pre-captured image (not a live stream) and returns an integer count. Used to cross-check expected doses against what is physically present.

## How the sorting pipeline fits together

```
Camera frame
    └── perception/pill_detect_yolo.py  →  bounding boxes
            └── manipulation/sorting/scan_state.py  →  triggers OCR
                    ├── expiration_date_parser.py  →  date string
                    └── medicine_name_parser.py    →  medicine name
                            └── assistant/memory/care_memory.py  →  stored
```

## Adding new manipulation capabilities

Pick-and-place controllers, grasping helpers, and arm trajectory planners belong here when they are implemented. Each capability should be a self-contained module that accepts structured inputs and returns structured outputs — it must not import from `behavior/` or `assistant/`.
