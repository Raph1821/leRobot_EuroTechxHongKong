"""Launch the medicine bottle detector node.

Usage:
  ros2 launch so101_pick_place bottle_detector.launch.py
  ros2 launch so101_pick_place bottle_detector.launch.py debug:=false
  ros2 launch so101_pick_place bottle_detector.launch.py hsv_h_low:=0 hsv_h_high:=10

HSV tuning guide (amber bottle defaults):
  Amber/orange: h_low=10 h_high=25  s_low=100 s_high=255  v_low=50  v_high=230
  White bottle: h_low=0  h_high=180 s_low=0   s_high=50   v_low=180 v_high=255
  Dark bottle:  h_low=0  h_high=180 s_low=30  s_high=255  v_low=10  v_high=100
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("debug",      default_value="true",
                              description="Publish /bottle_detector/debug_image"),
        DeclareLaunchArgument("hsv_h_low",  default_value="10"),
        DeclareLaunchArgument("hsv_h_high", default_value="25"),
        DeclareLaunchArgument("hsv_s_low",  default_value="100"),
        DeclareLaunchArgument("hsv_s_high", default_value="255"),
        DeclareLaunchArgument("hsv_v_low",  default_value="50"),
        DeclareLaunchArgument("hsv_v_high", default_value="230"),
        DeclareLaunchArgument("min_area",   default_value="500",
                              description="Min contour area in pixels²"),

        Node(
            package="so101_pick_place",
            executable="bottle_detector_node",
            name="bottle_detector",
            output="screen",
            parameters=[{
                "publish_debug":    LaunchConfiguration("debug"),
                "hsv_h_low":        LaunchConfiguration("hsv_h_low"),
                "hsv_h_high":       LaunchConfiguration("hsv_h_high"),
                "hsv_s_low":        LaunchConfiguration("hsv_s_low"),
                "hsv_s_high":       LaunchConfiguration("hsv_s_high"),
                "hsv_v_low":        LaunchConfiguration("hsv_v_low"),
                "hsv_v_high":       LaunchConfiguration("hsv_v_high"),
                "min_area_px":      LaunchConfiguration("min_area"),
            }],
        ),
    ])
