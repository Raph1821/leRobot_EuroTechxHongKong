# manipulation/

Robot manipulation tasks: sorting, pick-and-place, dosage handling.

## What belongs here

- Medicine sorting (`sorting/`)
- Dosage counting (`dosage_counter.py`)
- Pick-and-place controllers
- Grasping helpers
- Arm control interfaces

## Modules

| Module | Purpose |
|---|---|
| `sorting/expiration_date_parser.py` | Parse expiration dates from OCR text |
| `sorting/medicine_name_parser.py` | Match OCR text against known medicine names |
| `sorting/scan_state.py` | State machine for the scan-and-sort flow |
| `dosage_counter.py` | Count pills in a frame using computer vision |
