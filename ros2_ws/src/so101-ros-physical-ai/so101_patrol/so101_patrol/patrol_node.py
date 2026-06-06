# Copyright 2026 Myron Sydorov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
CareAI patrol node — autonomous left/right sweep for the SO-101 follower arm.

State machine
-------------
  HOMING          Smoothly moves all 6 joints from the measured startup pose to
                  the configured home pose, then transitions to PATROL.
                  (only when use_configured_home=true)

  PATROL          Sweeps shoulder_pan between pan_left and pan_right.
                  All other joints are held at the home position.

  PERSON_DETECTED Person visible on /person_detected.
                  Stops publishing; arm holds last position.
                  Returns to previous state after person_lost_timeout_s.

  RESTING         Activated on Ctrl+C when use_rest_pose=true.
                  Smoothly moves all 6 joints to the configured rest (closed)
                  pose before the process exits.

Subscriptions
-------------
  /person_detected          std_msgs/Bool        True=seen, False=gone
  /follower/joint_states    sensor_msgs/JointState  (startup init only)

Publications
------------
  /follower/forward_controller/commands   std_msgs/Float64MultiArray
  Joint order: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper
"""

import signal
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float64MultiArray

# Joint order expected by /follower/forward_controller/commands.
# Must match forward_controller config in follower_controllers.yaml.
_JOINT_NAMES = [
    "shoulder_pan",    # index 0 — sweeps during patrol
    "shoulder_lift",   # index 1 \
    "elbow_flex",      # index 2  | held at home position during patrol
    "wrist_flex",      # index 3  |
    "wrist_roll",      # index 4  |
    "gripper",         # index 5 /
]


class PatrolNode(Node):
    """Autonomous patrol node for the SO-101 follower arm."""

    _STATE_HOMING = "HOMING"
    _STATE_PATROL = "PATROL"
    _STATE_PERSON = "PERSON_DETECTED"
    _STATE_RESTING = "RESTING"

    def __init__(self) -> None:
        super().__init__("patrol_node")

        # ------------------------------------------------------------------ #
        # Parameters
        # ------------------------------------------------------------------ #
        self.declare_parameter("command_topic", "/follower/forward_controller/commands")
        self.declare_parameter("joint_states_topic", "/follower/joint_states")
        self.declare_parameter("person_detected_topic", "/person_detected")

        # Patrol sweep angles for shoulder_pan (radians).
        # URDF limits: ±1.92 rad.
        self.declare_parameter("shoulder_pan_left", 0.5)
        self.declare_parameter("shoulder_pan_right", -0.5)

        # Maximum joint speed for homing, patrol sweep, and rest motion (rad/s).
        self.declare_parameter("max_speed_rad_s", 0.3)

        # Seconds to wait after person disappears before resuming.
        self.declare_parameter("person_lost_timeout_s", 3.0)

        # Control loop rate (Hz).
        self.declare_parameter("publish_rate_hz", 10.0)

        # How close (rad) to a target before it is considered reached.
        self.declare_parameter("target_tolerance_rad", 0.03)

        # Home pose — arm configuration for patrol.
        # When use_configured_home=true the arm smoothly moves here first.
        # Find values with: ros2 topic echo /follower/joint_states --once
        self.declare_parameter("use_configured_home", False)
        self.declare_parameter("home_shoulder_pan", 0.0)
        self.declare_parameter("home_shoulder_lift", 0.0)
        self.declare_parameter("home_elbow_flex", 0.0)
        self.declare_parameter("home_wrist_flex", 0.0)
        self.declare_parameter("home_wrist_roll", 0.0)
        self.declare_parameter("home_gripper", 0.0)

        # Rest pose — arm returns here smoothly on Ctrl+C.
        # When use_rest_pose=true the arm moves to this pose before exiting.
        self.declare_parameter("use_rest_pose", False)
        self.declare_parameter("rest_shoulder_pan", 0.0)
        self.declare_parameter("rest_shoulder_lift", 0.0)
        self.declare_parameter("rest_elbow_flex", 0.0)
        self.declare_parameter("rest_wrist_flex", 0.0)
        self.declare_parameter("rest_wrist_roll", 0.0)
        self.declare_parameter("rest_gripper", 0.0)

        # ------------------------------------------------------------------ #
        # Read parameters
        # ------------------------------------------------------------------ #
        self._cmd_topic = str(self.get_parameter("command_topic").value)
        self._js_topic = str(self.get_parameter("joint_states_topic").value)
        self._person_topic = str(self.get_parameter("person_detected_topic").value)
        self._pan_left = float(self.get_parameter("shoulder_pan_left").value)
        self._pan_right = float(self.get_parameter("shoulder_pan_right").value)
        self._max_speed = float(self.get_parameter("max_speed_rad_s").value)
        self._person_lost_timeout = float(self.get_parameter("person_lost_timeout_s").value)
        self._rate_hz = float(self.get_parameter("publish_rate_hz").value)
        self._tolerance = float(self.get_parameter("target_tolerance_rad").value)

        self._use_configured_home = bool(self.get_parameter("use_configured_home").value)
        self._home_pose: list[float] = [
            float(self.get_parameter("home_shoulder_pan").value),
            float(self.get_parameter("home_shoulder_lift").value),
            float(self.get_parameter("home_elbow_flex").value),
            float(self.get_parameter("home_wrist_flex").value),
            float(self.get_parameter("home_wrist_roll").value),
            float(self.get_parameter("home_gripper").value),
        ]

        self._use_rest_pose = bool(self.get_parameter("use_rest_pose").value)
        self._rest_pose: list[float] = [
            float(self.get_parameter("rest_shoulder_pan").value),
            float(self.get_parameter("rest_shoulder_lift").value),
            float(self.get_parameter("rest_elbow_flex").value),
            float(self.get_parameter("rest_wrist_flex").value),
            float(self.get_parameter("rest_wrist_roll").value),
            float(self.get_parameter("rest_gripper").value),
        ]

        # ------------------------------------------------------------------ #
        # Runtime state
        # ------------------------------------------------------------------ #
        self._current_pose: list[float] | None = None
        self._target_pan: float = self._pan_left
        self._pre_detection_state: str = self._STATE_PATROL
        self._person_lost_time = None
        self._rest_reached: bool = False

        self._state = self._STATE_HOMING if self._use_configured_home else self._STATE_PATROL

        # ------------------------------------------------------------------ #
        # ROS interfaces
        # ------------------------------------------------------------------ #
        self._cmd_pub = self.create_publisher(Float64MultiArray, self._cmd_topic, 10)
        self.create_subscription(Bool, self._person_topic, self._on_person_detected, 10)
        self.create_subscription(JointState, self._js_topic, self._on_joint_states, 10)

        period = 1.0 / self._rate_hz
        self.create_timer(period, self._control_loop)

        # Startup log
        self.get_logger().info("Starting patrol mode")
        self.get_logger().info(f"  command topic        : {self._cmd_topic}")
        self.get_logger().info(f"  person detect topic  : {self._person_topic}")
        self.get_logger().info(
            f"  patrol sweep         : left={self._pan_left:.3f} rad"
            f"  right={self._pan_right:.3f} rad"
        )
        self.get_logger().info(
            f"  speed                : {self._max_speed:.2f} rad/s"
            f"  rate={self._rate_hz:.0f} Hz"
        )
        self.get_logger().info(f"  person lost timeout  : {self._person_lost_timeout:.1f} s")
        if self._use_configured_home:
            vals = "  ".join(f"{n}={v:+.4f}" for n, v in zip(_JOINT_NAMES, self._home_pose))
            self.get_logger().info(f"  home pose            : {vals}")
        if self._use_rest_pose:
            vals = "  ".join(f"{n}={v:+.4f}" for n, v in zip(_JOINT_NAMES, self._rest_pose))
            self.get_logger().info(f"  rest pose            : {vals}")
        self.get_logger().info("Waiting for first joint state...")

    # ---------------------------------------------------------------------- #
    # Callbacks
    # ---------------------------------------------------------------------- #

    def _on_joint_states(self, msg: JointState) -> None:
        """Record measured arm pose once at startup."""
        if self._current_pose is not None:
            return

        name_to_idx = {name: i for i, name in enumerate(msg.name)}
        pose: list[float] = []
        missing: list[str] = []

        for jname in _JOINT_NAMES:
            if jname in name_to_idx:
                pose.append(float(msg.position[name_to_idx[jname]]))
            else:
                pose.append(0.0)
                missing.append(jname)

        if missing:
            self.get_logger().warn(f"Joints missing from joint_states (using 0.0): {missing}")

        # Always start from the MEASURED position — the HOMING state moves
        # smoothly from here to _home_pose so there is never a jump.
        self._current_pose = pose
        self.get_logger().info(
            "Measured startup pose: "
            + "  ".join(f"{n}={v:+.4f}" for n, v in zip(_JOINT_NAMES, pose))
        )
        if self._use_configured_home:
            self.get_logger().info("Homing: moving smoothly to patrol position...")
        else:
            self.get_logger().info("Publishing left patrol pose")

    def _on_person_detected(self, msg: Bool) -> None:
        """Handle /person_detected messages."""
        # Ignore person detection while homing or resting
        if self._state in (self._STATE_HOMING, self._STATE_RESTING):
            return

        if msg.data:
            if self._state != self._STATE_PERSON:
                self.get_logger().info("Person detected, stopping patrol")
                self._pre_detection_state = self._state
                self._state = self._STATE_PERSON
            self._person_lost_time = None
        else:
            if self._state == self._STATE_PERSON and self._person_lost_time is None:
                self._person_lost_time = self.get_clock().now()

    # ---------------------------------------------------------------------- #
    # Control loop (runs at publish_rate_hz)
    # ---------------------------------------------------------------------- #

    def _control_loop(self) -> None:
        if self._current_pose is None:
            return

        dt = 1.0 / self._rate_hz
        max_step = self._max_speed * dt

        # ------------------------------------------------------------------ #
        # PERSON_DETECTED: hold; check for resume
        # ------------------------------------------------------------------ #
        if self._state == self._STATE_PERSON:
            if self._person_lost_time is not None:
                elapsed = (self.get_clock().now() - self._person_lost_time).nanoseconds * 1e-9
                if elapsed >= self._person_lost_timeout:
                    self.get_logger().info("Person lost, resuming patrol")
                    self._state = self._pre_detection_state
                    self._person_lost_time = None
            return  # forward_controller holds last commanded position

        # ------------------------------------------------------------------ #
        # HOMING / RESTING: smoothly move all 6 joints to target pose
        # ------------------------------------------------------------------ #
        if self._state in (self._STATE_HOMING, self._STATE_RESTING):
            target = self._home_pose if self._state == self._STATE_HOMING else self._rest_pose
            all_reached = True

            for i in range(6):
                error = target[i] - self._current_pose[i]
                if abs(error) > self._tolerance:
                    all_reached = False
                step = max(min(error, max_step), -max_step)
                self._current_pose[i] += step

            msg = Float64MultiArray()
            msg.data = list(self._current_pose)
            self._cmd_pub.publish(msg)

            if all_reached:
                if self._state == self._STATE_HOMING:
                    self.get_logger().info("Home position reached — starting patrol sweep")
                    self._state = self._STATE_PATROL
                    self._target_pan = self._pan_left
                    self.get_logger().info("Publishing left patrol pose")
                else:  # RESTING
                    self.get_logger().info("Rest position reached — ready to shut down")
                    self._rest_reached = True
            return

        # ------------------------------------------------------------------ #
        # PATROL: sweep shoulder_pan; hold all other joints
        # ------------------------------------------------------------------ #
        current_pan = self._current_pose[0]
        error = self._target_pan - current_pan

        if abs(error) < self._tolerance:
            if abs(self._target_pan - self._pan_left) < 1e-9:
                self._target_pan = self._pan_right
                self.get_logger().info("Publishing right patrol pose")
            else:
                self._target_pan = self._pan_left
                self.get_logger().info("Publishing left patrol pose")
            error = self._target_pan - current_pan

        step = max(min(error, max_step), -max_step)
        self._current_pose[0] = current_pan + step

        msg = Float64MultiArray()
        msg.data = list(self._current_pose)
        self._cmd_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PatrolNode()

    # Intercept SIGINT ourselves so rclpy does not shut down its context
    # immediately — this keeps spin_once usable during the rest-pose sequence.
    _stop = [False]

    def _on_sigint(sig, frame):
        _stop[0] = True

    signal.signal(signal.SIGINT, _on_sigint)

    try:
        # Normal spin loop
        while rclpy.ok() and not _stop[0]:
            rclpy.spin_once(node, timeout_sec=0.1)

        # Ctrl+C received — move arm to rest pose before exiting
        if node._use_rest_pose and node._current_pose is not None:
            node.get_logger().info("Shutdown requested — returning to rest position...")
            node._state = node._STATE_RESTING
            node._rest_reached = False
            deadline = time.time() + 30.0
            while rclpy.ok() and not node._rest_reached and time.time() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)

    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
