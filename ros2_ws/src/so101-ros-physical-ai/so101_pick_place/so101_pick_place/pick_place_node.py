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
CareAI wrist-camera pick-and-place node for the SO-101 follower arm.

State machine
-------------
  IDLE            Waiting for first joint state message.

  RESET           Smoothly moves all 6 joints to reset_pose, then → SEARCH.
                  Also activated on Ctrl+C (shutdown_mode=True, no SEARCH after).

  SEARCH_OBJECT   Sweeps shoulder_pan left/right looking for the object.
                  Transitions to CENTER_OBJECT when object is detected.

  CENTER_OBJECT   Servos shoulder_pan and shoulder_lift so the object centroid
                  reaches the image centre within centre_tolerance_px.
                  After required_centered_frames consecutive centred frames → GRASP.

  GRASP           Executes the fixed pose sequence:
                    pre_grasp → approach → close_gripper → lift → place →
                    open_gripper → reset
                  Then loops back to SEARCH_OBJECT.

Detection (priority order)
--------------------------
  1. ArUco marker (DICT_4X4_50, any ID) — attach to medicine bottle.
  2. Orange/amber colour blob — works bare for most amber medicine bottles.

Subscriptions
-------------
  /follower/image_raw              sensor_msgs/Image
  /follower/joint_states           sensor_msgs/JointState  (startup init only)

Publications
------------
  /follower/forward_controller/commands   std_msgs/Float64MultiArray
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
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

_PAN_SEARCH_LIMITS  = (-1.2,  1.2)   # shoulder_pan sweep range during SEARCH
_PAN_SERVO_LIMITS   = (-1.5,  1.5)   # shoulder_pan clamp during CENTER
_LIFT_SERVO_LIMITS  = (-2.0,  0.0)   # shoulder_lift clamp during CENTER


class PickPlaceNode(Node):
    _STATE_IDLE   = "IDLE"
    _STATE_RESET  = "RESET"
    _STATE_SEARCH = "SEARCH_OBJECT"
    _STATE_CENTER = "CENTER_OBJECT"
    _STATE_GRASP  = "GRASP"

    def __init__(self) -> None:
        super().__init__("pick_place_node")

        # ── Parameters ──────────────────────────────────────────────────── #
        self.declare_parameter("image_topic",         "/follower/image_raw")
        self.declare_parameter("command_topic",       "/follower/forward_controller/commands")
        self.declare_parameter("joint_states_topic",  "/follower/joint_states")

        self.declare_parameter("center_tolerance_px",      30.0)
        self.declare_parameter("required_centered_frames",  10)
        self.declare_parameter("servo_step_size",            0.02)
        # Flip to -1.0 if centering moves the arm the wrong way.
        self.declare_parameter("pan_servo_sign",             1.0)
        self.declare_parameter("tilt_servo_sign",            1.0)
        self.declare_parameter("move_speed_rad_s",           0.3)
        self.declare_parameter("publish_rate_hz",           10.0)

        # Poses — [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
        self.declare_parameter("reset_pose",         [-0.0844, -1.8270,  1.6659,  1.1612,  0.0614,  0.0015])
        self.declare_parameter("pre_grasp_pose",     [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000])
        self.declare_parameter("approach_pose",      [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000,  0.0000])
        self.declare_parameter("close_gripper_pose", [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000, -0.4000])
        self.declare_parameter("lift_pose",          [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000])
        self.declare_parameter("place_pose",         [ 0.5000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000])
        self.declare_parameter("open_gripper_pose",  [ 0.5000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000])

        # ── Read parameters ──────────────────────────────────────────────── #
        self._img_topic   = str(self.get_parameter("image_topic").value)
        self._cmd_topic   = str(self.get_parameter("command_topic").value)
        self._js_topic    = str(self.get_parameter("joint_states_topic").value)

        self._tol_px      = float(self.get_parameter("center_tolerance_px").value)
        self._req_frames  = int(self.get_parameter("required_centered_frames").value)
        self._servo_step  = float(self.get_parameter("servo_step_size").value)
        self._pan_sign    = float(self.get_parameter("pan_servo_sign").value)
        self._tilt_sign   = float(self.get_parameter("tilt_servo_sign").value)
        self._move_speed  = float(self.get_parameter("move_speed_rad_s").value)
        self._rate_hz     = float(self.get_parameter("publish_rate_hz").value)

        def _pose(name): return list(self.get_parameter(name).value)
        self._reset_pose         = _pose("reset_pose")
        self._pre_grasp_pose     = _pose("pre_grasp_pose")
        self._approach_pose      = _pose("approach_pose")
        self._close_gripper_pose = _pose("close_gripper_pose")
        self._lift_pose          = _pose("lift_pose")
        self._place_pose         = _pose("place_pose")
        self._open_gripper_pose  = _pose("open_gripper_pose")

        # ── Runtime state ────────────────────────────────────────────────── #
        self._current_pose: list[float] | None = None
        self._state        = self._STATE_IDLE
        self._shutdown_mode= False

        self._img_cx       = 320.0
        self._img_cy       = 240.0
        self._last_det: tuple[int, int] | None = None
        self._centered_cnt = 0

        self._grasp_sequence = [
            (self._pre_grasp_pose,     "pre_grasp"),
            (self._approach_pose,      "approach"),
            (self._close_gripper_pose, "close_gripper"),
            (self._lift_pose,          "lift"),
            (self._place_pose,         "place"),
            (self._open_gripper_pose,  "open_gripper"),
            (self._reset_pose,         "reset"),
        ]
        self._grasp_step = 0

        self._search_target = _PAN_SEARCH_LIMITS[1]

        # ── ArUco detector ───────────────────────────────────────────────── #
        self._bridge = CvBridge()
        try:
            _d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            _p = cv2.aruco.DetectorParameters()
            self._aruco       = cv2.aruco.ArucoDetector(_d, _p)
            self._aruco_new   = True
        except AttributeError:
            self._aruco_dict  = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            self._aruco_par   = cv2.aruco.DetectorParameters_create()
            self._aruco_new   = False
        self.get_logger().info("ArUco detector ready (DICT_4X4_50)")

        # ── ROS interfaces ───────────────────────────────────────────────── #
        self._cmd_pub = self.create_publisher(Float64MultiArray, self._cmd_topic, 10)
        self.create_subscription(Image,      self._img_topic, self._on_image,        10)
        self.create_subscription(JointState, self._js_topic,  self._on_joint_states, 10)
        self.create_timer(1.0 / self._rate_hz, self._control_loop)

        self.get_logger().info("Pick-and-place node started")
        self.get_logger().info(f"  image topic   : {self._img_topic}")
        self.get_logger().info(f"  command topic : {self._cmd_topic}")
        self.get_logger().info(f"  tolerance     : {self._tol_px:.0f} px  centred frames: {self._req_frames}")
        self.get_logger().info("Waiting for joint states...")

    # ── Callbacks ────────────────────────────────────────────────────────── #

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

    def _on_image(self, msg: Image) -> None:
        if self._state not in (self._STATE_SEARCH, self._STATE_CENTER):
            self._last_det = None
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

        if self._last_det is not None and self._state == self._STATE_SEARCH:
            self.get_logger().info(f"Object found at {self._last_det} — centering")
            self._state        = self._STATE_CENTER
            self._centered_cnt = 0

    # ── Object detection ─────────────────────────────────────────────────── #

    def _detect(self, img) -> tuple[int, int] | None:
        """Return (cx, cy) of detected object, or None."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. ArUco — attach any DICT_4X4_50 marker to the bottle
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

        # 2. Orange/amber colour blob (bare medicine bottle fallback)
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

    # ── Control loop ─────────────────────────────────────────────────────── #

    def _control_loop(self) -> None:
        if self._current_pose is None:
            return

        dt       = 1.0 / self._rate_hz
        max_step = self._move_speed * dt

        # RESET ─────────────────────────────────────────────────────────────
        if self._state == self._STATE_RESET:
            self._move_toward(self._reset_pose, max_step)
            if self._near(self._current_pose, self._reset_pose):
                self.get_logger().info("Reset pose reached")
                if not self._shutdown_mode:
                    self.get_logger().info("Starting SEARCH")
                    self._state         = self._STATE_SEARCH
                    self._last_det      = None
                    self._centered_cnt  = 0
                    self._search_target = _PAN_SEARCH_LIMITS[1]
            return

        # SEARCH_OBJECT ─────────────────────────────────────────────────────
        if self._state == self._STATE_SEARCH:
            err = self._search_target - self._current_pose[0]
            if abs(err) < 0.05:
                self._search_target = (
                    _PAN_SEARCH_LIMITS[0]
                    if self._search_target >= _PAN_SEARCH_LIMITS[1]
                    else _PAN_SEARCH_LIMITS[1]
                )
                err = self._search_target - self._current_pose[0]
            # Half speed while searching
            self._current_pose[0] += max(min(err, max_step * 0.5), -max_step * 0.5)
            self._publish()
            return

        # CENTER_OBJECT ─────────────────────────────────────────────────────
        if self._state == self._STATE_CENTER:
            if self._last_det is None:
                self.get_logger().info("Object lost — resuming SEARCH")
                self._centered_cnt = 0
                self._state        = self._STATE_SEARCH
                return

            cx, cy  = self._last_det
            err_x   = cx - self._img_cx
            err_y   = cy - self._img_cy
            centred = abs(err_x) <= self._tol_px and abs(err_y) <= self._tol_px

            if not centred:
                self._centered_cnt = 0
                if abs(err_x) > self._tol_px:
                    step = self._pan_sign * np.sign(err_x) * self._servo_step
                    self._current_pose[0] = max(_PAN_SERVO_LIMITS[0], min(
                        _PAN_SERVO_LIMITS[1], self._current_pose[0] - step))
                if abs(err_y) > self._tol_px:
                    step = self._tilt_sign * np.sign(err_y) * self._servo_step
                    self._current_pose[1] = max(_LIFT_SERVO_LIMITS[0], min(
                        _LIFT_SERVO_LIMITS[1], self._current_pose[1] + step))
                self._publish()
            else:
                self._centered_cnt += 1
                self.get_logger().info(
                    f"Centred {self._centered_cnt}/{self._req_frames} "
                    f"(err_x={err_x:+.0f}px  err_y={err_y:+.0f}px)")
                if self._centered_cnt >= self._req_frames:
                    self.get_logger().info("Object centred — starting GRASP sequence")
                    self._state      = self._STATE_GRASP
                    self._grasp_step = 0
            return

        # GRASP ─────────────────────────────────────────────────────────────
        if self._state == self._STATE_GRASP:
            if self._grasp_step >= len(self._grasp_sequence):
                self.get_logger().info("Grasp sequence complete — returning to SEARCH")
                self._state         = self._STATE_SEARCH
                self._last_det      = None
                self._centered_cnt  = 0
                self._search_target = _PAN_SEARCH_LIMITS[1]
                return

            target, label = self._grasp_sequence[self._grasp_step]
            self._move_toward(target, max_step)
            if self._near(self._current_pose, target):
                self.get_logger().info(f"  [{self._grasp_step + 1}/{len(self._grasp_sequence)}] {label}")
                self._grasp_step += 1

    # ── Helpers ──────────────────────────────────────────────────────────── #

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
    node = PickPlaceNode()

    _stop = [False]

    def _sigint(sig, frame):
        _stop[0] = True

    signal.signal(signal.SIGINT, _sigint)

    try:
        while rclpy.ok() and not _stop[0]:
            rclpy.spin_once(node, timeout_sec=0.1)

        # Ctrl+C → move to reset pose before exiting
        if node._current_pose is not None:
            node.get_logger().info("Stopping pick-and-place — moving to reset position")
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
