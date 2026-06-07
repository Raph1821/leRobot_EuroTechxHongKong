# Scripts

> Runnable entry points for the Elda robot system.

---

## `main.py` — Robot Runtime

The primary application loop. Initialises all subsystems and runs the robot in one of four operating modes, switchable at runtime via keyboard or voice.

### Modes

| Key | Mode | What Elda does |
|---|---|---|
| `1` | **Sorting** | Reads medicine labels via OCR, parses name and expiration date, stores to memory |
| `2` | **Patrol** | Monitors the room via camera, detects falls, manages emergency confirmation |
| `3` | **Dosage** | Uses the RealSense depth camera to count pills and verify doses *(requires `--realsense`)* |
| `4` | **Exploration** | Builds a CLIP visual memory of the environment for natural-language object search |

### Usage

```bash
# Single camera (uses the same camera for sorting and patrol)
python scripts/main.py

# Two cameras: index 1 for OCR, index 2 for patrol/fall detection
python scripts/main.py --ocr-camera 1 --patrol-camera 2

# Enable RealSense dosage mode with expected pill count verification
python scripts/main.py --realsense --expected-pills 3

# Rotate the wrist camera to correct its physical mounting (default: 270°)
python scripts/main.py --patrol-camera 2 --patrol-rotate 90
```

### Full argument reference

| Argument | Default | Description |
|---|---|---|
| `--ocr-camera` | `1` | Camera index for medicine scanning |
| `--patrol-camera` | *(same as OCR)* | Camera index for patrol and fall detection |
| `--realsense` | off | Enable RealSense depth camera for dosage mode |
| `--expected-pills` | *(none)* | Verify pill count against this number in dosage mode |
| `--patrol-rotate` | `270` | Rotate the patrol camera frame to correct mounting (0/90/180/270) |

### Keyboard shortcuts

| Key | Action |
|---|---|
| `a` | Ask Elda a question |
| `f` | Find an object from exploration memory |
| `B` | Generate morning briefing |
| `Y` | Generate daily care summary |
| `H` | Health check |
| `M` | View medicine schedules |
| `m` | View memory stats |
| `P` | View and edit patient profile |
| `R` | Trigger reminder check now |
| `D` / `X` | Record a dose / view dose history |
| `T` | Speaker test |
| `d` | Toggle debug output |
| `r` | Reset current scan or patrol state |
| `q` | Quit |
