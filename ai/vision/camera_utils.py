"""
Camera utility functions for OpenCV-based video capture.
"""

from typing import Optional, Tuple

import cv2
import numpy as np


def open_camera(
    index: int = 0,
    width: int = 1280,
    height: int = 720,
) -> cv2.VideoCapture:
    """
    Open the camera at *index* and request the given resolution.
    On macOS the built-in FaceTime camera is usually index 0.

    Raises RuntimeError if the camera cannot be opened.
    """
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera index {index}. "
            "Check that the camera is connected and that macOS camera "
            "permissions are granted for this terminal / application."
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def read_frame(cap: cv2.VideoCapture) -> Optional[np.ndarray]:
    """Read one frame.  Returns the frame array, or None on failure."""
    ret, frame = cap.read()
    return frame if ret else None


def get_center_crop(
    frame: np.ndarray,
    ratio: float = 0.65,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Return a centre-cropped region of *frame*.
    Returns ``(cropped_array, (x, y, w, h))``.
    """
    h, w = frame.shape[:2]
    cw, ch = int(w * ratio), int(h * ratio)
    x, y = (w - cw) // 2, (h - ch) // 2
    return frame[y : y + ch, x : x + cw], (x, y, cw, ch)


def resize_for_display(frame: np.ndarray, max_width: int = 1280) -> np.ndarray:
    """Scale the frame down if it is wider than *max_width*, preserving aspect ratio."""
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    return cv2.resize(frame, (max_width, int(h * scale)))
