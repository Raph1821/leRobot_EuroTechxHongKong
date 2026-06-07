from typing import Any

_MIN_VISIBLE = 8
_VISIBILITY_MIN = 0.5

# Landmark indices (MediaPipe Pose 33-point model)
_NOSE = 0
_L_SHOULDER, _R_SHOULDER = 11, 12
_L_HIP, _R_HIP = 23, 24

# Thresholds
_ASPECT_RATIO = 1.3   # bbox width / height above this → body is horizontal
_SHOULDER_HIP_V = 0.2  # normalized shoulder-hip vertical gap below this → horizontal
_NOSE_HIP_V = 0.25    # normalized nose-hip vertical gap below this → head alongside body


def detect_fall_or_lying(
    pose_landmarks: list[Any],
    frame_width: int,
    frame_height: int,
) -> bool:
    """
    Return True if the person appears to be lying down or fallen.

    pose_landmarks: list of NormalizedLandmark (x, y in 0-1 range, visibility 0-1).
    Requires at least 2 of 3 heuristics to fire to avoid false positives.
    """
    visible = [lm for lm in pose_landmarks if lm.visibility > _VISIBILITY_MIN]
    if len(visible) < _MIN_VISIBLE:
        return False

    # Pixel-space bounding box for accurate aspect ratio on non-square frames.
    xs = [lm.x * frame_width for lm in visible]
    ys = [lm.y * frame_height for lm in visible]
    bbox_w = max(xs) - min(xs)
    bbox_h = max(ys) - min(ys)
    if bbox_h < 1:
        return False

    # Heuristic 1: body bounding box is wider than tall.
    h1 = bbox_w > bbox_h * _ASPECT_RATIO

    # Heuristic 2: shoulder midpoint and hip midpoint are at similar vertical positions.
    key_ids = (_L_SHOULDER, _R_SHOULDER, _L_HIP, _R_HIP)
    key_ok = all(pose_landmarks[i].visibility > _VISIBILITY_MIN for i in key_ids)
    h2 = False
    hip_y = 0.0
    if key_ok:
        shoulder_y = (pose_landmarks[_L_SHOULDER].y + pose_landmarks[_R_SHOULDER].y) / 2
        hip_y = (pose_landmarks[_L_HIP].y + pose_landmarks[_R_HIP].y) / 2
        h2 = abs(shoulder_y - hip_y) < _SHOULDER_HIP_V

    # Heuristic 3: nose is at a similar vertical position to the hips.
    h3 = False
    if key_ok and pose_landmarks[_NOSE].visibility > _VISIBILITY_MIN:
        h3 = abs(pose_landmarks[_NOSE].y - hip_y) < _NOSE_HIP_V

    return (h1 + h2 + h3) >= 2
