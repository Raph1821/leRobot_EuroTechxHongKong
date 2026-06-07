"""
Exploration Memory — semantic visual memory for the EXPLORATION mode.

While the robot is in EXPLORATION mode, it stores CLIP embeddings of what the
camera sees. Later, the user can ask natural-language questions through the
interaction chat, e.g.:

    "I need something I can drink"
        -> finds the stored frame most similar to that phrase (a water bottle)
        -> the assistant can answer: "I see a bottle of water you can drink."

This is a lightweight wrapper around the CLIP embedding provider. Unlike the
full DimOS SpatialMemory (which needs ChromaDB + robot odometry), this keeps
embeddings in memory and does cosine-similarity search — perfect for a
stationary arm with no position tracking.

Usage:
    mem = ExplorationMemory()
    mem.observe(frame)                       # call repeatedly while exploring
    hit = mem.query("something to drink")    # returns best match or None
"""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    obs_id: str
    embedding: np.ndarray
    image_jpeg: bytes
    timestamp: float


@dataclass
class QueryHit:
    obs_id: str
    score: float          # cosine similarity 0..1 (higher = better)
    image_jpeg: bytes
    timestamp: float


class ExplorationMemory:
    """In-memory CLIP visual memory with text-query retrieval."""

    def __init__(
        self,
        min_interval: float = 0.8,     # seconds between stored frames
        dedup_threshold: float = 0.92,  # skip if too similar to an existing frame
        max_items: int = 300,
        clip_model_path: str | None = None,
    ):
        self.min_interval = min_interval
        self.dedup_threshold = dedup_threshold
        self.max_items = max_items
        self._observations: list[Observation] = []
        self._last_store_time: float = 0.0
        self._count = 0

        # The interaction module lives at the repo root; make it importable.
        self._provider = None
        try:
            import os
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from interaction.memory.embedding import ImageEmbeddingProvider
            self._provider = ImageEmbeddingProvider(model_path=clip_model_path)
            logger.info("ExplorationMemory: CLIP provider ready.")
        except Exception as e:
            logger.warning(f"ExplorationMemory: CLIP provider unavailable ({e}).")

    @property
    def available(self) -> bool:
        return self._provider is not None and getattr(self._provider, "model", None) is not None

    @property
    def count(self) -> int:
        return len(self._observations)

    def observe(self, frame: np.ndarray) -> bool:
        """Store the frame's embedding if enough time passed and it's novel.

        Returns True if stored, False if skipped.
        """
        if self._provider is None:
            return False

        now = time.time()
        if now - self._last_store_time < self.min_interval:
            return False

        emb = self._provider.get_embedding(frame)

        # Dedup: skip if near-identical to a recent observation.
        for obs in self._observations[-20:]:
            if float(np.dot(emb, obs.embedding)) > self.dedup_threshold:
                self._last_store_time = now
                return False

        import cv2
        ok, buf = cv2.imencode(".jpg", frame)
        image_jpeg = buf.tobytes() if ok else b""

        self._count += 1
        self._observations.append(Observation(
            obs_id=f"obs_{self._count}",
            embedding=emb,
            image_jpeg=image_jpeg,
            timestamp=now,
        ))
        # Cap memory size (drop oldest).
        if len(self._observations) > self.max_items:
            self._observations.pop(0)

        self._last_store_time = now
        return True

    def query(self, text: str, top_k: int = 1, min_score: float = 0.18) -> list[QueryHit]:
        """Return the best matching observations for a natural-language query."""
        if self._provider is None or not self._observations:
            return []

        text_emb = self._provider.get_text_embedding(text)
        scored = []
        for obs in self._observations:
            score = float(np.dot(text_emb, obs.embedding))
            scored.append((score, obs))
        scored.sort(key=lambda s: s[0], reverse=True)

        hits = []
        for score, obs in scored[:top_k]:
            if score < min_score:
                continue
            hits.append(QueryHit(
                obs_id=obs.obs_id,
                score=score,
                image_jpeg=obs.image_jpeg,
                timestamp=obs.timestamp,
            ))
        return hits

    def clear(self) -> None:
        self._observations.clear()
        self._count = 0
        self._last_store_time = 0.0
