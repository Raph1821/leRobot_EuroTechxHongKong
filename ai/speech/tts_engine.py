import queue
import subprocess
import threading


class TTSEngine:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="TTSEngine")
        self._thread.start()

    def speak(self, text: str) -> None:
        if self._enabled:
            self._queue.put(text)

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                return
            try:
                subprocess.run(["say", text], timeout=60, check=False)
            except FileNotFoundError:
                print("[TTS] Warning: 'say' command not found — TTS disabled.")
                self._enabled = False
            except subprocess.TimeoutExpired:
                print("[TTS] Warning: speech timed out, skipping.")
            except Exception as exc:
                print(f"[TTS] Warning: {exc}")
