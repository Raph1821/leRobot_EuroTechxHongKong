"""
Spatial Memory — builds a semantic map from video frames + robot pose.

Adapted for the SO-101 robotic arm (EuroTech x Hong Kong Hackathon).

Originally from DimOS (EPFL RoboHack 2026, Unitree Go2 quadruped branch).
Key adaptations for a STATIONARY robotic arm vs a mobile quadruped:

  1. Distance gate uses END-EFFECTOR pose, not base odometry.
     The SO-101 base never moves — only the arm joints change.
  2. Position = end-effector (x, y, z) in the robot's workspace frame.
  3. Rotation = camera/wrist orientation, not robot heading.
  4. Spatial queries use workspace coordinates (where the arm was pointing)
     rather than room-scale navigation coordinates.
  5. Thresholds are tuned for arm workspace (~0.5m range) instead of
     room-scale exploration (~10m+ range for a mobile robot).

Usage:
    from interaction.memory.spatial_memory import SpatialMemory

    mem = SpatialMemory(db_path="/tmp/carebot_memory")
    # position = end-effector XYZ, rotation = wrist RPY
    mem.process_frame(frame_bgr, position=(0.15, 0.0, 0.12), rotation=(0, -0.5, 1.2))
    results = mem.query_by_text("aspirin box")
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from typing import Any

import numpy as np

from interaction.memory.embedding import ImageEmbeddingProvider
from interaction.memory.spatial_vector_db import SpatialVectorDB
from interaction.memory.visual_memory import VisualMemory

logger = logging.getLogger(__name__)


class SpatialMemory:
    """Builds and queries a semantic spatial map of the arm's workspace.

    For the SO-101, "spatial" means the end-effector pose when the frame
    was captured — NOT the robot's base position (which is fixed).
    """

    def __init__(
        self,
        collection_name: str = "spatial_memory",
        embedding_model: str = "clip",
        db_path: str | None = None,
        visual_memory_path: str | None = None,
        new_memory: bool = True,
        # SO-101 workspace is ~0.3m radius — use small distance threshold.
        # Original DimOS used 0.5m for a quadruped traversing rooms.
        min_distance_threshold: float = 0.03,
        min_time_threshold: float = 0.5,
        dedup_threshold: float = 0.08,
        clip_model_path: str | None = None,
    ):
        self.min_distance_threshold = min_distance_threshold
        self.min_time_threshold = min_time_threshold
        self.dedup_threshold = dedup_threshold

        # Setup ChromaDB
        chroma_client = None
        if db_path:
            os.makedirs(db_path, exist_ok=True)
            if new_memory:
                for item in os.listdir(db_path):
                    p = os.path.join(db_path, item)
                    if os.path.isfile(p):
                        os.unlink(p)
                    elif os.path.isdir(p):
                        shutil.rmtree(p)
            import chromadb
            from chromadb.config import Settings
            chroma_client = chromadb.PersistentClient(
                path=db_path, settings=Settings(anonymized_telemetry=False)
            )

        # Visual memory
        visual_memory: VisualMemory
        if new_memory or not visual_memory_path or not os.path.exists(visual_memory_path):
            visual_memory = VisualMemory(output_dir=os.path.dirname(visual_memory_path) if visual_memory_path else None)
        else:
            visual_memory = VisualMemory.load(visual_memory_path)

        self.embedding_provider = ImageEmbeddingProvider(
            model_name=embedding_model, model_path=clip_model_path
        )
        self.vector_db = SpatialVectorDB(
            collection_name=collection_name,
            chroma_client=chroma_client,
            visual_memory=visual_memory,
            embedding_provider=self.embedding_provider,
        )
        self.visual_memory_path = visual_memory_path

        self.last_position: tuple[float, float, float] | None = None
        self.last_record_time: float | None = None
        self.frame_count = 0
        self.stored_frame_count = 0

    def process_frame(
        self,
        frame: np.ndarray,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0, 0, 0),
        timestamp: float | None = None,
    ) -> dict | None:
        """Process a single frame + end-effector pose.

        For SO-101:
          - position = end-effector (x, y, z) from forward kinematics
          - rotation = wrist (roll, pitch, yaw)

        Returns metadata dict if stored, None if skipped.
        """
        self.frame_count += 1

        # Distance gate: skip if the end-effector hasn't moved enough.
        # For a stationary arm, this means the wrist camera viewpoint
        # is looking at roughly the same workspace region.
        if self.last_position is not None:
            dist = np.linalg.norm(np.array(position) - np.array(self.last_position))
            if dist < self.min_distance_threshold:
                return None

        # Time gate
        now = timestamp or time.time()
        if self.last_record_time is not None and (now - self.last_record_time) < self.min_time_threshold:
            return None

        # Compute embedding
        embedding = self.embedding_provider.get_embedding(frame)

        # Deduplication: skip if visually near-identical to existing frames
        if self.stored_frame_count > 0:
            nearest = self.vector_db.query_by_embedding(embedding, limit=1)
            if nearest and nearest[0].get("distance", 1.0) < self.dedup_threshold:
                return None

        # Store
        frame_id = f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "pos_x": float(position[0]),
            "pos_y": float(position[1]),
            "pos_z": float(position[2]),
            "rot_x": float(rotation[0]),
            "rot_y": float(rotation[1]),
            "rot_z": float(rotation[2]),
            "timestamp": now,
            "frame_id": frame_id,
        }
        self.vector_db.add_image_vector(frame_id, frame, embedding, metadata)

        self.last_position = position
        self.last_record_time = now
        self.stored_frame_count += 1

        logger.info(
            f"Stored frame at EE=({position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}), "
            f"{self.stored_frame_count}/{self.frame_count} total"
        )
        return metadata

    def query_by_text(self, text: str, limit: int = 5) -> list[dict]:
        """Query the workspace map by natural language (CLIP text-to-image).

        Example queries for the SO-101 care robot:
          - "aspirin box"
          - "pill tray slot A"
          - "medicine label"
          - "empty workspace"
        """
        robot_pos = None
        if self.last_position:
            robot_pos = (self.last_position[0], self.last_position[1])
        return self.vector_db.query_by_text(text, limit, robot_position=robot_pos)

    def query_by_image(self, image: np.ndarray, limit: int = 5) -> list[dict]:
        """Query the map by image similarity (find when we last saw this)."""
        embedding = self.embedding_provider.get_embedding(image)
        return self.vector_db.query_by_embedding(embedding, limit)

    def query_by_location(self, x: float, y: float, radius: float = 0.1, limit: int = 5) -> list[dict]:
        """Query memories within a radius of end-effector position (x, y).

        For SO-101: useful for "what was in slot A?" where slots have known XY.
        Default radius is 10cm (workspace scale) vs 2m in mobile robot DimOS.
        """
        return self.vector_db.query_by_location(x, y, radius, limit)

    def spatial_range_retrieval(self, x: float, y: float, radius: float, text: str, limit: int = 5) -> list[dict]:
        """Meta-Memory SRR: spatial filter + semantic re-ranking.

        For SO-101: filter by workspace region, then rank by visual similarity.
        Example: spatial_range_retrieval(0.15, 0.0, 0.05, "medicine box")
        → finds medicine-looking frames captured when the arm was near (0.15, 0.0).
        """
        return self.vector_db.spatial_range_retrieval(x, y, radius, text, limit)

    def tag_location(self, name: str, position: tuple[float, float, float], rotation: tuple[float, float, float] = (0, 0, 0)) -> None:
        """Tag a workspace location with a name (e.g., sorting slots).

        Example:
            mem.tag_location("slot_A", position=(0.15, 0.10, 0.05))
            mem.tag_location("medicine_tray", position=(0.20, 0.0, 0.03))
        """
        loc_id = f"loc_{uuid.uuid4().hex[:8]}"
        metadata = {
            "name": name, "pos_x": position[0], "pos_y": position[1], "pos_z": position[2],
            "rot_x": rotation[0], "rot_y": rotation[1], "rot_z": rotation[2],
        }
        self.vector_db.tag_location(name, loc_id, metadata)

    def find_tagged_location(self, query: str, threshold: float = 0.3) -> dict | None:
        """Find a tagged workspace location by semantic text search.

        Example: find_tagged_location("where are the morning pills?")
        → returns metadata for "slot_A" if it was tagged as morning meds.
        """
        meta, distance = self.vector_db.query_tagged_location(query)
        if meta and distance < threshold:
            return meta
        return None

    def save(self) -> None:
        """Persist visual memory to disk."""
        if self.visual_memory_path:
            self.vector_db.visual_memory.save(self.visual_memory_path)

    def get_stats(self) -> dict:
        return {"frame_count": self.frame_count, "stored_frame_count": self.stored_frame_count}
