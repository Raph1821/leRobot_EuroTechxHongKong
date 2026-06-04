import queue
import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

_SAMPLE_RATE = 16000
_CHUNK_SECONDS = 3

# Commands matched by substring in the transcribed text.
# Ordered longest-first so "sorting mode" matches before "mode".
COMMANDS = [
    "sorting mode",
    "patrol mode",
    "show medicines",
    "reset",
]


class SpeechListener:
    """
    Records microphone audio in background chunks, transcribes offline
    with faster-whisper, and puts recognised command strings into a queue.
    """

    def __init__(self, command_queue: queue.Queue, model_size: str = "tiny") -> None:
        self._queue = command_queue
        print("Loading speech model…")
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Speech model ready. Listening for voice commands.")
        self._running = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        while self._running:
            audio = sd.rec(
                int(_CHUNK_SECONDS * _SAMPLE_RATE),
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
            )
            sd.wait()

            segments, _ = self._model.transcribe(
                audio.flatten(),
                language="en",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
            )

            text = " ".join(seg.text for seg in segments).lower().strip()
            if not text:
                continue

            for command in COMMANDS:
                if command in text:
                    print(f"Voice command: {command}")
                    self._queue.put(command)
                    break
