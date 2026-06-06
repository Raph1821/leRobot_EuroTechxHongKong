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
Launch the SO-101 CareAI patrol node.

Prerequisites
-------------
  ros2 launch so101_bringup follower.launch.py hardware_type:=real

Then in a second terminal:

  ros2 launch so101_patrol patrol.launch.py

Do NOT run alongside so101_teleop — both write to the same command topic.

Testing person detection
------------------------
  ros2 topic pub /person_detected std_msgs/msg/Bool "{data: true}"
  ros2 topic pub /person_detected std_msgs/msg/Bool "{data: false}"
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        # Topics
        DeclareLaunchArgument(
            "command_topic",
            default_value="/follower/forward_controller/commands",
        ),
        DeclareLaunchArgument(
            "joint_states_topic",
            default_value="/follower/joint_states",
        ),
        DeclareLaunchArgument(
            "person_detected_topic",
            default_value="/person_detected",
        ),

        # ---- Patrol sweep ------------------------------------------------ #
        # shoulder_pan URDF limits: ±1.92 rad
        DeclareLaunchArgument("shoulder_pan_left",  default_value="1.3"),
        DeclareLaunchArgument("shoulder_pan_right", default_value="-1.3"),

        # ---- Motion ------------------------------------------------------ #
        DeclareLaunchArgument("max_speed_rad_s",       default_value="0.3"),
        DeclareLaunchArgument("person_lost_timeout_s", default_value="3.0"),
        DeclareLaunchArgument("publish_rate_hz",       default_value="10.0"),

        # ---- Home pose --------------------------------------------------- #
        # Arm configuration held during patrol.
        # Arm smoothly moves here from startup position before sweep begins.
        DeclareLaunchArgument("use_configured_home",   default_value="true"),
        DeclareLaunchArgument("home_shoulder_pan",     default_value="0.1457"),
        DeclareLaunchArgument("home_shoulder_lift",    default_value="-0.9710"),
        DeclareLaunchArgument("home_elbow_flex",       default_value="-0.1856"),
        DeclareLaunchArgument("home_wrist_flex",       default_value="1.4557"),
        DeclareLaunchArgument("home_wrist_roll",       default_value="-0.0276"),
        DeclareLaunchArgument("home_gripper",          default_value="0.0046"),

        # ---- Rest pose --------------------------------------------------- #
        # Arm returns here smoothly when you press Ctrl+C.
        DeclareLaunchArgument("use_rest_pose",         default_value="true"),
        DeclareLaunchArgument("rest_shoulder_pan",     default_value="0.0046"),
        DeclareLaunchArgument("rest_shoulder_lift",    default_value="-1.8316"),
        DeclareLaunchArgument("rest_elbow_flex",       default_value="1.6567"),
        DeclareLaunchArgument("rest_wrist_flex",       default_value="1.1658"),
        DeclareLaunchArgument("rest_wrist_roll",       default_value="-0.0123"),
        DeclareLaunchArgument("rest_gripper",          default_value="0.4357"),
    ]

    patrol_node = Node(
        package="so101_patrol",
        executable="patrol_node",
        name="patrol_node",
        output="screen",
        emulate_tty=True,
        parameters=[{
            "command_topic":          LaunchConfiguration("command_topic"),
            "joint_states_topic":     LaunchConfiguration("joint_states_topic"),
            "person_detected_topic":  LaunchConfiguration("person_detected_topic"),
            "shoulder_pan_left":      LaunchConfiguration("shoulder_pan_left"),
            "shoulder_pan_right":     LaunchConfiguration("shoulder_pan_right"),
            "max_speed_rad_s":        LaunchConfiguration("max_speed_rad_s"),
            "person_lost_timeout_s":  LaunchConfiguration("person_lost_timeout_s"),
            "publish_rate_hz":        LaunchConfiguration("publish_rate_hz"),
            "use_configured_home":    LaunchConfiguration("use_configured_home"),
            "home_shoulder_pan":      LaunchConfiguration("home_shoulder_pan"),
            "home_shoulder_lift":     LaunchConfiguration("home_shoulder_lift"),
            "home_elbow_flex":        LaunchConfiguration("home_elbow_flex"),
            "home_wrist_flex":        LaunchConfiguration("home_wrist_flex"),
            "home_wrist_roll":        LaunchConfiguration("home_wrist_roll"),
            "home_gripper":           LaunchConfiguration("home_gripper"),
            "use_rest_pose":          LaunchConfiguration("use_rest_pose"),
            "rest_shoulder_pan":      LaunchConfiguration("rest_shoulder_pan"),
            "rest_shoulder_lift":     LaunchConfiguration("rest_shoulder_lift"),
            "rest_elbow_flex":        LaunchConfiguration("rest_elbow_flex"),
            "rest_wrist_flex":        LaunchConfiguration("rest_wrist_flex"),
            "rest_wrist_roll":        LaunchConfiguration("rest_wrist_roll"),
            "rest_gripper":           LaunchConfiguration("rest_gripper"),
        }],
    )

    return LaunchDescription(args + [patrol_node])
