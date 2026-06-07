import time
from typing import Optional


SCANNING = "SCANNING"
WAITING_FOR_REMOVAL = "WAITING_FOR_REMOVAL"

NO_TEXT_MIN_SECONDS = 2.5
NO_TEXT_MIN_CYCLES = 3
READABLE_MIN_LEN = 5


class MedicineScanState:
    def __init__(self) -> None:
        self.phase: str = SCANNING
        self.current_medicine_name: Optional[str] = None
        self.current_expiration_date: Optional[str] = None
        self.completed_results: list[dict] = []
        self.removal_detected: bool = False
        self._reported: bool = False
        self.no_text_cycles: int = 0
        self._no_text_since: Optional[float] = None

    def update(self, medicine_name: Optional[str], expiration_date: Optional[str], raw_text: str = "") -> bool:
        """
        Drive the state machine with latest OCR output.
        Returns True when a medicine scan completes.
        Sets self.removal_detected = True when the cleared-camera condition fires.
        """
        self.removal_detected = False
        readable = len(raw_text.strip()) >= READABLE_MIN_LEN

        if self.phase == SCANNING:
            if medicine_name:
                self.current_medicine_name = medicine_name
            if expiration_date:
                self.current_expiration_date = expiration_date

            if self.is_complete() and not self._reported:
                self._reported = True
                self.completed_results.append({
                    "medicine_name": self.current_medicine_name,
                    "expiration_date": self.current_expiration_date,
                })
                self.phase = WAITING_FOR_REMOVAL
                self.no_text_cycles = 0
                self._no_text_since = None
                return True

            return False

        # WAITING_FOR_REMOVAL
        if readable:
            self.no_text_cycles = 0
            self._no_text_since = None
        else:
            if self._no_text_since is None:
                self._no_text_since = time.monotonic()
            self.no_text_cycles += 1
            elapsed = time.monotonic() - self._no_text_since
            if elapsed >= NO_TEXT_MIN_SECONDS or self.no_text_cycles >= NO_TEXT_MIN_CYCLES:
                self.removal_detected = True
                self.reset_current()

        return False

    def is_complete(self) -> bool:
        return bool(self.current_medicine_name and self.current_expiration_date)

    def reset_current(self) -> None:
        self.current_medicine_name = None
        self.current_expiration_date = None
        self._reported = False
        self.phase = SCANNING
        self.no_text_cycles = 0
        self._no_text_since = None

    def get_missing_fields(self) -> list[str]:
        missing = []
        if not self.current_medicine_name:
            missing.append("medicine_name")
        if not self.current_expiration_date:
            missing.append("expiration_date")
        return missing
