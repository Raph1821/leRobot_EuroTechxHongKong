"""
Visual memory — stores and retrieves images (JPEG-encoded, base64) with persistence.
"""

from __future__ import annotations

import base64
import logging
import os
import pickle

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class VisualMemory:
    """In-memory image store with pickle persistence."""

    def __init__(self, output_dir: str | None = None):
        self.images: dict[str, str] = {}
        self.output_dir = output_dir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

    def add(self, image_id: str, image: np.ndarray) -> None:
        ok, encoded = cv2.imencode(".jpg", image)
        if ok:
            self.images[image_id] = base64.b64encode(encoded.tobytes()).decode()

    def get(self, image_id: str) -> np.ndarray | None:
        if image_id not in self.images:
            return None
        data = base64.b64decode(self.images[image_id])
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

    def count(self) -> int:
        return len(self.images)

    def save(self, path: str | None = None) -> str:
        path = path or (os.path.join(self.output_dir, "visual_memory.pkl") if self.output_dir else "")
        if not path:
            return ""
        with open(path, "wb") as f:
            pickle.dump(self.images, f)
        logger.info(f"Saved {len(self.images)} images to {path}")
        return path

    @classmethod
    def load(cls, path: str, output_dir: str | None = None) -> VisualMemory:
        instance = cls(output_dir=output_dir)
        if os.path.exists(path):
            with open(path, "rb") as f:
                instance.images = pickle.load(f)
            logger.info(f"Loaded {len(instance.images)} images from {path}")
        return instance

    def clear(self) -> None:
        self.images = {}
