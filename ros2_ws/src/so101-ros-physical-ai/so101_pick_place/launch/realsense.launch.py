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
                # Lower FPS + smaller colour res to fit USB bandwidth in QEMU.
                # D405 native colour width is 848; depth is 640.
                # Raise fps to 15 or 30 once bandwidth is confirmed stable.
                "rgb_camera.color_profile":   "424x240x6",
                "depth_module.depth_profile":  "640x480x6",
                "align_depth.enable": True,
                "pointcloud.enable":  False,
            }],
        )
    ])
