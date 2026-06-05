"""GR00T N1.7 Policy Runner — copied from so_arm_starter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import torch
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.policy.gr00t_policy import Gr00tPolicy


class GR00TN1_7_PolicyRunner:
    """Policy runner for GR00T N1.7 policy.

    Supports both PyTorch and TensorRT inference modes.
    """

    def __init__(
        self,
        ckpt_path: str,
        embodiment_tag: str = "new_embodiment",
        task_description: str = "Pick up the medicine and place it in the correct slot",
        device: str = "cuda",
        trt_engine_path: str | None = None,
        trt_mode: str = "n17_full_pipeline",
    ):
        if not torch.cuda.is_available():
            raise RuntimeError("Deployment of GR00T N1.7 requires NVIDIA GPU with CUDA 12.0+")

        print(f"Loading GR00T N1.7 model from {ckpt_path} ...")
        self.model = Gr00tPolicy(
            embodiment_tag=EmbodimentTag.resolve(embodiment_tag),
            model_path=ckpt_path,
            device=device,
        )
        self.task_description = task_description
        self._language_key = self.model.language_key
        print(f"GR00T N1.7 model loaded successfully (language_key={self._language_key!r}).")

        if trt_engine_path is not None:
            self._setup_trt(self.model, trt_engine_path, trt_mode)

    @staticmethod
    def _setup_trt(policy, trt_engine_path: str, mode: str) -> None:
        groot_root = Path(__file__).resolve().parents[5] / "third_party" / "Isaac-GR00T"
        trt_fwd = groot_root / "scripts" / "deployment" / "trt_model_forward.py"

        spec = importlib.util.spec_from_file_location("trt_model_forward", trt_fwd)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot find {trt_fwd}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        print(f"Setting up TensorRT engines from {trt_engine_path} (mode={mode}) ...")
        mod.setup_tensorrt_engines(policy, trt_engine_path, mode=mode)
        print("TensorRT engines loaded successfully.")

    def infer(
        self,
        room_img: np.ndarray,
        wrist_img: np.ndarray,
        current_state: np.ndarray,
    ) -> torch.Tensor:
        """Run a single inference step.

        Returns:
            Tensor of shape (chunk_length, 6) — [single_arm (5), gripper (1)] per step.
        """
        obs = {
            "video": {
                "room": room_img[np.newaxis, np.newaxis].astype(np.uint8),
                "wrist": wrist_img[np.newaxis, np.newaxis].astype(np.uint8),
            },
            "state": {
                "single_arm": np.array(current_state[:5], dtype=np.float32)[np.newaxis, np.newaxis],
                "gripper": np.array(current_state[5:6], dtype=np.float32)[np.newaxis, np.newaxis],
            },
            "language": {
                self._language_key: [[self.task_description]],
            },
        }

        action_dict, _info = self.model.get_action(obs)

        single_arm = action_dict.get("single_arm")
        gripper = action_dict.get("gripper")

        if single_arm is None or gripper is None:
            raise ValueError(f"Missing action keys. Available: {list(action_dict.keys())}")

        if isinstance(single_arm, np.ndarray):
            single_arm = torch.from_numpy(single_arm)
        if isinstance(gripper, np.ndarray):
            gripper = torch.from_numpy(gripper)

        if single_arm.dim() == 3:
            single_arm = single_arm.squeeze(0)
        if gripper.dim() == 3:
            gripper = gripper.squeeze(0)
        if gripper.dim() == 1:
            gripper = gripper.unsqueeze(-1)

        return torch.cat([single_arm, gripper], dim=-1)
