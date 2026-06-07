# Fall Detection — Code Audit & Review

**Scope:** `ai/patrol/fall_detector.py`, `ai/patrol/emergency_state.py`, `ai/patrol/patrol_mode.py`
**Model:** MediaPipe PoseLandmarker Lite (float16)
**Date:** 2026-06-06

---

## 1. Current Algorithm Explanation

### Pipeline Overview

```
Camera frame
    │
    ▼
MediaPipe PoseLandmarkerLite  (every frame, VIDEO mode)
    │
    ├─ No person detected → reset EmergencyState, stop
    │
    └─ Person detected → every 3rd frame:
           │
           ▼
       detect_fall_or_lying()
           │
           ├─ False → EmergencyState.update(False) → reset to NORMAL if needed
           │
           └─ True  → EmergencyState.update(True)
                          │
                          ├─ t ≥ 2.0s → POSSIBLE_FALL
                          ├─ t ≥ 5.0s → CONFIRMING_EMERGENCY
                          └─ t ≥ 7.0s → EMERGENCY_CONFIRMED → callback fires
```

### Landmarks Used

MediaPipe Pose produces 33 landmarks (normalized x, y ∈ [0, 1] with visibility score).
The detector uses only **5 of them** for classification, plus all visible landmarks for the bounding box:

| Role | Index | Name |
|---|---|---|
| Bounding box | all visible | All landmarks with visibility > 0.5 |
| H2, H3 key check | 11 | Left Shoulder |
| H2, H3 key check | 12 | Right Shoulder |
| H2, H3 key check | 23 | Left Hip |
| H2, H3 key check | 24 | Right Hip |
| H3 | 0 | Nose |

33 available landmarks (knees, ankles, wrists, elbows, feet, eyes, ears) are **ignored**.

### Fall Heuristics (≥ 2 of 3 must fire)

**Pre-condition:** ≥ 8 landmarks visible with `visibility > 0.5`. If not met, returns `False` immediately.

| # | Name | Condition | Threshold |
|---|---|---|---|
| H1 | Horizontal bounding box | `bbox_width > bbox_height × 1.3` | `_ASPECT_RATIO = 1.3` |
| H2 | Shoulder–hip vertical collapse | `|shoulder_midpoint_y − hip_midpoint_y| < 0.2` | `_SHOULDER_HIP_V = 0.2` |
| H3 | Nose at hip level | `|nose_y − hip_midpoint_y| < 0.25` | `_NOSE_HIP_V = 0.25` |

H2 and H3 only run if all four shoulder/hip landmarks are visible with confidence > 0.5.

### Emergency State Machine

```
NORMAL
  │  fall detected continuously for ≥ 2.0 s
  ▼
POSSIBLE_FALL          (prints: "Possible fall detected")
  │  still falling for ≥ 3.0 s more
  ▼
CONFIRMING_EMERGENCY   (prints: "Confirming emergency...")
  │  still falling for ≥ 2.0 s more
  ▼
EMERGENCY_CONFIRMED    (fires on_camera_emergency callback, logs to memory)

At any point: fall_detected = False  →  reset to NORMAL
Person leaves frame                  →  silent reset to NORMAL
```

**Total time from first fall signal to confirmed alert: 7.0 seconds.**

### Key Configuration Values

| Parameter | Value | Location |
|---|---|---|
| Minimum visible landmarks | 8 | `fall_detector.py:_MIN_VISIBLE` |
| Visibility threshold | 0.5 | `fall_detector.py:_VISIBILITY_MIN` |
| Bbox aspect ratio threshold | 1.3 | `fall_detector.py:_ASPECT_RATIO` |
| Shoulder–hip vertical gap | 0.2 | `fall_detector.py:_SHOULDER_HIP_V` |
| Nose–hip vertical gap | 0.25 | `fall_detector.py:_NOSE_HIP_V` |
| Fall check interval | every 3 frames | `patrol_mode.py:_FALL_CHECK_EVERY` |
| Pose detection confidence | 0.5 | `patrol_mode.py` options |
| POSSIBLE_FALL timer | 2.0 s | `emergency_state.py` |
| CONFIRMING timer | 3.0 s | `emergency_state.py` |
| FINAL_CONFIRM timer | 2.0 s | `emergency_state.py` |

---

## 2. Strengths

- **Voting system.** Requiring ≥ 2 of 3 heuristics substantially reduces single-heuristic noise. A transient camera glitch that briefly distorts the bounding box will not trigger H2 or H3.
- **Temporal confirmation.** The 7-second state machine prevents one-frame detections from raising an alarm. Most false postures (bending to pick something up, quick stretches) resolve before 7 seconds.
- **Confidence pre-filter.** The `_MIN_VISIBLE = 8` and `_VISIBILITY_MIN = 0.5` guards prevent detection from running on near-empty or highly occluded frames.
- **Key landmark confidence check.** H2 and H3 are gated on all four shoulder/hip landmarks being individually confident, not just the count.
- **Pixel-space bounding box.** The aspect ratio (H1) is computed in pixel space, not normalized, so it works correctly on non-square frames without distortion.
- **Emergency state stickiness.** `EMERGENCY_CONFIRMED` does not auto-reset — it persists until fall_detected clears, preventing a brief recovery from masking an ongoing emergency.
- **Modular design.** `fall_detector.py`, `emergency_state.py`, and `patrol_mode.py` are clearly separated. Each can be tested and replaced independently.

---

## 3. Weaknesses

### Critical

1. **Person lost → emergency resets.** When a person disappears from the camera frame — for example because they fell behind furniture, out of frame, or the robot arm moved — the code calls `self._emergency.reset()` silently. This is the most dangerous bug: a person falls, the robot loses sight of them, and the emergency state is cleared. The exact scenario where an alert is most needed produces a reset instead.

2. **No motion / velocity analysis.** The detector is purely postural. A person who slowly lies down on a mat to do yoga and a person who collapses unconsciously produce identical heuristic outputs. There is no measurement of how fast the transition happened.

3. **No inactivity detection after confirmation.** After `EMERGENCY_CONFIRMED`, the system fires the callback once and then does nothing further with the state. There is no check for whether the person moves again, escalates, or remains motionless.

### Structural

4. **Only 5 of 33 landmarks used.** The MediaPipe model produces knees, ankles, wrists, elbows, feet, face landmarks — none of which are used. Ankle position alone would distinguish a lying-down person from a person in a push-up.

5. **Lite model.** `pose_landmarker_lite.task` is the smallest, least accurate model. The full and heavy variants have significantly better accuracy, especially at distance, with partial occlusion, or in poor lighting. Elderly care environments routinely have all three.

6. **Fall check every 3rd frame only.** At 30 fps, the detector runs at ~10 fps. A person who falls in 0.5 seconds is already on the ground before the first check. The 7-second confirmation catches the aftermath, but the transition itself is invisible.

7. **num_poses = 1.** Only one person is detected. If a caregiver is present and closer to the camera than the patient, the patient's pose is silently ignored.

8. **No camera position awareness.** The patrol camera is on a robot wrist that physically rotates. The normalized landmark coordinates change depending on how the arm is oriented. The algorithm has no knowledge of camera angle and treats all poses as if the camera is upright and level.

---

## 4. False Positive Scenarios

### 4.1 Person Sleeping / Lying Down

**Triggers fall detection: YES — always.**

When a person lies in bed or on the floor:
- H1 fires: body is wider than tall in the frame.
- H2 fires: shoulders and hips are at nearly identical Y coordinates.
- H3 fires: nose is at approximately hip level.

All three heuristics fire. After 7 continuous seconds of lying still (which is immediate, since the person stays horizontal), `EMERGENCY_CONFIRMED` is reached. Every time the patient goes to sleep would trigger a false emergency.

### 4.2 Person Lying on Sofa

**Triggers fall detection: YES — always.**

Identical analysis to sleeping. Sofa elevation does not change the normalized landmark positions. All three heuristics fire within one frame of the person becoming horizontal.

### 4.3 Person Exercising

**Triggers fall detection: LIKELY for floor exercises.**

- Push-up position: body is horizontal → H1, H2, H3 all fire. If held for 7+ seconds, confirms emergency.
- Yoga warrior or tree pose: body is vertical and asymmetric → H1 unlikely, H2/H3 unlikely. Probably safe.
- Sit-ups: person alternates horizontal/vertical. Each horizontal phase lasts ~1–2 seconds. The 2-second `POSSIBLE_FALL` timer means a slow sit-up or a hold at the bottom fires POSSIBLE_FALL but likely clears before CONFIRMING_EMERGENCY. A higher risk in slow or assisted exercise.
- Stretching on the floor: same as push-up analysis.

### 4.4 Camera Angle Changes / Robot Arm Movement

**Triggers fall detection: UNPREDICTABLY.**

The wrist camera is mounted on the SO-101 robot arm and defaults to 270° rotation correction. As the arm moves during patrol, the frame orientation shifts. A vertical person viewed from a 45° sideways angle may have a bounding box that is roughly square, which does not trigger H1. But at certain arm angles, a standing person's projected bounding box could be wider than tall, triggering H1. Combined with slight variations in shoulder/hip Y positions from the oblique view, this could cause spurious heuristic firing.

### 4.5 Partial Body Visible (Only Upper or Lower Half)

**Triggers fall detection: UNLIKELY for half-body; VARIABLE for three-quarters.**

If only the upper body is visible (waist and above), all landmark Y values cluster in the top half of the frame. The bounding box is taller than wide → H1 does not fire. H2 depends on whether shoulders and hips are at similar Y — with only upper body visible, hips may not be detected at all, so H2/H3 are gated off. Safe, but only because H1 doesn't fire.

If three-quarters visible (head to below knee), a standing person still projects as taller than wide, so H1 is safe. However, if the person bends, the bounding box widens, and H1 could fire.

### 4.6 Person Bending to Pick Something Up

**Triggers fall detection: POSSIBLE if held longer than 7 seconds.**

When a person bends deeply at the waist:
- Head descends toward hip level → H3 approaches threshold.
- Shoulders approach hip Y level → H2 may fire.
- Body bounding box may become wider → H1 may fire.

A quick pick-up (under 2 seconds) is safe due to the POSSIBLE_FALL timer. Searching on the floor for a dropped item, tying shoes slowly, or gardening could sustain the posture long enough to reach EMERGENCY_CONFIRMED.

### 4.7 Person Sitting on Ground (Cross-Legged)

**Triggers fall detection: POSSIBLE.**

When sitting cross-legged:
- Hips are on the floor; shoulders are above but not by much.
- H2: shoulder–hip vertical gap may be under 0.2 in normalized coordinates.
- H1: bounding box could be near-square or wide.
- H3: nose is above hip level — likely safe.

If H1 + H2 both fire, emergency escalation begins. A person sitting on the ground for 7+ seconds (common for floor exercises, resting, or playing with a grandchild) reaches EMERGENCY_CONFIRMED.

### 4.8 Low-Confidence Landmarks

**Triggers fall detection: NO (correctly).**

If fewer than 8 landmarks have `visibility > 0.5`, the function returns `False` immediately. If the four key landmarks (shoulders, hips) are low-confidence, H2 and H3 are skipped. At most H1 fires, which is insufficient (need ≥ 2). Low-confidence detection is one area the code handles well.

---

## 5. False Negative Scenarios

### 5.1 Real Fall, Body Partially Occluded

**Detection: MISSED.**

If a person falls and furniture, a wall, or the camera angle means fewer than 8 landmarks are visible, the detector returns `False` on every frame. The emergency timer never starts. This is a realistic scenario in any furnished living space.

### 5.2 Sideways Fall (Camera Perpendicular to Fall Direction)

**Detection: LIKELY CAUGHT via H2 + H3, but delayed.**

After a sideways fall onto the floor, the person's shoulders and hips are at the same vertical position (H2 fires), and the nose approaches hip level (H3 fires). H1 depends on camera angle and body rotation. H2 + H3 = 2 heuristics → detection proceeds. The fall itself is not observed, only the resulting horizontal posture. Detection proceeds normally if the person stays in frame after falling.

### 5.3 Fast Collapse (Person Falls in Under 2 Seconds)

**Detection: THE FALL IS MISSED; the aftermath is caught.**

A fast collapse means the person goes from standing to horizontal in under one second. The POSSIBLE_FALL timer requires 2.0 continuous seconds of fall detection. During the fall itself (< 1 second), the detector may fire `True` for 2–3 frames, but this clears the 2-second threshold. The person then lies on the floor, which immediately triggers H1+H2+H3 again — now sustained — so the 7-second clock starts from when they are on the floor.

**Net effect:** Emergency confirmed approximately 7 seconds after landing, not from the moment of falling. For an unconscious elderly person, 7 seconds to start the timer plus confirmation delay means alert arrives roughly 7+ seconds late. That is acceptable for survivable falls but could matter in cardiac events.

### 5.4 Person Falls Behind Furniture (Disappears from Frame)

**Detection: CRITICAL MISS.**

This is the most dangerous false negative, combined with the person-lost reset bug (Weakness #1). The person is visible and standing. They fall and land behind a sofa. The camera loses pose detection. `patrol_mode.py` line 83 executes `self._emergency.reset()`. The emergency state returns to `NORMAL`. The person is on the floor, invisible, and no alert is raised.

### 5.5 Person Falls Outside Center of Frame / Camera Edge

**Detection: UNRELIABLE.**

MediaPipe's confidence drops for poses near frame edges. Key landmark visibility scores drop below 0.5, triggering the gating conditions that prevent H2 and H3. If the visible landmark count also drops below 8, the function returns `False` immediately. A person who falls near a doorway or beside a wall at the frame edge may not be detected.

### 5.6 Person Falls While in SORTING Mode

**Detection: NEVER.**

Fall detection only runs in `AppMode.PATROL`. If the system is in SORTING or DOSAGE mode, `patrol.process_frame()` is never called. A fall while the robot is scanning a medicine box is completely ignored. The system has no background fall detection capability.

---

## 6. Robustness Evaluation

| Component | Score | Rationale |
|---|---|---|
| Person detection reliability | **5 / 10** | MediaPipe Lite works well in daylight, short range, clear sightlines. Fails with occlusion, low light, distance > 3m, multiple people in frame, camera motion blur during robot movement. |
| Pose detection reliability | **4 / 10** | Lite model is the least accurate variant. Only 5 of 33 landmarks used — the system discards most of the signal the model produces. No smoothing between frames. |
| Fall classification reliability | **3 / 10** | Three geometry-based heuristics cannot distinguish a fall from sleeping, lying, or many floor-level activities. No temporal velocity, no transition analysis, no ankle/knee data. High false positive rate for any horizontal posture. |
| Emergency escalation reliability | **5 / 10** | The state machine logic is sound and the 7-second timer helps. But the person-lost reset is a critical flaw that inverts the expected behavior in one of the most important scenarios. |

**Overall system reliability for real elderly care: 4 / 10**

---

## 7. Recommended Improvements

Listed by priority. None are implemented here — analysis only.

### Priority 1 — Critical Safety Fixes

**1.1 Fix person-lost emergency reset**
When pose detection is lost while the system is in `POSSIBLE_FALL` or higher, do not reset the emergency. Instead, escalate: a person who was falling and then disappears is more likely behind furniture than recovered. Implement a grace period (e.g., 5 seconds of person absence while in elevated state → escalate to EMERGENCY_CONFIRMED).

**1.2 Background fall monitoring across all modes**
Fall detection should not be tied to `AppMode.PATROL`. Run a lightweight pose check on a background thread regardless of mode. A person who falls during medicine scanning must still trigger an alert.

### Priority 2 — Detection Quality

**2.1 Add velocity / posture transition analysis**
Track the Y position of key landmarks (shoulder midpoint, hip midpoint) over the last N frames. A fall involves rapid downward displacement (high velocity) followed by sudden stillness. A person lying down gradually shows slow displacement. This single feature would substantially reduce false positives from sleeping while maintaining true positive sensitivity.

```
fall_score += 1  if |Δshoulder_y / Δt| > FALL_VELOCITY_THRESHOLD
fall_score += 1  if posture was STANDING in previous 10 frames
```

**2.2 Add more landmarks — ankles and knees**
- Ankle Y position: In a standing person, ankles are at maximum Y (bottom of frame). After a fall, ankles and hips are at the same level. `|ankle_y − hip_y| < 0.15` is a strong fall signal.
- Knee Y position: In lying-down vs. sitting, the knee angle distinguishes the postures.

Using ankles (27, 28) and knees (25, 26) would allow the system to distinguish:
- Standing (ankles low, hips mid, shoulders high)
- Sitting (ankles mid, knees bent, hips low)
- Lying (all landmarks at similar Y)
- Fallen (rapid transition to lying, then stillness)

**2.3 Inactivity detection post-confirmation**
After `EMERGENCY_CONFIRMED`, track whether any landmark moves by more than a minimum threshold across 5-second windows. No movement → escalate alert severity or re-notify. This matters for unconscious falls where the person stays motionless.

**2.4 Add temporal smoothing**
Require that `detect_fall_or_lying()` returns `True` for at least 3 consecutive fall checks (at 10 fps ≈ 0.3 seconds) before accumulating toward the 2-second timer. This suppresses single-frame glitches without increasing the overall confirmation window.

### Priority 3 — Reliability

**3.1 Upgrade to full PoseLandmarker model**
`pose_landmarker_full.task` or `pose_landmarker_heavy.task` provides significantly higher landmark accuracy, especially for partial body visibility, distance, and non-ideal lighting. The Lite model was chosen for speed — evaluate whether the hardware supports the full model at acceptable frame rates.

**3.2 Confidence-weighted heuristic scoring**
Weight each heuristic by the minimum visibility score of its contributing landmarks. A heuristic firing with all landmarks at 0.51 confidence should count less than one firing with all at 0.95.

**3.3 Camera angle compensation**
When the robot arm rotates, the frame orientation changes. Track the arm's known joint angles (already available via `jointStore`) and apply a coordinate transform to landmark positions before running the heuristics. This would prevent arm movement from causing spurious detections or blind spots.

**3.4 Multi-person support**
Set `num_poses = 2` or higher and track each detected person independently. In a care home, caregivers are present. The current system may lock onto the caregiver's pose instead of the patient's.

### Priority 4 — Robustness for Specific Scenarios

**4.1 Sleep / lying down context filter**
Maintain a "sleeping window" (e.g., 22:00–08:00) in which sustained horizontal detection is treated as sleep, not a fall. Outside this window, apply normal detection. This eliminates the nightly false-positive flood.

**4.2 Distinguish lying down vs. fallen by prior state**
If the system observed the person standing or moving within the last 30 seconds and now detects a horizontal posture, weight the detection as a fall. If the person was already horizontal (woke up slowly, sat down gradually), treat it as intentional. Track `last_upright_timestamp` to provide this context.

---

## 8. How Would This Perform in a Real Elderly Care Deployment?

### Safety Assessment

**Likely outcome: Unreliable in both directions — too many false alarms, and critical real falls can be missed.**

In a real deployment with an elderly patient living alone:

**Night (22:00–08:00):** The patient sleeps. The camera detects a horizontal person every frame. After 7 seconds of lying in bed, `EMERGENCY_CONFIRMED` fires. This happens every night, multiple times. Caregivers are notified of non-existent emergencies. Within days, alert fatigue sets in and notifications are ignored or disabled — eliminating the safety benefit entirely.

**Morning routine:** Patient sits on the edge of the bed (horizontal pose transitioning), exercises, does yoga, bends to put on socks. Each of these activities can trigger POSSIBLE_FALL or higher before resolving.

**Real fall in the living room:** Patient falls near the sofa. If the camera sees them on the floor with all landmarks visible, the 7-second confirmation proceeds correctly. **Alert raised, true positive.**

**Real fall behind the sofa:** Patient falls, disappears from camera. Emergency state resets. **No alert. Highest-risk failure mode.** The patient may lie unconscious on the floor for hours.

**Real fall in a different room:** Patrol mode uses a single fixed camera (or a wrist-mounted one). The patient falls in the bathroom, out of camera range. **No alert.**

**Real fall during SORTING mode:** The robot is scanning medicine. **No alert at all.**

### Reliability in Context

| Scenario | Expected Outcome | Verdict |
|---|---|---|
| Patient sleeps in bed | Emergency alert every night | Dangerous false positive |
| Patient falls in camera view, stays visible | Alert in ~7s | Correct |
| Patient falls behind furniture | Emergency resets, no alert | Dangerous false negative |
| Patient falls in bathroom / different room | No detection | Coverage gap |
| Patient bends to pick something up for 10s | Alert triggered | False positive |
| Fast cardiac event, collapses | Alert ~7s after landing | Acceptable delay |
| Robot in SORTING mode | No fall detection running | Coverage gap |

### Expected Failure Rate

In a typical 24-hour period with a mobile elderly patient:
- **False positives:** 5–15+ (sleeping, lying down, floor exercises, extended bending)
- **True positives (falls in camera view):** Correctly caught, ~7s delay
- **False negatives:** Any fall outside camera sightline, behind furniture, or during non-patrol mode

### Minimum Viable Path to Safe Deployment

Before deploying in any real care context, these three changes are essential — everything else is secondary:

1. **Fix person-lost reset in emergency states.** Person disappearing while alarm is active must never silently clear the alarm.
2. **Add sleeping/intentional lying context.** Time-gating or transition analysis to suppress nightly false positives.
3. **Run background fall detection across all modes.** No mode switch should create a fall detection blind spot.

Without these three, the system is not safe for deployment. With them, it becomes a reasonable first-generation prototype that would benefit from the velocity and landmark improvements as a second iteration.
