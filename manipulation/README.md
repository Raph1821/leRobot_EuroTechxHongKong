# Manipulation

> The physical reasoning layer of Elda — algorithms that classify, measure, and act on objects the robot has perceived.

---

## Overview

`manipulation/` sits between perception and behavior. Where `perception/` answers *"what is in the frame?"*, manipulation answers *"what exactly is it, is it safe, and how many are there?"*

This module receives already-extracted data — OCR text, bounding boxes, depth measurements — and produces clean, typed results that the rest of the system can act on. It contains no camera code, no LLM calls, and no behavioral decisions.

---

## Components

### `sorting/` — Medicine Scanning Pipeline

The core pipeline for Sorting Mode, processing raw OCR output into structured medicine records.

| File | Responsibility |
|---|---|
| `expiration_date_parser.py` | Extracts and normalises expiration dates from raw OCR strings using regex and fuzzy date matching |
| `medicine_name_parser.py` | Matches OCR text against the canonical medicine list in `data/medicine_names.json` to produce a verified medicine name |
| `scan_state.py` | State machine coordinating a full scan cycle: `WAITING → READING → CONFIRMED → DONE`. Drives when OCR is triggered and when a result is accepted |

### `dosage_counter.py`

Counts visible pills in a pre-captured image using contour detection. Returns an integer count used to cross-check what is physically present against the expected dose in the patient's schedule.

---

## Data Flow

```
Camera frame
    └─▶  perception/pill_detect_yolo.py
              └─▶  manipulation/sorting/scan_state.py   (triggers OCR)
                        ├─▶  expiration_date_parser.py  →  "MM/YYYY"
                        └─▶  medicine_name_parser.py    →  "Paracetamol"
                                  └─▶  assistant/memory/care_memory.py  (stored)
```

---

## Architecture Boundaries

**Imports allowed into this module:**
- Standard library
- `data/` (static reference files)

**Never import from:**
- `behavior/` — no decisions made here
- `assistant/` — no LLM calls here
- `perception/` — receives extracted data, not raw frames

---

## Extending This Module

Future capabilities that belong here:

- **Pick-and-place controllers** — trajectory planning and arm command generation
- **Grasping helpers** — grasp point estimation from depth maps
- **Arm control interfaces** — wrappers around robot arm APIs

Each new capability should accept structured inputs and return structured outputs. It must remain self-contained and testable without a live robot.
