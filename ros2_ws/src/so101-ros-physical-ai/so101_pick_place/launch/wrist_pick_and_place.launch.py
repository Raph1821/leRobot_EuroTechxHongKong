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
Launch the SO-101 wrist-camera pick-and-place node.

Prerequisites
-------------
  Terminal 1:
    ros2 launch so101_bringup follower.launch.py hardware_type:=real

  Terminal 2:
    ros2 launch so101_pick_place wrist_pick_and_place.launch.py

Test camera detection
---------------------
  Check what the arm sees:
    ros2 run rqt_image_view rqt_image_view /follower/image_raw

  Simulate detection trigger (ArUco):
    Print any marker from https://chev.me/arucogen/ using DICT_4X4_50,
    tape it to the bottle.

  Colour fallback: bare amber/orange medicine bottle — no marker needed.

Tune poses
----------
  Edit the pose lists in the parameters block below.
  Measure real positions with:
    ros2 topic echo /follower/joint_states --once
  Then remap alphabetical → controller order:
    [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]

  If the centering servo moves the wrong way, flip pan_servo_sign or
  tilt_servo_sign to -1.0.

Do NOT run alongside so101_teleop or so101_patrol — all write to the same topic.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pick_place_node = Node(
        package="so101_pick_place",
        executable="pick_place_node",
        name="pick_place_node",
        output="screen",
        emulate_tty=True,
        parameters=[{
            # ── Topics ────────────────────────────────────────────────── #
            "image_topic":         "/follower/image_raw",
            "command_topic":       "/follower/forward_controller/commands",
            "joint_states_topic":  "/follower/joint_states",

            # ── Detection / centering ─────────────────────────────────── #
            "center_tolerance_px":       30.0,
            "required_centered_frames":  10,
            "servo_step_size":            0.02,
            "pan_servo_sign":             1.0,   # set to -1.0 if pan goes wrong way
            "tilt_servo_sign":            1.0,   # set to -1.0 if tilt goes wrong way

            # ── Motion ────────────────────────────────────────────────── #
            "move_speed_rad_s":  0.3,
            "publish_rate_hz":   10.0,

            # ── Poses ─────────────────────────────────────────────────── #
            # Joint order: [shoulder_pan, shoulder_lift, elbow_flex,
            #               wrist_flex,   wrist_roll,   gripper]
            # TUNE THESE before running — defaults are conservative placeholders.
            "reset_pose":         [-0.0844, -1.8270,  1.6659,  1.1612,  0.0614,  0.0015],
            # Patrol home height — arm rises here before sweeping (same as patrol home pose).
            "search_pose":        [ 0.1457, -0.9710, -0.1856,  1.4557, -0.0276,  0.0046],
            "pre_grasp_pose":     [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000],
            "approach_pose":      [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000,  0.0000],
            "close_gripper_pose": [ 0.0000, -0.5000,  0.8000,  1.2000,  0.0000, -0.4000],
            "lift_pose":          [ 0.0000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000],
            "place_pose":         [ 0.5000, -0.9000,  0.5000,  1.0000,  0.0000, -0.4000],
            "open_gripper_pose":  [ 0.5000, -0.9000,  0.5000,  1.0000,  0.0000,  0.0000],
        }],
    )

    return LaunchDescription([pick_place_node])
