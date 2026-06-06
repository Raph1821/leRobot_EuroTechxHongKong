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
Launch the SO-101 RealSense overhead pick-and-place node.

Prerequisites
-------------
  Terminal 1 — follower arm:
    ros2 launch so101_bringup follower.launch.py hardware_type:=real

  Terminal 2 — cameras (if not already running):
    ros2 launch so101_bringup cameras.launch.py

  Terminal 3 — this node:
    ros2 launch so101_pick_place overhead_pick_and_place.launch.py

Topics used
-----------
  Color : /static_camera/color/image_raw       (RealSense default)
  Depth : /static_camera/depth/image_rect_raw  (RealSense default, optional)
  If using gscam overhead camera instead:
    Color : /static_camera/image_raw
    Depth : (not available)

Detection
---------
  Priority 1 — ArUco (DICT_4X4_50): tape any marker to the bottle.
  Priority 2 — Orange/amber HSV blob: works for bare amber medicine bottles.

How to tune camera-to-robot offsets
------------------------------------
  1. Run the node and watch for the log:
       "Object found — pixel=(cx, cy)  pan_correction=X rad"
  2. If the arm pans to the wrong side, flip:
       image_to_pan_rad_per_px: -0.003
  3. If the arm doesn't pan far enough, increase the magnitude.
  4. If the arm pans past the bottle, decrease the magnitude.
  5. camera_to_robot_x adds a constant pan bias (e.g. if camera is off-center).
  6. Tune grasp_pose height first with the bottle in the centre of the image,
     then tune image_to_pan_rad_per_px to handle off-centre bottles.

How to test with a single medicine bottle
-----------------------------------------
  1. Place the bottle in the pick zone on the table.
  2. Confirm the camera sees it:
       ros2 topic hz /static_camera/color/image_raw
  3. Launch this node and watch logs:
       "Searching for object..."     → looking
       "Object found ..."            → detected, computing pan correction
       "Moving to pre-grasp pose"    → arm moving
       "above object"                → hovering
       "at grasp position"           → lowering
       "closing gripper"             → gripping
       "Lifting object"              → lifting
       "Moving to slot A"            → placing
       "opening gripper"             → done
  4. If the arm misses the bottle, adjust grasp_pose and image_to_pan_rad_per_px.

Pose tuning order
-----------------
  1. reset_pose        — safe resting position
  2. pre_grasp_pose    — arm raised, ready to act
  3. grasp_pose        — arm lowered to bottle height (shoulder_pan here is BASE,
                         detection adds correction automatically)
  4. close_gripper_pose — same as grasp but gripper joint = -0.4 (or your close value)
  5. lift_pose         — arm raised with gripper closed
  6. slot_A_pose       — above placement slot A
  7. open_gripper_pose — same as slot_A but gripper = 0.0

Do NOT run alongside so101_teleop or so101_patrol — all write the same command topic.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    node = Node(
        package="so101_pick_place",
        executable="overhead_pick_place_node",
        name="overhead_pick_place_node",
        output="screen",
        emulate_tty=True,
        parameters=[{
            # ── Topics ────────────────────────────────────────────────── #
            "image_topic":         "/static_camera/color/image_raw",
            "depth_topic":         "/static_camera/depth/image_rect_raw",
            "command_topic":       "/follower/forward_controller/commands",
            "joint_states_topic":  "/follower/joint_states",

            # ── Camera-to-robot tuning ─────────────────────────────────── #
            # image_to_pan_rad_per_px:
            #   How many radians shoulder_pan moves per pixel of horizontal
            #   offset from image centre.  For a 640px image spanning ~2 rad:
            #     2 rad / 640 px ≈ 0.003 rad/px
            #   Flip sign if pan goes the wrong direction.
            "image_to_pan_rad_per_px":  0.003,
            "camera_to_robot_x":        0.0,   # constant pan bias (rad)
            "camera_to_robot_y":        0.0,   # reserved
            "camera_to_robot_z":        0.0,   # reserved

            # ── Detection ─────────────────────────────────────────────── #
            "required_detection_frames": 5,

            # ── Motion ────────────────────────────────────────────────── #
            "move_speed_rad_s":  0.3,
            "publish_rate_hz":   10.0,

            # ���─ Poses ─────────────────────────────────────────────────── #
            # [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
            # shoulder_pan in grasp_pose/close_gripper_pose/pre_grasp_pose is the BASE
            # value — detection automatically adds a pan correction on top.
            # TUNE ALL POSES before running a real pick-and-place cycle.
            "reset_pose":         [ 0.0000, -0.5000,  0.5000,  0.0000,  0.0000,  0.0000],
            "pre_grasp_pose":     [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000],
            "grasp_pose":         [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000,  0.0000],
            "close_gripper_pose": [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000, -0.4000],
            "lift_pose":          [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000],
            "slot_A_pose":        [ 0.6000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000],
            "open_gripper_pose":  [ 0.6000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000],
        }],
    )

    return LaunchDescription([node])
