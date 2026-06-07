# HONESTY.md

> Mandatory disclosure for the hackathon. This file lives at the root of your repository. Judges cross-check it against your code and your technical video.
>
> **The deal:** disclosed shortcuts are **not** penalized — that is the entire point of this file. Hidden ones are. Undisclosed pre-built code is heavily penalized, each undisclosed mock carries a small penalty, and a faked demo is heavily penalized. Telling the truth here costs you nothing.

---

## 1. Team — who did what
Judges compare this against `git shortlog -sn`, so keep it honest.

| Member | GitHub handle | Main contributions |
|---|---|---|
| Myron Sydorov | Myron Sydorov | Majority of commits (~83): AI pipeline, module architecture, LLM integration, camera subsystems |
| Nyrok | Nyrok | ~11 commits *(fill in contributions)* |
| Raph1821 | Raph1821 | ~8 commits *(fill in contributions)* |
| goat | goat | ~5 commits *(fill in contributions)* |
| Hamza Konte | Hamza KONTE | ~2 commits *(fill in contributions)* |
| Minh Nhut Nguyen | Minh Nhut NGUYEN | ~2 commits *(fill in contributions)* |
| Gauthier BM | GauthierBM | ~1 commit *(fill in contributions)* |

*(Counts from `git shortlog -sn`; update handles/contributions to match your records.)*

---

## 2. What is fully working
Features that run end-to-end on the live app, with real data and real logic.

- **Medicine label scanning.** Camera frame → PaddleOCR text extraction → fuzzy name matching against `data/medicine_names.json` (rapidfuzz, 88% threshold) → `expiration_date_parser.py` extracts MM/YYYY → result stored in `data/care_memory.json`. Runs in a dedicated subprocess to avoid blocking the camera loop.
- **Fall detection.** MediaPipe Pose Landmarker (`pose_landmarker_lite.task`) estimates full-body landmarks on every frame → `fall_detector.py` classifies lying/fallen posture via joint-angle heuristics → `emergency_state.py` requires N consecutive positive frames before escalating, preventing single-frame false positives.
- **Patrol mode.** Continuous camera loop that invokes fall detection per frame, manages an emergency state machine, and fires a spoken alert + care memory event on confirmation.
- **LLM care assistant.** User question → `intents.py` keyword classifier → known intents are answered deterministically (no API call); unknown intents call the Claude API (`llm_client.py`) with a structured `[CareContext]` block assembled from live memory. Response spoken via TTS.
- **Medication reminders.** Background daemon thread polls active schedules every 30 s and fires a spoken TTS alert when current time matches a scheduled dose.
- **Persistent care memory.** `care_memory.py` maintains a JSON store (`data/care_memory.json`) for scanned medicines, schedules, dose history, events, emergencies, wellbeing reports, and patient profile. All writes are atomic (`os.replace`) to prevent corruption.
- **Wellbeing scoring pipeline.** `wellbeing_signals.py` counts falls, missed reminders, voice emergencies, and health concerns over a configurable window → `wellbeing_score.py` maps them to a 0–100 risk score with `NORMAL / CAUTION / HIGH_RISK` classification → `wellbeing_report.py` stores the report and optionally generates a natural-language summary via the LLM.
- **REST API server.** FastAPI server (`server/api_server.py`) exposes care memory read/write, the conversation endpoint, mode control, and a live JPEG camera frame stream.
- **Voice input (STT).** `speech_listener.py` uses `faster-whisper` running on-device (CPU) to transcribe microphone input. Emergency phrases bypass intent classification and go directly to the emergency flow.
- **Text-to-speech (TTS).** `tts_engine.py` uses the macOS `say` command via `subprocess`. Queued on a daemon thread so it never blocks the camera loop.
- **Morning briefing and daily summary.** `morning_briefing.py` and `daily_summary.py` assemble patient profile, today's schedule, and recent events → LLM-generated spoken summary; deterministic fallback when LLM is unavailable.
- **Health check.** Keyword detection flags symptom words in user responses; LLM generates a context-aware response using care memory; fallback text used if LLM unavailable.
- **Pill detection (YOLO).** `perception/pill_detect_yolo.py` runs a YOLOv8 ONNX model (`data/pills_yolov8.onnx`) on camera frames to count tablets and capsules by class.
- **Exploration memory.** CLIP embeddings (`assistant/memory/embedding.py`) stored while in Exploration Mode. Natural-language queries retrieve best-matching stored frames, passed to Claude Vision for description.

---

## 3. What is mocked, stubbed, or hardcoded
Every shortcut. **Anything you list here = free.**

| What is faked | Where (file:line or folder) | Why we mocked it | What the real version would do |
|---|---|---|---|
| **TTS uses macOS `say` command — not cross-platform.** | `assistant/speech/tts_engine.py:23` | Fast to integrate; works natively on macOS during the hackathon. | A cross-platform TTS service (e.g. Azure Cognitive Speech, Coqui TTS) that runs on Linux/Windows robot hardware. |
| **Demo dose recording (`D` key) is hardcoded to "Vitamin D, 1 tablet".** | `scripts/main.py:553` | Debug/demo shortcut for live presentation. | A proper dose confirmation UI where the carer selects which medicine was taken, based on what the robot just scanned. |
| **Sample schedule (`S` key) is hardcoded to "vitamin d, 09:00".** | `scripts/main.py:570` | Debug/demo shortcut. | Schedule management via the web dashboard or a voice command flow. |
| **`vision.pill_classifier.PillClassifier` is referenced but the module does not exist.** | `perception/realsense_pills.py:31` | The classifier was planned but not completed during the hackathon. | A trained classification model that identifies pill type and count from RealSense depth + RGB data. |
| **Health check intent uses simple string `in` matching, not NLP.** | `behavior/health/health_check.py` | Fast to ship; covers common phrases. Falls back to LLM for anything not matched. | Full intent classification via the LLM or a dedicated symptom-parsing model. |

---

## 4. External APIs, services & data sources

| Service / API / dataset | Used for | Real call or mocked? | Auth |
|---|---|---|---|
| **Anthropic Claude API** (`claude-haiku-4-5`) | LLM assistant responses, wellbeing summaries, morning briefings, health check replies, exploration descriptions | **Real call** | `ANTHROPIC_API_KEY` env var / `.env` file |
| MediaPipe Pose Landmarker (on-device) | Fall and lying-down detection from camera frames | **Real, runs locally** — no network call | none |
| PaddleOCR (on-device) | Medicine label text extraction | **Real, runs locally** — no network call | none |
| faster-whisper (on-device) | Speech-to-text transcription from microphone | **Real, runs locally** — no network call | none |
| YOLOv8 / Ultralytics ONNX (on-device) | Pill detection bounding boxes + count | **Real, runs locally** — no network call | none |
| CLIP via `transformers` / `onnxruntime` (on-device) | Semantic visual memory for Exploration Mode | **Real, runs locally** — no network call | none |

---

## 5. Pre-existing code

We started preparing ~4 days before the hackathon (first commit: 2026-06-02; bulk of pre-hackathon work: 2026-06-03 morning). During that preparation window:

- We found relevant open-source code and merged it into the repo (see table below).
- We built a simple, barely-working project skeleton — a webcam loop feeding frames to PaddleOCR for medicine label reading, with a basic state machine. This is the earliest form of what became `perception/` and `manipulation/`.
- We built a personal team presentation website (static, presentation only — no robot logic).

Everything else in the repo — fall detection, LLM assistant, reminders, care memory, wellbeing scoring, patrol mode, STT/TTS, FastAPI server, full webapp — was built during the hackathon itself (commits from 2026-06-03 afternoon through 2026-06-07).

| Item | Source | Roughly how much | License |
|---|---|---|---|
| Open-source code merged pre-hackathon | *(fill in: repo URL or description of the OSS project)* | *(fill in: e.g. ~N files / the full X module)* | *(fill in: license)* |
| Initial medicine OCR skeleton | Built by our team pre-hackathon | ~3 files: webcam loop, name parser, expiration parser | — |
| Team presentation website | Built by our team pre-hackathon (static, no robot logic) | Minimal — presentation only | — |
| Python AI libraries (PaddleOCR, MediaPipe, ultralytics, faster-whisper, etc.) | Standard open-source packages, pip-installed | Libraries only — no code copied | various OSS |

---

## 6. Known limitations & next steps

- **TTS is macOS-only.** The `say` command does not exist on Linux or Windows. A cross-platform TTS library is needed for deployment on the robot's onboard computer.
- **`vision.pill_classifier` module is missing.** `perception/realsense_pills.py` references it but it was not completed. RealSense-based pill classification will fail at import on that file.
- **No API authentication on the care server.** `server/api_server.py` has no auth layer — any client on the local network can read and write care memory.
- **Care memory is a flat JSON file.** Suitable for a single-patient prototype; not suitable for multi-patient or concurrent-write scenarios.
- **No physical arm control for medication dispensing.** The `manipulation/` module handles classification and counting; actual pick-and-place commands are not wired up.
- **Exploration Mode requires heavy optional dependencies.** `torch` + `transformers` (or `onnxruntime`) must be installed separately.
- **Wellbeing baseline needs historical data.** `personal_baseline.py` computes a 14-day rolling average; with a fresh memory store the baseline is `None` and the score uses population-level defaults.
