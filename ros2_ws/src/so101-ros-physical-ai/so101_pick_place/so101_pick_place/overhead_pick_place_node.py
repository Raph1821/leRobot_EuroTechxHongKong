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
CareAI overhead (RealSense) pick-and-place node for the SO-101 follower arm.

Detection
---------
  1. ArUco marker DICT_4X4_50 (attach to bottle — most reliable)
  2. Orange/amber colour blob fallback (bare amber medicine bottle)

Position mapping
----------------
  The overhead camera looks down at the table.  Horizontal pixel offset from
  the image centre is converted to a shoulder_pan correction via:

      pan_correction = (cx - img_cx) * image_to_pan_rad_per_px + camera_to_robot_x

  Tune image_to_pan_rad_per_px until the arm pans to the bottle correctly.
  Flip the sign if it pans the wrong way.

State machine
-------------
  IDLE → RESET → SEARCH_OBJECT → OBJECT_FOUND → MOVE_TO_PREGRASP →
  GRASP (above → lower → close) → LIFT → PLACE (slot → open) → RESET

Subscriptions
-------------
  /static_camera/color/image_raw       sensor_msgs/Image
  /static_camera/depth/image_rect_raw  sensor_msgs/Image   (optional)
  /follower/joint_states               sensor_msgs/JointState

Publications
------------
  /follower/forward_controller/commands  std_msgs/Float64MultiArray
  Joint order: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper
"""

import signal
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import Float64MultiArray

_JOINT_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex",   "wrist_roll",    "gripper",
]


class OverheadPickPlaceNode(Node):
    _STATE_IDLE     = "IDLE"
    _STATE_RESET    = "RESET"
    _STATE_SEARCH   = "SEARCH_OBJECT"
    _STATE_FOUND    = "OBJECT_FOUND"
    _STATE_PREGRASP = "MOVE_TO_PREGRASP"
    _STATE_GRASP    = "GRASP"
    _STATE_LIFT     = "LIFT"
    _STATE_PLACE    = "PLACE"

    def __init__(self) -> None:
        super().__init__("overhead_pick_place_node")

        # ── Parameters ──────────────────────────────────────────────────── #
        self.declare_parameter("image_topic",        "/static_camera/color/image_raw")
        self.declare_parameter("depth_topic",        "/static_camera/depth/image_rect_raw")
        self.declare_parameter("command_topic",      "/follower/forward_controller/commands")
        self.declare_parameter("joint_states_topic", "/follower/joint_states")

        # Camera-to-robot offset tuning (see launch file comments)
        self.declare_parameter("camera_to_robot_x",        0.0)
        self.declare_parameter("camera_to_robot_y",        0.0)
        self.declare_parameter("camera_to_robot_z",        0.0)
        self.declare_parameter("image_to_pan_rad_per_px",  0.003)

        self.declare_parameter("move_speed_rad_s",          0.3)
        self.declare_parameter("publish_rate_hz",          10.0)
        self.declare_parameter("required_detection_frames",  5)

        # Poses: [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
        # shoulder_pan in these poses is the BASE value; detection adds a correction.
        self.declare_parameter("reset_pose",         [ 0.0000, -0.5000,  0.5000,  0.0000,  0.0000,  0.0000])
        self.declare_parameter("pre_grasp_pose",     [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000])
        self.declare_parameter("grasp_pose",         [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000,  0.0000])
        self.declare_parameter("close_gripper_pose", [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000, -0.4000])
        self.declare_parameter("lift_pose",          [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000])
        self.declare_parameter("slot_A_pose",        [ 0.6000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000])
        self.declare_parameter("open_gripper_pose",  [ 0.6000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000])

        # ── Read parameters ──────────────────────────────────────────────── #
        self._img_topic   = str(self.get_parameter("image_topic").value)
        self._dep_topic   = str(self.get_parameter("depth_topic").value)
        self._cmd_topic   = str(self.get_parameter("command_topic").value)
        self._js_topic    = str(self.get_parameter("joint_states_topic").value)

        self._cam_x       = float(self.get_parameter("camera_to_robot_x").value)
        self._cam_y       = float(self.get_parameter("camera_to_robot_y").value)
        self._cam_z       = float(self.get_parameter("camera_to_robot_z").value)
        self._pan_gain    = float(self.get_parameter("image_to_pan_rad_per_px").value)

        self._move_speed  = float(self.get_parameter("move_speed_rad_s").value)
        self._rate_hz     = float(self.get_parameter("publish_rate_hz").value)
        self._req_frames  = int(self.get_parameter("required_detection_frames").value)

        def _p(n): return list(self.get_parameter(n).value)
        self._reset_pose         = _p("reset_pose")
        self._pre_grasp_pose     = _p("pre_grasp_pose")
        self._grasp_pose         = _p("grasp_pose")
        self._close_gripper_pose = _p("close_gripper_pose")
        self._lift_pose          = _p("lift_pose")
        self._slot_A_pose        = _p("slot_A_pose")
        self._open_gripper_pose  = _p("open_gripper_pose")

        # ── Runtime state ────────────────────────────────────────────────── #
        self._current_pose: list[float] | None = None
        self._state        = self._STATE_IDLE
        self._shutdown_mode= False
        self._prev_state   = ""

        self._img_cx       = 424.0   # updated from actual image on first frame
        self._img_cy       = 240.0
        self._last_det: tuple[int, int] | None = None
        self._last_depth: float | None = None
        self._det_cnt      = 0

        # Dynamically computed from detection
        self._above_pose:  list[float] = list(self._pre_grasp_pose)
        self._grasp_adj:   list[float] = list(self._grasp_pose)
        self._close_adj:   list[float] = list(self._close_gripper_pose)

        self._seq_step     = 0

        # ── ArUco detector ───────────────────────────────────────────────── #
        self._bridge = CvBridge()
        try:
            _d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            _p = cv2.aruco.DetectorParameters()
            self._aruco     = cv2.aruco.ArucoDetector(_d, _p)
            self._aruco_new = True
        except AttributeError:
            self._aruco_dict  = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            self._aruco_par   = cv2.aruco.DetectorParameters_create()
            self._aruco_new   = False

        # ── ROS interfaces ────────���──────────────────────────────────────── #
        self._cmd_pub = self.create_publisher(Float64MultiArray, self._cmd_topic, 10)
        self.create_subscription(Image,      self._img_topic, self._on_image,        10)
        self.create_subscription(Image,      self._dep_topic, self._on_depth,        10)
        self.create_subscription(JointState, self._js_topic,  self._on_joint_states, 10)
        self.create_timer(1.0 / self._rate_hz, self._control_loop)

        self.get_logger().info("Overhead pick-and-place node started")
        self.get_logger().info(f"  colour topic  : {self._img_topic}")
        self.get_logger().info(f"  depth topic   : {self._dep_topic}")
        self.get_logger().info(f"  command topic : {self._cmd_topic}")
        self.get_logger().info(f"  pan gain      : {self._pan_gain:.4f} rad/px")
        self.get_logger().info("Waiting for joint states...")

    # ── Callbacks ───────���────────────────────────────────────────────────── #

    def _on_joint_states(self, msg: JointState) -> None:
        if self._current_pose is not None:
            return
        n2i = {n: i for i, n in enumerate(msg.name)}
        self._current_pose = [
            float(msg.position[n2i[j]]) if j in n2i else 0.0
            for j in _JOINT_NAMES
        ]
        self.get_logger().info("Joint states received — moving to reset pose")
        self._state = self._STATE_RESET

    def _on_depth(self, msg: Image) -> None:
        if self._last_det is None:
            return
        try:
            depth_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            cx, cy = self._last_det
            h, w   = depth_img.shape[:2]
            cx = max(0, min(w - 1, cx))
            cy = max(0, min(h - 1, cy))
            raw = float(depth_img[cy, cx])
            if raw > 0:
                # RealSense uint16 depth is in mm
                self._last_depth = raw / 1000.0 if raw > 100 else raw
        except Exception:
            pass

    def _on_image(self, msg: Image) -> None:
        if self._state != self._STATE_SEARCH:
            return
        try:
            img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"Image decode failed: {e}")
            return
        h, w = img.shape[:2]
        self._img_cx = w / 2.0
        self._img_cy = h / 2.0
        self._last_det = self._detect(img)

    # ── Detection ────────────────────────────────────────────────────────── #

    def _detect(self, img) -> tuple[int, int] | None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 1. ArUco
        try:
            if self._aruco_new:
                corners, ids, _ = self._aruco.detectMarkers(gray)
            else:
                corners, ids, _ = cv2.aruco.detectMarkers(
                    gray, self._aruco_dict, parameters=self._aruco_par)
            if ids is not None and len(ids) > 0:
                c = corners[0][0]
                return int(np.mean(c[:, 0])), int(np.mean(c[:, 1]))
        except Exception:
            pass
        # 2. Orange/amber colour blob
        hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([5, 100, 80]), np.array([25, 255, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        largest = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(largest) < 300:
            return None
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None
        return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])

    # ── Position computation ───���─────────────────────────────────────────── #

    def _compute_adjusted_poses(self) -> None:
        """Adjust shoulder_pan of grasp poses based on detected object position."""
        pan_offset = self._cam_x
        if self._last_det is not None:
            cx, cy = self._last_det
            pan_offset += (cx - self._img_cx) * self._pan_gain

        def _adj(base: list[float]) -> list[float]:
            p = list(base)
            p[0] = base[0] + pan_offset
            return p

        self._above_pose = _adj(self._pre_grasp_pose)
        self._grasp_adj  = _adj(self._grasp_pose)
        self._close_adj  = _adj(self._close_gripper_pose)

        depth_str = f"  depth={self._last_depth:.3f}m" if self._last_depth else ""
        self.get_logger().info(
            f"Object found — pixel={self._last_det}  "
            f"pan_correction={pan_offset:+.4f} rad{depth_str}"
        )

    # ── Control loop ──────────────────────��──────────────────────────────── #

    def _log_state_entry(self, msg: str) -> None:
        if self._state != self._prev_state:
            self.get_logger().info(msg)
            self._prev_state = self._state

    def _control_loop(self) -> None:
        if self._current_pose is None:
            return

        dt       = 1.0 / self._rate_hz
        max_step = self._move_speed * dt

        # RESET ─────────────────────────────────────────────────────────────
        if self._state == self._STATE_RESET:
            self._log_state_entry("Returning to reset pose")
            self._move_toward(self._reset_pose, max_step)
            if self._near(self._current_pose, self._reset_pose):
                if not self._shutdown_mode:
                    self.get_logger().info("Searching for object...")
                    self._state   = self._STATE_SEARCH
                    self._det_cnt = 0
                    self._last_det = None
            return

        # SEARCH_OBJECT ────────────────────���────────────────────────────────
        if self._state == self._STATE_SEARCH:
            if self._last_det is not None:
                self._det_cnt += 1
                if self._det_cnt >= self._req_frames:
                    self._compute_adjusted_poses()
                    self._state    = self._STATE_PREGRASP
                    self._seq_step = 0
            else:
                self._det_cnt = 0
            return

        # MOVE_TO_PREGRASP ──────���───────────────────────────────��───────────
        if self._state == self._STATE_PREGRASP:
            self._log_state_entry("Moving to pre-grasp pose")
            self._move_toward(self._pre_grasp_pose, max_step)
            if self._near(self._current_pose, self._pre_grasp_pose):
                self.get_logger().info("Moving to grasp position above object")
                self._state    = self._STATE_GRASP
                self._seq_step = 0
            return

        # GRASP: hover above → lower to grasp → close gripper ──────────────
        if self._state == self._STATE_GRASP:
            grasp_seq = [
                (self._above_pose, "above object"),
                (self._grasp_adj,  "at grasp position"),
                (self._close_adj,  "closing gripper"),
            ]
            if self._seq_step >= len(grasp_seq):
                self.get_logger().info("Lifting object")
                self._state    = self._STATE_LIFT
                self._seq_step = 0
                return
            target, label = grasp_seq[self._seq_step]
            self._move_toward(target, max_step)
            if self._near(self._current_pose, target):
                self.get_logger().info(f"  {label}")
                self._seq_step += 1
            return

        # LIFT ─────��──────────────────────────────���─────────────────────────
        if self._state == self._STATE_LIFT:
            self._log_state_entry("Lifting object")
            self._move_toward(self._lift_pose, max_step)
            if self._near(self._current_pose, self._lift_pose):
                self.get_logger().info("Moving to slot A")
                self._state    = self._STATE_PLACE
                self._seq_step = 0
            return

        # PLACE: move to slot → open gripper ────────────────────────────────
        if self._state == self._STATE_PLACE:
            place_seq = [
                (self._slot_A_pose,     "at slot A"),
                (self._open_gripper_pose, "opening gripper"),
            ]
            if self._seq_step >= len(place_seq):
                self.get_logger().info("Returning to reset pose")
                self._state    = self._STATE_RESET
                self._seq_step = 0
                return
            target, label = place_seq[self._seq_step]
            self._move_toward(target, max_step)
            if self._near(self._current_pose, target):
                self.get_logger().info(f"  {label}")
                self._seq_step += 1
            return

    # ── Helpers ────��──────────────────────────────��──────────────────────── #

    def _move_toward(self, target: list[float], max_step: float) -> None:
        for i in range(6):
            err = target[i] - self._current_pose[i]
            self._current_pose[i] += max(min(err, max_step), -max_step)
        self._publish()

    def _near(self, a: list[float], b: list[float], tol: float = 0.03) -> bool:
        return all(abs(x - y) <= tol for x, y in zip(a, b))

    def _publish(self) -> None:
        msg = Float64MultiArray()
        msg.data = list(self._current_pose)
        self._cmd_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OverheadPickPlaceNode()

    _stop = [False]

    def _sigint(sig, frame):
        _stop[0] = True

    signal.signal(signal.SIGINT, _sigint)

    try:
        while rclpy.ok() and not _stop[0]:
            rclpy.spin_once(node, timeout_sec=0.1)

        if node._current_pose is not None:
            node.get_logger().info("Stopping — returning to reset position")
            node._shutdown_mode = True
            node._state         = node._STATE_RESET
            deadline = time.time() + 30.0
            while rclpy.ok() and time.time() < deadline:
                rclpy.spin_once(node, timeout_sec=0.1)
                if node._near(node._current_pose, node._reset_pose):
                    node.get_logger().info("Reset position reached — shutting down")
                    break
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
