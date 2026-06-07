# Carebot AI

Live webcam feed — milestone 1.

## Setup

**Requirements:** Python 3.11+

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
python ai/main.py
```

Press `q` to quit.

## macOS camera permission

The first time you run the program, macOS will prompt for camera access. Click **OK**.

If the prompt does not appear and the camera fails to open, go to:

**System Settings → Privacy & Security → Camera**

and enable access for your terminal application (Terminal, iTerm2, etc.).
