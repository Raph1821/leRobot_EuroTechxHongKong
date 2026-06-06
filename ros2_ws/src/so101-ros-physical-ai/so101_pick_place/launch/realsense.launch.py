"""
Launch the Intel RealSense D405 as the overhead camera.

Publishes:
  /static_camera/color/image_raw
  /static_camera/depth/image_rect_raw

Prerequisite:
  sudo apt install ros-jazzy-realsense2-camera
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="realsense2_camera",
            executable="realsense2_camera_node",
            name="cam_overhead",
            namespace="static_camera",
            output="screen",
            parameters=[{
                "enable_color":  True,
                "enable_depth":  True,
                "enable_infra1": False,
                "enable_infra2": False,
                "rgb_camera.color_profile":   "640x480x30",
                "depth_module.depth_profile":  "640x480x30",
                "align_depth.enable": True,
                "pointcloud.enable":  False,
            }],
        )
    ])
