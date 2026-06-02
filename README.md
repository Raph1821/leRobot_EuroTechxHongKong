# CareBot AI — Medicine Scanner

Live camera demo that detects a medicine object, reads its label via OCR,
and extracts two required fields: **medicine name** and **expiration date**.

Designed for demo use now and future integration with a robotic arm that
sorts medicines into bins.

---

## Project structure

```
ai/
├── vision/
│   ├── webcam_medicine_scanner.py   ← main entry point
│   ├── medicine_object_detector.py  ← YOLO + contour object detection
│   └── camera_utils.py
│
├── ocr/
│   ├── paddle_ocr_reader.py         ← PaddleOCR wrapper
│   ├── medicine_text_parser.py      ← fuzzy name matching
│   └── expiration_date_parser.py    ← robust date extraction
│
├── scanner/
│   └── medicine_scan_state.py       ← multi-frame state accumulator
│
├── data/
│   └── medicine_names.json          ← 200 + medicine/supplement names
│
└── sorting/
    └── virtual_sorter.py            ← bin assignment logic
```

---

## Setup

### 1. Create a virtual environment (Python 3.11+)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **First run note:** PaddleOCR automatically downloads its English model
> (~100 MB) on first use.  An internet connection is required for that
> initial download.

### 3. Optional — YOLO object detection

YOLO improves detection of bottles and boxy containers.  Without it the
scanner uses contour-based detection (works well when the package is
clearly visible against a plain background).

```bash
pip install ultralytics
```

---

## macOS camera permissions

macOS requires explicit camera permission for each application.

1. Open **System Settings → Privacy & Security → Camera**.
2. Enable access for **Terminal** (or your IDE / Python launcher).
3. If the window opens but shows a black frame, revoke and re-grant the
   permission, then restart the terminal.

---

## Run

```bash
python ai/vision/webcam_medicine_scanner.py
```

Use a different camera (e.g. external USB webcam at index 1):

```bash
python ai/vision/webcam_medicine_scanner.py --camera 1
```

---

## Keyboard controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `s` | Force OCR scan of the current frame |
| `r` | Reset — discard current medicine and start over |
| `n` | Next medicine — **only allowed when both name and EXP date are found** |
| `p` | Print accumulated OCR candidates and debug state to terminal |

If you press `n` before both fields are confirmed:

```
Cannot move to next medicine yet. Missing: medicine_name / expiration_date
```

---

## Output format

Once both fields are found the terminal prints:

```
================ MEDICINE SCAN ================
Medicine name:      Vitamin D
Expiration date:    09/2026

Status:             valid
Sort category:      valid_medicine
Recommended action: place_in_bin_A
Ready for sorting:  yes
===============================================
```

---

## Demo instructions

1. Hold one medicine package or bottle clearly in front of the camera.
2. Rotate it slowly until the brand name and expiration date are visible.
3. Keep it steady — OCR runs approximately every 1 second.
4. Wait until the overlay shows **READY FOR SORTING**.
5. Press **`n`** to confirm and scan the next medicine.

**Tips for best results:**
- Use good lighting — avoid harsh shadows across the label.
- Keep the package centred in the frame, about 30–50 cm from the camera.
- If scanning is slow, press **`s`** to force an immediate OCR pass.

---

## Sorting logic

| Condition | Status | Bin |
|-----------|--------|-----|
| Name or EXP date missing | unknown | keep scanning |
| EXP date in the future | valid | Bin A |
| EXP date in the past | expired | Bin B |

---

## Future: robotic arm integration

`virtual_sorter.py` returns a `SortResult` dataclass with `status`,
`sort_category`, and `recommended_action`.  The robotic arm controller
can import `sort_medicine()` and act on `recommended_action` directly
without changes to the scanner logic.
