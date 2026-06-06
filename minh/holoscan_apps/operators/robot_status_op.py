"""Robot Status Operator — copied from so_arm_starter."""

import logging
import time

from holoscan.conditions import PeriodicCondition
from holoscan.core import Operator, OperatorSpec
from lerobot.common.robots import make_robot_from_config

logger = logging.getLogger(__name__)


class RobotStatusOp(Operator):
    """Robot status operator - gets observations and sends to GR00T"""

    def __init__(self, fragment, robot_config=None, **kwargs):
        periodic_condition = PeriodicCondition(fragment, recess_period=100, name="robot_status")
        super().__init__(fragment, periodic_condition, **kwargs)
        self.robot_config = robot_config
        self.robot = None
        self.camera_keys = []
        self.robot_state_keys = []
        self.cycle_count = 0
        self.running = True
        self.action_in_progress = False
        self.last_action_time = 0

    def setup(self, spec: OperatorSpec):
        spec.output("robot_status")

    def start(self):
        logger.info("=== Initializing Robot Status Operator ===")
        try:
            if self.robot_config:
                self.robot = make_robot_from_config(self.robot_config)
                self.robot.connect()
                self.camera_keys = list(self.robot_config.cameras.keys())
                self.robot_state_keys = list(self.robot._motors_ft.keys())
                logger.info(f"Robot connected: {self.robot_config.type}")
            else:
                raise ValueError("No robot config provided")
        except Exception as e:
            logger.error(f"Failed to initialize robot: {e}")
            raise

    def compute(self, op_input, op_output, context):
        if not self.running or not self.robot:
            return
        try:
            self.cycle_count += 1
            current_time = time.time()

            if self.action_in_progress:
                if current_time - self.last_action_time > 2.0:
                    self.action_in_progress = False
                else:
                    return

            observation_dict = self.robot.get_observation()
            status_data = {
                "observation": observation_dict,
                "camera_keys": self.camera_keys,
                "robot_state_keys": self.robot_state_keys,
                "cycle_id": self.cycle_count,
                "timestamp": current_time,
            }
            op_output.emit(status_data, "robot_status")
        except Exception as e:
            logger.error(f"Error in robot status cycle {self.cycle_count}: {e}")

    def set_action_in_progress(self, in_progress=True):
        self.action_in_progress = in_progress
        if in_progress:
            self.last_action_time = time.time()
