import threading
from datetime import datetime
from typing import Optional

from memory.care_memory import CareMemory


class ReminderChecker:
    def __init__(self, memory: CareMemory, interval: int = 30, tts=None) -> None:
        self._memory = memory
        self._interval = interval
        self._tts = tts
        # (date, schedule_id, time) — tracks what has already fired today
        self._fired: set[tuple[str, str, str]] = set()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ReminderChecker")

    def start(self) -> None:
        self._thread.start()

    def check_now(self) -> None:
        """Run a check immediately (from the calling thread) and reset the 30-second timer."""
        self._check()
        self._wake.set()

    def _run(self) -> None:
        while True:
            self._check()
            self._wake.wait(timeout=self._interval)
            self._wake.clear()

    def _check(self) -> None:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hhmm = now.strftime("%H:%M")
        for schedule in self._memory.get_active_schedules():
            sid = schedule["id"]
            for t in schedule["times"]:
                if t != current_hhmm:
                    continue
                key = (today, sid, t)
                with self._lock:
                    if key in self._fired:
                        continue
                    self._fired.add(key)
                _print_reminder(schedule)
                if self._tts:
                    self._tts.speak(
                        f"It's time to take {schedule['medicine_name']}. "
                        f"Dose: {schedule['dose']}."
                    )


def _print_reminder(schedule: dict) -> None:
    print("\n================ MEDICINE REMINDER ================")
    print(f"Time to take: {schedule['medicine_name']}")
    print(f"Dose: {schedule['dose']}")
    if schedule.get("notes"):
        print(f"Notes: {schedule['notes']}")
    print("===================================================\n")
