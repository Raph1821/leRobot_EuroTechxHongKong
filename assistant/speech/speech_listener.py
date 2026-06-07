import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

from assistant.speech.emergency_phrases import EMERGENCY_PHRASES

_SAMPLE_RATE = 16000
_CHUNK_SECONDS = 3
_EMERGENCY_COOLDOWN = 10.0

# Ordered longest-first so "sorting mode" matches before bare "mode".
COMMANDS = [
    "sorting mode",
    "patrol mode",
    "show medicines",
    "reset",
]


class SpeechListener:
    """
    Records microphone audio in background chunks, transcribes offline
    with faster-whisper, and:
      - puts recognised command strings into a queue
      - calls on_voice_emergency(text) when an emergency phrase is heard
    """

    def __init__(
        self,
        command_queue: queue.Queue,
        on_voice_emergency: Optional[Callable[[str], None]] = None,
        model_size: str = "tiny",
        debug: bool = False,
    ) -> None:
        self._queue = command_queue
        self._on_emergency = on_voice_emergency
        self._debug = debug
        self._last_emergency_at: float = 0.0
        self._running = False
        self._model = None

        try:
            from faster_whisper import WhisperModel
            import sounddevice  # noqa: F401 — confirm mic library present
            print("Loading speech model…")
            self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
            print("Speech model ready. Listening for voice commands.")
        except Exception as e:
            print(f"Speech listener disabled: {e}")

        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled

    def _run(self) -> None:
        if self._model is None:
            return

        import sounddevice as sd

        while self._running:
            try:
                audio = sd.rec(
                    int(_CHUNK_SECONDS * _SAMPLE_RATE),
                    samplerate=_SAMPLE_RATE,
                    channels=1,
                    dtype=np.float32,
                )
                sd.wait()
            except Exception as e:
                print(f"Speech listener disabled: {e}")
                return

            try:
                segments, _ = self._model.transcribe(
                    audio.flatten(),
                    language="en",
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text for seg in segments).lower().strip()
            except Exception:
                continue

            if not text:
                continue

            if self._debug:
                print(f"[STT] {text!r}")

            # Emergency phrases — highest priority, with cooldown.
            now = time.monotonic()
            if self._on_emergency and (now - self._last_emergency_at) >= _EMERGENCY_COOLDOWN:
                for phrase in EMERGENCY_PHRASES:
                    if phrase in text:
                        self._last_emergency_at = now
                        self._on_emergency(text)
                        break  # one emergency per chunk

            # Regular commands.
            for command in COMMANDS:
                if command in text:
                    print(f"Voice command: {command}")
                    self._queue.put(command)
                    break
