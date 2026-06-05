"""
GR00T N1.7 Fine-tuning Script for Medicine Robot.
Wraps Isaac-GR00T's launch_finetune.py with convenient CLI.

Usage:
    python -m training.gr00t_n1_7.train \
        --dataset_path /path/to/lerobot/dataset \
        --output_dir /path/to/checkpoints \
        --max_steps 10000 \
        --batch_size 32
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal

import torch
import tyro


@dataclass
class ArgsConfig:
    """Configuration for GR00T N1.7 fine-tuning."""

    dataset_path: List[str]
    """Path to the dataset directory (LeRobot format)."""

    output_dir: str = "/tmp/gr00t_n1_7_medicine"
    """Directory to save model checkpoints."""

    base_model_path: str = "nvidia/GR00T-N1.7-3B"
    """Path or HuggingFace model ID for the base model."""

    embodiment_tag: str = "new_embodiment"
    """Embodiment tag to use for training."""

    batch_size: int = 32
    """Global batch size for training."""

    max_steps: int = 10000
    """Maximum number of training steps."""

    num_gpus: int = 1
    """Number of GPUs to use for training."""

    save_steps: int = 1000
    """Steps between checkpoints."""

    tune_llm: bool = False
    """Whether to fine-tune the language model backbone."""

    tune_visual: bool = False
    """Whether to fine-tune the vision tower."""

    tune_projector: bool = True
    """Whether to fine-tune the projector."""

    tune_diffusion_model: bool = True
    """Whether to fine-tune the diffusion model."""

    learning_rate: float = 1e-4
    """Learning rate."""

    weight_decay: float = 1e-5
    """Weight decay for AdamW."""

    warmup_ratio: float = 0.05
    """Warmup ratio."""

    dataloader_num_workers: int = 8
    """Data loading workers."""

    report_to: Literal["wandb", "tensorboard"] = "tensorboard"
    """Metrics reporting destination."""

    video_backend: Literal["decord", "torchvision_av", "torchcodec"] = "torchcodec"
    """Video backend."""

    modality_config_path: str | None = None
    """Path to custom modality config. If None, uses default so_arm_config."""

    state_dropout_prob: float = 0.2
    """State input dropout probability."""


def _find_groot_root() -> Path:
    """Resolve Isaac-GR00T repo root. Adjust this path based on your setup."""
    # Try relative to this file first
    candidate = Path(__file__).resolve().parents[4] / "third_party" / "Isaac-GR00T"
    if candidate.exists():
        return candidate
    # Fallback: check environment variable
    import os
    groot_path = os.environ.get("ISAAC_GROOT_PATH")
    if groot_path and Path(groot_path).exists():
        return Path(groot_path)
    raise FileNotFoundError(
        "Isaac-GR00T not found. Set ISAAC_GROOT_PATH env var or ensure "
        "third_party/Isaac-GR00T exists relative to workspace."
    )


def main(config: ArgsConfig):
    groot_root = _find_groot_root()
    launch_script = groot_root / "gr00t" / "experiment" / "launch_finetune.py"

    if not launch_script.exists():
        raise FileNotFoundError(f"launch_finetune.py not found at {launch_script}")

    cmd = [
        sys.executable,
        str(launch_script),
        "--base_model_path", config.base_model_path,
        "--dataset_path", config.dataset_path[0],
        "--embodiment_tag", config.embodiment_tag,
        "--output_dir", config.output_dir,
        "--save_steps", str(config.save_steps),
        "--max_steps", str(config.max_steps),
        "--warmup_ratio", str(config.warmup_ratio),
        "--weight_decay", str(config.weight_decay),
        "--learning_rate", str(config.learning_rate),
        "--global_batch_size", str(config.batch_size),
        "--dataloader_num_workers", str(config.dataloader_num_workers),
        "--num_gpus", str(config.num_gpus),
        "--state_dropout_prob", str(config.state_dropout_prob),
    ]

    if config.tune_llm:
        cmd.append("--tune_llm")
    if config.tune_visual:
        cmd.append("--tune_visual")
    if not config.tune_projector:
        cmd.append("--no-tune_projector")
    if not config.tune_diffusion_model:
        cmd.append("--no-tune_diffusion_model")
    if config.modality_config_path:
        cmd.extend(["--modality_config_path", str(Path(config.modality_config_path).resolve())])
    if config.report_to == "wandb":
        cmd.append("--use_wandb")

    print("=" * 60)
    print("GR00T N1.7 Fine-Tuning (Medicine Robot)")
    print("=" * 60)
    for key, value in vars(config).items():
        print(f"  {key}: {value}")
    print("=" * 60)

    sys.exit(subprocess.run(cmd, cwd=str(groot_root)).returncode)


if __name__ == "__main__":
    config = tyro.cli(ArgsConfig)
    available_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 1
    assert config.num_gpus <= available_gpus
    main(config)
