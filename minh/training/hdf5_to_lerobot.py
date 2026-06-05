"""
Convert Isaac Lab HDF5 teleoperation data to LeRobot format for GR00T fine-tuning.
Copied from SO-ARM Starter with medicine-specific task descriptions.

Usage:
    python -m training.hdf5_to_lerobot \
        --repo_id my_medicine_dataset \
        --hdf5_path /path/to/recording.hdf5 \
        --task_description "Pick up the medicine and place it in the correct slot"
"""

import argparse
import json
import os

import h5py
import numpy as np
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from tqdm import tqdm

# Feature definition for so101_follower
FEATURES = {
    "action": {
        "dtype": "float32",
        "shape": (6,),
        "names": [
            "shoulder_pan.pos",
            "shoulder_lift.pos",
            "elbow_flex.pos",
            "wrist_flex.pos",
            "wrist_roll.pos",
            "gripper.pos",
        ],
    },
    "observation.state": {
        "dtype": "float32",
        "shape": (6,),
        "names": [
            "shoulder_pan.pos",
            "shoulder_lift.pos",
            "elbow_flex.pos",
            "wrist_flex.pos",
            "wrist_roll.pos",
            "gripper.pos",
        ],
    },
    "observation.images.room": {
        "dtype": "video",
        "shape": [480, 640, 3],
        "names": ["height", "width", "channels"],
        "video_info": {
            "video.height": 480,
            "video.width": 640,
            "video.codec": "av1",
            "video.pix_fmt": "yuv420p",
            "video.is_depth_map": False,
            "video.fps": 30.0,
            "video.channels": 3,
            "has_audio": False,
        },
    },
    "observation.images.wrist": {
        "dtype": "video",
        "shape": [480, 640, 3],
        "names": ["height", "width", "channels"],
        "video_info": {
            "video.height": 480,
            "video.width": 640,
            "video.codec": "av1",
            "video.pix_fmt": "yuv420p",
            "video.is_depth_map": False,
            "video.fps": 30.0,
            "video.channels": 3,
            "has_audio": False,
        },
    },
}

# Joint position conversion between IsaacLab and LeRobot coordinate systems
ISAACLAB_JOINT_POS_LIMIT_RANGE = [
    (-110.0, 110.0),
    (-100.0, 100.0),
    (-100.0, 90.0),
    (-95.0, 95.0),
    (-160.0, 160.0),
    (-10, 100.0),
]
LEROBOT_JOINT_POS_LIMIT_RANGE = [
    (-100, 100),
    (-100, 100),
    (-100, 100),
    (-100, 100),
    (-100, 100),
    (0, 100),
]


def preprocess_joint_pos(joint_pos: np.ndarray) -> np.ndarray:
    """Convert simulation joint positions to lerobot coordinate system."""
    joint_pos = joint_pos / np.pi * 180
    for i in range(6):
        isaaclab_min, isaaclab_max = ISAACLAB_JOINT_POS_LIMIT_RANGE[i]
        lerobot_min, lerobot_max = LEROBOT_JOINT_POS_LIMIT_RANGE[i]
        normalized = (joint_pos[:, i] - isaaclab_min) / (isaaclab_max - isaaclab_min)
        joint_pos[:, i] = normalized * (lerobot_max - lerobot_min) + lerobot_min
    return joint_pos


def create_modality_json(dataset_path):
    """Create the modality.json file required for GR00T training."""
    meta_dir = os.path.join(dataset_path, "meta")
    os.makedirs(meta_dir, exist_ok=True)

    modality = {
        "state": {"single_arm": {"start": 0, "end": 5}, "gripper": {"start": 5, "end": 6}},
        "action": {"single_arm": {"start": 0, "end": 5}, "gripper": {"start": 5, "end": 6}},
        "video": {
            "room": {"original_key": "observation.images.room"},
            "wrist": {"original_key": "observation.images.wrist"},
        },
        "annotation": {"human.task_description": {"original_key": "task_index"}},
    }

    modality_path = os.path.join(meta_dir, "modality.json")
    with open(modality_path, "w") as f:
        json.dump(modality, f, indent=4)

    print(f"Created modality.json at: {modality_path}")
    return modality_path


def convert_isaaclab_to_lerobot():
    """Convert Isaac Lab HDF5 data to LeRobot dataset format."""
    parser = argparse.ArgumentParser(description="Convert HDF5 data to LeRobot format")
    parser.add_argument("--repo_id", type=str, default="datasets/medicine_sorting")
    parser.add_argument("--hdf5_path", type=str, required=True)
    parser.add_argument("--robot_type", type=str, default="so101_follower")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--task_description", type=str,
        default="Pick up the medicine and place it in the correct slot",
    )
    parser.add_argument("--push_to_hub", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.hdf5_path):
        raise FileNotFoundError(f"HDF5 file not found: {args.hdf5_path}")

    print(f"Converting: {args.hdf5_path} → {args.repo_id}")
    print(f"Task: {args.task_description}")

    dataset = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        robot_type=args.robot_type,
        features=FEATURES,
    )

    with h5py.File(args.hdf5_path, "r") as f:
        demo_names = list(f["data"].keys())
        print(f"Found {len(demo_names)} demos")

        for demo_name in tqdm(demo_names, desc="Processing demos"):
            demo_group = f["data"][demo_name]
            if "success" in demo_group.attrs and not demo_group.attrs["success"]:
                continue

            try:
                actions = preprocess_joint_pos(np.array(demo_group["obs/actions"]))
                joint_pos = preprocess_joint_pos(np.array(demo_group["obs/joint_pos"]))
                room_images = np.array(demo_group["obs/room"])
                wrist_images = np.array(demo_group["obs/wrist"])
            except KeyError:
                print(f"Demo {demo_name} invalid, skipping")
                continue

            total_frames = actions.shape[0]
            for frame_index in tqdm(range(5, total_frames), desc="Frames", leave=False):
                frame = {
                    "action": actions[frame_index],
                    "observation.state": joint_pos[frame_index],
                    "observation.images.room": room_images[frame_index],
                    "observation.images.wrist": wrist_images[frame_index],
                }
                dataset.add_frame(frame=frame, task=args.task_description)
            dataset.save_episode()

    if args.push_to_hub:
        dataset.push_to_hub()

    create_modality_json(dataset.root)
    print("Conversion complete!")


if __name__ == "__main__":
    convert_isaaclab_to_lerobot()
