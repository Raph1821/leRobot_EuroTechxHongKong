# HONESTY.md

> Mandatory disclosure for the hackathon. This file lives at the root of your repository. Judges cross-check it against your code and your technical video.
>
> **The deal:** disclosed shortcuts are **not** penalized — that is the entire point of this file. Hidden ones are. Undisclosed pre-built code is heavily penalized, each undisclosed mock carries a small penalty, and a faked demo is heavily penalized. Telling the truth here costs you nothing.

---

## 1. Team — who did what
Judges compare this against `git shortlog -sn`, so keep it honest.

| Member | GitHub handle | Main contributions |
|---|---|---|
| Myron Sydorov | Myron Sydorov | Majority of commits (~83): AI pipeline, web-control backend/frontend, teleop, camera, module restructure |
| Nyrok | Nyrok | ~11 commits *(fill in contributions)* |
| Raph1821 | Raph1821 | ~8 commits *(fill in contributions)* |
| goat | goat | ~5 commits *(fill in contributions)* |
| Hamza Konte | Hamza KONTE | ~2 commits *(fill in contributions)* |
| Minh Nhut Nguyen | Minh Nhut NGUYEN | ~2 commits (orchestrator `minh/`) |
| Gauthier BM | GauthierBM | ~1 commit *(fill in contributions)* |

*(Counts from `git shortlog -sn`; update handles/contributions to match your records.)*

---

## 2. What is fully working
Features that run end-to-end on the live app, with real data and real logic. Be specific: name the feature, what input it takes, what output it produces.

### Elda AI care assistant (`perception/`, `behavior/`, `assistant/`, `manipulation/`, `server/`)

- **Medicine label scanning.** Camera frame → PaddleOCR text extraction → fuzzy name matching against `data/medicine_names.json` (rapidfuzz, 88% threshold) → `expiration_date_parser.py` extracts MM/YYYY → result stored in `data/care_memory.json`. Runs in a dedicated subprocess to avoid blocking the camera loop.
- **Fall detection.** MediaPipe Pose Landmarker (`pose_landmarker_lite.task`) estimates full-body landmarks on every frame → `fall_detector.py` classifies lying/fallen posture via joint-angle heuristics → `emergency_state.py` requires N consecutive positive frames before escalating, preventing single-frame false positives.
- **Patrol mode.** Continuous camera loop that invokes fall detection per frame, manages an emergency state machine, and can call back into the assistant system (spoken alert + care memory event).
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

### Robot arm web-control stack (`so_arm_100_web_bridge/`, `webapp/`)

- **Browser → robot joint control (real ROS2).** Moving a joint slider in the web UI
  (`webapp/components/ControlPanel.tsx`) sends a `joint_command` over WebSocket
  (`webapp/lib/jointStore.tsx:186`). The bridge validates it against URDF limits and
  publishes a real `JointTrajectory` to `/arm_controller/joint_trajectory`
  (`so_arm_100_web_bridge/.../websocket_bridge_node.py:615`). This is genuine ROS2
  integration, not a mock. **Verified on real SO-101 hardware.**
- **Gripper control.** `gripper_command` messages drive a real `GripperCommand` action
  on the controller.
- **Live joint-state feedback at ~30 Hz.** The bridge subscribes to `/joint_states` and
  broadcasts `joint_state` JSON to all clients; the 3D viewer
  (`webapp/components/RobotViewer.tsx`) follows live hardware feedback when the bridge is
  online, and falls back to commanded values when offline (`jointStore.tsx:280`).
- **Cartesian / IK goals.** `cartesian_goal` messages call the real ROS2 `/compute_ik`
  service (MoveIt) and, on success, publish the resulting trajectory
  (`so_arm_100_web_bridge/.../cartesian_controller.py`). Workspace bounds are enforced
  before the IK call.
- **Camera streaming.** The bridge subscribes to a real `sensor_msgs/Image` topic,
  JPEG-compresses with OpenCV, base64-encodes, and streams `camera_frame` messages with a
  drop-oldest queue (`camera_stream_handler.py`). Shown in the UI.
- **Auto-reconnect WebSocket client.** Frontend reconnects every 2 s if the bridge drops
  (`jointStore.tsx:96`), and the whole UI degrades gracefully (works offline, commands no-op).
- **Three control modes in the UI** (`webapp/components/ManualControl.tsx`): Manual joint
  sliders, Simulator diagnostics, and Teleop (keyboard + cartesian + episode recorder tabs).

---

## 3. What is mocked, stubbed, or hardcoded
Every shortcut. Examples: a login that accepts any password, a payment that always succeeds, an "AI" that is an if/else, a database that is an in-memory dictionary, fake JSON returned instead of a real API call.

**Undisclosed mocks carry a small penalty each. Anything you list here = free.**

| What is faked | Where (file:line or folder) | Why we mocked it | What the real version would do |
|---|---|---|---|
| **TTS uses macOS `say` command — not cross-platform.** | `assistant/speech/tts_engine.py:23` | Fast to integrate; works natively on macOS during the hackathon. | A cross-platform TTS service (e.g. Azure Cognitive Speech, Coqui TTS) that runs on Linux/Windows robot hardware. |
| **Demo dose recording (`D` key) is hardcoded to "Vitamin D, 1 tablet".** | `scripts/main.py:553` | Debug/demo shortcut for live presentation. | A proper dose confirmation UI where the carer selects which medicine was taken, based on what the robot just scanned. |
| **Sample schedule (`S` key) is hardcoded to "vitamin d, 09:00".** | `scripts/main.py:570` | Debug/demo shortcut. | Schedule management via the web dashboard or a voice command flow. |
| **`vision.pill_classifier.PillClassifier` is referenced but the module does not exist.** | `perception/realsense_pills.py:31` | The classifier was planned but not completed during the hackathon. | A trained classification model that identifies pill type and count from RealSense depth + RGB data. |
| **Health check intent uses simple string `in` matching, not NLP.** | `behavior/health/health_check.py` | Fast to ship; covers the common phrases. Falls back to LLM for anything not matched. | Full intent classification via the LLM or a dedicated symptom-parsing model. |
| **Teleop velocity → joint velocity uses a hand-tuned approximation, NOT a real Jacobian inverse.** Fixed coefficients (e.g. `shoulder_rotation_vel = -vx * 2.0`) map Cartesian velocity to joints. | `so_arm_100_web_bridge/.../teleop_handler.py:239-300` (docstring admits it at line 251-254) | A full Jacobian-inverse at runtime was out of scope for the hackathon; the approximation is "good enough" for keyboard jogging. | Query the IK/Jacobian at the current joint configuration each tick and solve `q̇ = J⁺ · ẋ` with singularity handling. |
| **Mock bridge for frontend-only dev.** A dependency-free Node WebSocket server that fakes `joint_state` + a synthetic PNG `camera_frame`. | `webapp/scripts/mock-bridge.mjs` (run via `npm run mock-bridge`) | Lets us build/test the web UI on a laptop with no ROS2 / no arm. **Not used in the hardware demo.** | N/A — it is intentionally a stand-in for the real ROS2 bridge. |
| **DH link lengths for forward kinematics are approximate hardcoded constants.** | `cartesian_controller.py:42-47` (`_LINK_LENGTHS`) | We used rough measured link lengths instead of pulling exact values from the URDF. | Read precise kinematic params from the SO-101 URDF / MoveIt config. |
| Episode recording/replay depends on external `episode_recorder` ROS2 services being up. | `episode_handler.py:71-89` | We wired the protocol but did not validate full record→replay on hardware during the event. | End-to-end tested rosbag2 MCAP record + replay on the live arm. |

---

## 4. External APIs, services & data sources
Everything the project calls or pretends to call. Mark each as real or mocked.

| Service / API / dataset | Used for | Real call or mocked? | Auth (sandbox / test key / none) |
|---|---|---|---|
| **Anthropic Claude API** (`claude-haiku-4-5`) | LLM assistant responses, wellbeing summaries, morning briefings, health check replies, exploration descriptions | **Real call** | `ANTHROPIC_API_KEY` env var / `.env` file |
| MediaPipe Pose Landmarker (on-device) | Fall and lying-down detection from camera frames | **Real, runs locally** — no network call | none |
| PaddleOCR (on-device) | Medicine label text extraction | **Real, runs locally** — no network call | none |
| faster-whisper (on-device) | Speech-to-text transcription from microphone | **Real, runs locally** — no network call | none |
| YOLOv8 / Ultralytics ONNX (on-device) | Pill detection bounding boxes + count | **Real, runs locally** — no network call | none |
| CLIP via `transformers` / `onnxruntime` (on-device) | Semantic visual memory for Exploration Mode | **Real, runs locally** — no network call | none |
| ROS2 `/arm_controller/joint_trajectory` (topic) | Sending joint/teleop commands to the arm | **Real** | none (local DDS) |
| ROS2 `/joint_states` (topic) | Live robot feedback at ~30 Hz | **Real** | none |
| ROS2 `/compute_ik` (MoveIt service) | Cartesian goal IK | **Real** (when MoveIt is launched) | none |
| ROS2 `/viewport_camera/image_raw` (Image topic) | Camera stream to browser | **Real** (from camera/sim) | none |
| `episode_recorder` ROS2 services | Record/replay episodes | **Real protocol**, not fully demoed on HW | none |
| WebSocket `ws://localhost:9090` | Browser ↔ bridge transport | **Real** | none |

---

## 5. Pre-existing code
Anything written **before** kickoff that we brought into this project: prior personal projects, forked open-source code, templates, boilerplate, internal libraries.

**Undisclosed pre-built code is heavily penalized. Anything you list here = free.**

| Item | Source (URL or description) | Roughly how much | License |
|---|---|---|---|
| SO-101 / SO-ARM-100 URDF, meshes, MoveIt + bringup configs | TheRobotStudio / community SO-ARM-100 robot description (adapted) | Several ROS2 packages (`so101_description`, `so101_moveit_config`, etc.) | Apache-2.0 (see repo LICENSE) |
| Next.js project scaffold | `create-next-app` boilerplate | Standard app skeleton in `webapp/` | MIT |
| Three.js / React-Three-Fiber / drei / `urdf-loader` | npm packages for the 3D viewer | Libraries only (not our code) | MIT |
| ROS2 `rclpy`, `websockets`, OpenCV, MoveIt | Standard robotics/Python libs | Libraries only | various OSS |

*The application/glue logic in `so_arm_100_web_bridge/` and `webapp/` (bridge protocol, handlers, control UI, jointStore) was written during the hackathon window (commits 2026-06-02 → 2026-06-07).*

---

## 6. Known limitations & next steps
What we would build next, and the weak spots we already know about. Naming these honestly is a strength, not a flaw.

**Elda AI care assistant:**
- **TTS is macOS-only.** The `say` command does not exist on Linux or Windows. A cross-platform TTS library is needed for deployment on the robot's onboard computer.
- **`vision.pill_classifier` module is missing.** `perception/realsense_pills.py` references it but it was not completed. RealSense-based pill classification will fail at import time on that file.
- **No API authentication on the care server.** `server/api_server.py` has no auth layer — any client on the local network can read and write care memory.
- **Care memory is a flat JSON file.** Suitable for a single-patient prototype; not suitable for multi-patient or concurrent-write scenarios.
- **No physical arm control for medication dispensing.** The `manipulation/` module handles classification and counting; actual pick-and-place commands are not wired up.
- **Exploration Mode requires heavy optional dependencies.** `torch` + `transformers` (or `onnxruntime`) must be installed separately.
- **Wellbeing baseline needs historical data.** `personal_baseline.py` computes a 14-day rolling average; with a fresh memory store the baseline is `None` and the score uses population-level defaults.

**Robot arm web-control stack:**
- **Teleop jogging is approximate, not kinematically exact** (see §3). It is usable for
  nudging the arm but can behave oddly near singularities; replace with a true Jacobian-inverse.
- **No authentication / authorization on the bridge.** Anyone who can reach `ws://…:9090`
  can drive the arm. Needs auth + an e-stop and command rate-limiting before any non-lab use.
- **IK/MoveIt is a hard dependency for Cartesian mode** — if `/compute_ik` isn't launched,
  Cartesian goals fail (the UI surfaces the error, but the feature is unavailable).
- **Episode record/replay** is protocol-complete but was not validated end-to-end on the
  physical arm during the event.
- **Connection-status surfacing is partial** — the store tracks `online/offline/connecting`
  but not all pages display it prominently.
- **No collision checking / soft limits beyond URDF joint limits** for streamed commands.
