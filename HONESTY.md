# HONESTY.md

> Mandatory disclosure for the hackathon. This file lives at the root of your repository. Judges cross-check it against your code and your technical video.
>
> **The deal:** disclosed shortcuts are **not** penalized — that is the entire point of this file. Hidden ones are. Undisclosed pre-built code is heavily penalized, each undisclosed mock carries a small penalty, and a faked demo is heavily penalized. Telling the truth here costs you nothing.

> **Scope of this disclosure:** this file focuses on the **robot web-control stack** — the
> backend WebSocket bridge (`so_arm_100_web_bridge/`) and the web frontend (`webapp/`) that
> together let you drive the SO-101 arm from the browser. Other modules in the repo
> (`ai/`, `interaction/`, `minh/`) are summarised at a higher level.

---

## 1. Team — who did what
Judges compare this against `git shortlog -sn`, so keep it honest.

| Member | GitHub handle | Main contributions |
|---|---|---|
| Myron Sydorov | Myron Sydorov | Majority of commits (~68): web-control backend/frontend, teleop, camera, control UI |
| Nyrok | Nyrok | ~11 commits |
| Raph1821 | Raph1821 | ~8 commits |
| goat | goat | ~3 commits |
| Hamza Konte | Hamza KONTE | ~2 commits |
| Minh Nhut Nguyen | Minh Nhut NGUYEN | ~2 commits (orchestrator `minh/`) |
| Gauthier BM | GauthierBM | ~1 commit |

*(Counts from `git shortlog -sn`; update handles/contributions to match your records.)*

---

## 2. What is fully working
Features that run end-to-end on the live app, with real data and real logic. Be specific: name the feature, what input it takes, what output it produces.

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
| **Teleop velocity → joint velocity uses a hand-tuned approximation, NOT a real Jacobian inverse.** Fixed coefficients (e.g. `shoulder_rotation_vel = -vx * 2.0`) map Cartesian velocity to joints. | `so_arm_100_web_bridge/.../teleop_handler.py:239-300` (docstring admits it at line 251-254) | A full Jacobian-inverse at runtime was out of scope for the hackathon; the approximation is "good enough" for keyboard jogging. | Query the IK/Jacobian at the current joint configuration each tick and solve `q̇ = J⁺ · ẋ` with singularity handling. |
| **Mock bridge for frontend-only dev.** A dependency-free Node WebSocket server that fakes `joint_state` + a synthetic PNG `camera_frame`. | `webapp/scripts/mock-bridge.mjs` (run via `npm run mock-bridge`) | Lets us build/test the web UI on a laptop with no ROS2 / no arm. **Not used in the hardware demo.** | N/A — it is intentionally a stand-in for the real ROS2 bridge. |
| **DH link lengths for forward kinematics are approximate hardcoded constants.** | `cartesian_controller.py:42-47` (`_LINK_LENGTHS`) | We used rough measured link lengths instead of pulling exact values from the URDF. | Read precise kinematic params from the SO-101 URDF / MoveIt config. |
| Episode recording/replay depends on external `episode_recorder` ROS2 services being up. | `episode_handler.py:71-89` | We wired the protocol but did not validate full record→replay on hardware during the event. | End-to-end tested rosbag2 MCAP record + replay on the live arm. |

---

## 4. External APIs, services & data sources
Everything the project calls or pretends to call. Mark each as real or mocked.

| Service / API / dataset | Used for | Real call or mocked? | Auth (sandbox / test key / none) |
|---|---|---|---|
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
