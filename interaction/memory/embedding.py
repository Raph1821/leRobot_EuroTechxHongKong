"""
Image embedding provider — generates CLIP embeddings for images and text.

Decoupled from dimos; only requires: transformers, onnxruntime, PIL, numpy, cv2.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Default CLIP ONNX model path — override via env or constructor arg.
DEFAULT_CLIP_MODEL = os.environ.get("CLIP_MODEL_PATH", "")


class ImageEmbeddingProvider:
    """Generates CLIP embeddings for images and text queries."""

    def __init__(self, model_name: str = "clip", dimensions: int = 512, model_path: str | None = None):
        self.model_name = model_name
        self.dimensions = dimensions
        self.model = None
        self.processor = None
        self.model_path = model_path or DEFAULT_CLIP_MODEL
        self._initialize_model()

    def _initialize_model(self):
        import onnxruntime as ort
        from transformers import CLIPProcessor

        if self.model_name == "clip":
            if self.model_path and os.path.exists(self.model_path):
                onnx_path = self.model_path
            else:
                # Try common locations
                candidates = [
                    Path.home() / ".cache" / "clip" / "model.onnx",
                    Path("data/models_clip/model.onnx"),
                ]
                onnx_path = next((str(p) for p in candidates if p.exists()), None)
                if not onnx_path:
                    raise FileNotFoundError(
                        "CLIP ONNX model not found. Set CLIP_MODEL_PATH env var or "
                        "download from HuggingFace."
                    )

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self.model = ort.InferenceSession(onnx_path, providers=providers)
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            logger.info(f"Loaded CLIP: {onnx_path}, providers: {self.model.get_providers()}")
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")

    def get_embedding(self, image: np.ndarray | str | bytes) -> np.ndarray:
        """Generate a normalized embedding vector for an image."""
        if self.model is None:
            return np.random.randn(self.dimensions).astype(np.float32)

        pil_image = self._to_pil(image)
        inputs = self.processor(images=pil_image, return_tensors="np")

        ort_inputs = {
            inp.name: inputs[inp.name]
            for inp in self.model.get_inputs()
            if inp.name in inputs
        }
        input_names = [i.name for i in self.model.get_inputs()]
        batch_size = inputs["pixel_values"].shape[0]
        if "input_ids" in input_names:
            ort_inputs["input_ids"] = np.zeros((batch_size, 1), dtype=np.int64)
        if "attention_mask" in input_names:
            ort_inputs["attention_mask"] = np.ones((batch_size, 1), dtype=np.int64)

        ort_outputs = self.model.run(None, ort_inputs)
        output_names = [o.name for o in self.model.get_outputs()]

        if "image_embeds" in output_names:
            embedding = ort_outputs[output_names.index("image_embeds")]
        else:
            raise RuntimeError(f"No 'image_embeds' in outputs: {output_names}")

        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        return embedding[0]

    def get_text_embedding(self, text: str) -> np.ndarray:
        """Generate a normalized embedding vector for text (CLIP text encoder)."""
        if self.model is None or self.model_name != "clip":
            return np.random.randn(self.dimensions).astype(np.float32)

        inputs = self.processor(text=[text], return_tensors="np", padding=True)
        ort_inputs = {
            inp.name: inputs[inp.name]
            for inp in self.model.get_inputs()
            if inp.name in inputs
        }
        input_names = [i.name for i in self.model.get_inputs()]
        batch_size = inputs["input_ids"].shape[0]
        if "pixel_values" in input_names:
            ort_inputs["pixel_values"] = np.zeros((batch_size, 3, 224, 224), dtype=np.float32)

        ort_outputs = self.model.run(None, ort_inputs)
        output_names = [o.name for o in self.model.get_outputs()]

        if "text_embeds" in output_names:
            embedding = ort_outputs[output_names.index("text_embeds")]
        else:
            embedding = ort_outputs[0]

        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        return embedding[0]

    def _to_pil(self, image: np.ndarray | str | bytes) -> Image.Image:
        if isinstance(image, np.ndarray):
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return Image.fromarray(image)
        elif isinstance(image, str):
            if os.path.isfile(image):
                return Image.open(image)
            return Image.open(io.BytesIO(base64.b64decode(image)))
        elif isinstance(image, bytes):
            return Image.open(io.BytesIO(image))
        raise ValueError(f"Unsupported image type: {type(image)}")
