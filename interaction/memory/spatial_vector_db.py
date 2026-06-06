"""
Spatial Vector Database — stores image embeddings mapped to (x, y, θ) locations.

Uses ChromaDB with cosine similarity. Supports:
  - query by embedding (image similarity)
  - query by text (CLIP cross-modal)
  - query by location (radius filter)
  - spatial-range retrieval with semantic re-ranking (Meta-Memory SRR)
  - tagged named locations
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from interaction.memory.embedding import ImageEmbeddingProvider
from interaction.memory.visual_memory import VisualMemory

logger = logging.getLogger(__name__)


class SpatialVectorDB:
    """Vector DB for semantic spatial memory — images mapped to XY positions."""

    def __init__(
        self,
        collection_name: str = "spatial_memory",
        chroma_client=None,
        visual_memory: VisualMemory | None = None,
        embedding_provider: ImageEmbeddingProvider | None = None,
    ):
        import chromadb

        self.client = chroma_client or chromadb.Client()
        self.image_collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        self.location_collection = self.client.get_or_create_collection(
            name=f"{collection_name}_locations", metadata={"hnsw:space": "cosine"}
        )
        self.visual_memory = visual_memory or VisualMemory()
        self.embedding_provider = embedding_provider

    def add_image_vector(
        self, vector_id: str, image: np.ndarray, embedding: np.ndarray, metadata: dict[str, Any]
    ) -> None:
        """Store an image with its embedding and position metadata."""
        self.visual_memory.add(vector_id, image)
        self.image_collection.add(
            ids=[vector_id], embeddings=[embedding.tolist()], metadatas=[metadata]
        )

    def query_by_embedding(self, embedding: np.ndarray, limit: int = 5) -> list[dict]:
        results = self.image_collection.query(
            query_embeddings=[embedding.tolist()], n_results=limit
        )
        return self._process_results(results)

    def query_by_text(
        self, text: str, limit: int = 5, robot_position: tuple[float, float] | None = None
    ) -> list[dict]:
        """Query by text with coarse-to-fine re-ranking using spatial proximity."""
        if self.embedding_provider is None:
            self.embedding_provider = ImageEmbeddingProvider()

        text_embedding = self.embedding_provider.get_text_embedding(text)
        coarse_limit = limit * 3 if robot_position else limit

        results = self.image_collection.query(
            query_embeddings=[text_embedding.tolist()],
            n_results=coarse_limit,
            include=["metadatas", "distances"],
        )

        # Fine re-ranking with spatial proximity bonus
        if robot_position and results and results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            scored = []
            for i in range(len(ids)):
                semantic_score = 1.0 - distances[i]
                meta = metadatas[i]
                px, py = meta.get("pos_x"), meta.get("pos_y")
                spatial_bonus = 0.0
                if px is not None and py is not None:
                    spatial_dist = np.sqrt(
                        (robot_position[0] - px) ** 2 + (robot_position[1] - py) ** 2
                    )
                    spatial_bonus = 0.05 / (1.0 + spatial_dist)
                scored.append((i, semantic_score + spatial_bonus))

            scored.sort(key=lambda x: x[1], reverse=True)
            top = [s[0] for s in scored[:limit]]
            results = {
                "ids": [[ids[i] for i in top]],
                "metadatas": [[metadatas[i] for i in top]],
                "distances": [[distances[i] for i in top]],
            }

        return self._process_results(results)

    def query_by_location(self, x: float, y: float, radius: float = 2.0, limit: int = 5) -> list[dict]:
        """Query by Euclidean proximity to (x, y)."""
        results = self.image_collection.get(include=["metadatas"])
        if not results or not results["ids"]:
            return []

        filtered = {"ids": [], "metadatas": [], "distances": []}
        for i, meta in enumerate(results["metadatas"]):
            px, py = meta.get("pos_x"), meta.get("pos_y")
            if px is None or py is None:
                continue
            dist = np.sqrt((x - px) ** 2 + (y - py) ** 2)
            if dist <= radius:
                filtered["ids"].append(results["ids"][i])
                filtered["metadatas"].append(meta)
                filtered["distances"].append(dist)

        indices = np.argsort(filtered["distances"])[:limit]
        return [
            {"id": filtered["ids"][i], "metadata": filtered["metadatas"][i], "distance": filtered["distances"][i]}
            for i in indices
        ]

    def spatial_range_retrieval(
        self, x: float, y: float, radius: float, text_query: str, limit: int = 5
    ) -> list[dict]:
        """Meta-Memory SRR: filter by radius, then re-rank by text similarity."""
        if self.embedding_provider is None:
            self.embedding_provider = ImageEmbeddingProvider()

        results = self.image_collection.get(include=["metadatas", "embeddings"])
        if not results or not results["ids"]:
            return []

        candidates = []
        for i, meta in enumerate(results["metadatas"]):
            px, py = meta.get("pos_x"), meta.get("pos_y")
            if px is None or py is None:
                continue
            if np.sqrt((x - px) ** 2 + (y - py) ** 2) <= radius:
                candidates.append((results["ids"][i], results["embeddings"][i], meta))

        if not candidates:
            return []

        text_emb = self.embedding_provider.get_text_embedding(text_query)
        scored = [
            (c[0], c[2], float(np.dot(text_emb, np.array(c[1]))))
            for c in candidates
        ]
        scored.sort(key=lambda x: x[2], reverse=True)

        return [
            {"id": s[0], "metadata": s[1], "distance": 1.0 - s[2]}
            for s in scored[:limit]
        ]

    def tag_location(self, name: str, location_id: str, metadata: dict) -> None:
        """Tag a named location for text-based retrieval."""
        self.location_collection.add(
            ids=[location_id], documents=[name], metadatas=[metadata]
        )

    def query_tagged_location(self, query: str) -> tuple[dict | None, float]:
        """Find the best matching tagged location by semantic text search."""
        results = self.location_collection.query(
            query_texts=[query], n_results=1, include=["metadatas", "distances"]
        )
        if not (results and results["ids"] and results["ids"][0]):
            return None, 1.0
        return results["metadatas"][0][0], float(results["distances"][0][0])

    def _process_results(self, results) -> list[dict]:
        if not results or not results["ids"]:
            return []
        processed = []
        for i, vid in enumerate(results["ids"]):
            lookup_id = vid[0] if isinstance(vid, list) else vid
            result = {"id": lookup_id}
            if "metadatas" in results:
                m = results["metadatas"][i]
                result["metadata"] = m[0] if isinstance(m, list) else m
            if "distances" in results:
                d = results["distances"][i]
                result["distance"] = d[0] if isinstance(d, list) else d
            processed.append(result)
        return processed
