import time
from typing import Optional

POSSIBLE_FALL_SECONDS = 2.0
CONFIRMING_SECONDS = 3.0
FINAL_CONFIRM_SECONDS = 2.0

NORMAL = "NORMAL"
POSSIBLE_FALL = "POSSIBLE_FALL"
CONFIRMING_EMERGENCY = "CONFIRMING_EMERGENCY"
EMERGENCY_CONFIRMED = "EMERGENCY_CONFIRMED"


class EmergencyState:
    """
    Time-based state machine that confirms a fall emergency in stages.

    Call update(fall_detected, now) on each fall-check tick.
    All terminal output is handled internally; callers only pass the boolean.
    """

    def __init__(self) -> None:
        self.phase: str = NORMAL
        self._phase_entered_at: float = 0.0
        self._fall_start: Optional[float] = None

    # ------------------------------------------------------------------
    def update(self, fall_detected: bool, now: Optional[float] = None) -> None:
        if now is None:
            now = time.monotonic()

        if not fall_detected:
            self._fall_start = None
            if self.phase != NORMAL:
                if self.phase == EMERGENCY_CONFIRMED:
                    print("Emergency reset / person recovered")
                else:
                    print("Fall cleared")
                self._enter(NORMAL, now)
            return

        # fall is ongoing — track how long
        if self._fall_start is None:
            self._fall_start = now
        fall_duration = now - self._fall_start

        if self.phase == NORMAL:
            if fall_duration >= POSSIBLE_FALL_SECONDS:
                self._enter(POSSIBLE_FALL, now)
                print("Possible fall detected")

        elif self.phase == POSSIBLE_FALL:
            if (now - self._phase_entered_at) >= CONFIRMING_SECONDS:
                self._enter(CONFIRMING_EMERGENCY, now)
                print("Confirming emergency...")

        elif self.phase == CONFIRMING_EMERGENCY:
            if (now - self._phase_entered_at) >= FINAL_CONFIRM_SECONDS:
                self._enter(EMERGENCY_CONFIRMED, now)
                print("EMERGENCY DETECTED")

        # EMERGENCY_CONFIRMED: do nothing until fall clears

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Silent reset — use when person leaves frame."""
        self.phase = NORMAL
        self._phase_entered_at = 0.0
        self._fall_start = None

    # ------------------------------------------------------------------
    def _enter(self, phase: str, now: float) -> None:
        self.phase = phase
        self._phase_entered_at = now
