"""
GR00T Inference App for Medicine Robot — adapted from so_arm_starter.

This runs the full real-hardware deployment pipeline:
  Camera → Robot Status → GR00T Inference → Robot Actions
"""

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

import numpy as np
import yaml
from holoscan.core import Application
from holoscan_apps.operators import GR00TInferenceOp, RobotStatusOp
from lerobot.common.cameras.opencv import OpenCVCameraConfig
from lerobot.common.robots.so101_follower import SO101FollowerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GR00TMedicineApplication(Application):
    """Holoscan application for GR00T-controlled medicine robot."""

    def __init__(self, config_path: str = None):
        super().__init__()
        self.config_path = config_path
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def compose(self):
        robot_config = self._create_robot_config()
        gr00t_policy = self._create_policy()

        robot_status_op = RobotStatusOp(self, robot_config=robot_config, name="robot_status")
        gr00t_inference_op = GR00TInferenceOp(
            self,
            policy=gr00t_policy,
            language_instruction=self.config["gr00t"]["language_instruction"],
            action_horizon=self.config["gr00t"]["action_horizon"],
            robot_status_op=robot_status_op,
            name="gr00t_inference",
        )
        self.add_flow(robot_status_op, gr00t_inference_op, {("robot_status", "robot_status")})
        logger.info("Medicine robot application composed.")

    def _create_robot_config(self):
        camera_configs = {}
        for name, cam_config in self.config["robot"]["cameras"].items():
            cam_config_copy = dict(cam_config)
            cam_config_copy.pop("type", None)
            camera_configs[name] = OpenCVCameraConfig(**cam_config_copy)

        return SO101FollowerConfig(
            port=self.config["robot"]["port"],
            id=self.config["robot"]["id"],
            cameras=camera_configs,
        )

    def _create_policy(self):
        from gr00t.data.embodiment_tags import EmbodimentTag
        from gr00t.policy.gr00t_policy import Gr00tPolicy

        model_path = self.config["gr00t"]["model_path"]
        embodiment_tag = self.config["gr00t"].get("embodiment_tag", "new_embodiment")

        policy = Gr00tPolicy(
            embodiment_tag=EmbodimentTag.resolve(embodiment_tag),
            model_path=model_path,
            device="cuda",
        )
        logger.info("GR00T N1.7 model loaded for medicine robot.")

        # Wrap in adapter for flat obs format
        class _Adapter:
            def __init__(self, p):
                self._policy = p
                self._language_key = p.language_key

            def get_action(self, flat_obs):
                nested = {"video": {}, "state": {}, "language": {}}
                for k, v in flat_obs.items():
                    if k.startswith("video."):
                        arr = np.asarray(v)
                        if arr.dtype != np.uint8:
                            arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
                        nested["video"][k[len("video."):]] = arr
                    elif k.startswith("state."):
                        nested["state"][k[len("state."):]] = np.asarray(v, dtype=np.float32)
                    elif k.startswith("annotation.") or k == "task_description":
                        if isinstance(v, list) and v and isinstance(v[0], str):
                            nested["language"][self._language_key] = [[s] for s in v]
                        elif isinstance(v, str):
                            nested["language"][self._language_key] = [[v]]
                        else:
                            nested["language"][self._language_key] = v
                action_dict, _ = self._policy.get_action(nested)
                return {f"action.{key}": action_dict[key] for key in action_dict}

        return _Adapter(policy)


def main():
    parser = argparse.ArgumentParser(description="Medicine Robot GR00T App")
    parser.add_argument(
        "--config", type=str,
        default=f"{os.path.dirname(os.path.abspath(__file__))}/medicine_robot_config.yaml",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    app = GR00TMedicineApplication(config_path=args.config)
    logger.info("Starting medicine robot application...")
    app.run()


if __name__ == "__main__":
    main()
