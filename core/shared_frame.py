import os
import cv2

_PATH = "/tmp/careai_frame.jpg"
_TMP = _PATH + ".tmp"
_ENCODE_PARAMS = [cv2.IMWRITE_JPEG_QUALITY, 75]


def set_latest_frame(frame) -> None:
    """Encode frame to JPEG and atomically replace the shared temp file."""
    try:
        ok, buf = cv2.imencode(".jpg", frame, _ENCODE_PARAMS)
        if not ok:
            return
        with open(_TMP, "wb") as f:
            f.write(buf.tobytes())
        os.replace(_TMP, _PATH)  # atomic on POSIX — no torn reads
    except Exception:
        pass


def get_latest_frame() -> bytes | None:
    """Return the latest JPEG bytes, or None if no frame is available yet."""
    try:
        with open(_PATH, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception:
        return None
