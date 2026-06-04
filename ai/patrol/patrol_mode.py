import cv2
import mediapipe as mp


class PatrolMode:
    def __init__(self, debug: bool = False) -> None:
        self._debug = debug
        self._person_visible: bool = False
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def process_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        detected = result.pose_landmarks is not None

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
