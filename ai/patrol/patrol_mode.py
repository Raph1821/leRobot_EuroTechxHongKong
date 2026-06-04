import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)
_MODEL_PATH = Path(__file__).parent.parent / "data" / "pose_landmarker_lite.task"


def _ensure_model() -> Path:
    if not _MODEL_PATH.exists():
        print(f"Downloading pose model to {_MODEL_PATH} …")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("Download complete.")
    return _MODEL_PATH


class PatrolMode:
    def __init__(self, debug: bool = False) -> None:
        self._debug = debug
        self._person_visible: bool = False
        self._start_ms: int = int(time.monotonic() * 1000)

        model_path = _ensure_model()
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = mp_vision.PoseLandmarker.create_from_options(options)

    def process_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(time.monotonic() * 1000) - self._start_ms

        result = self._detector.detect_for_video(mp_image, timestamp_ms)
        detected = len(result.pose_landmarks) > 0

        if detected and not self._person_visible:
            self._person_visible = True
            print("Person detected")
        elif not detected and self._person_visible:
            self._person_visible = False
            print("Person lost")

        if self._debug:
            print(f"[PATROL] person_visible={self._person_visible}")

    def reset(self) -> None:
        self._person_visible = False

    def print_debug_state(self) -> None:
        print("\n--- PATROL mode state ---")
        print(f"  person_visible: {self._person_visible}")
        print(f"  debug: {self._debug}")
        print("-------------------------")

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled
