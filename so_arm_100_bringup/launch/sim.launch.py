"""
Unified simulation launch file for the SO-100 5-DOF robot arm.

Provides a `sim_backend` launch argument to switch between simulation backends:
  - gazebo (default): Launches the Gazebo Harmonic simulation
  - isaac_sim: Launches the NVIDIA Isaac Sim simulation

Both backends share the same controller configuration (controllers_5dof.yaml,
initial_positions.yaml) from the so_arm_100_moveit_config package.

Usage:
  # Launch with Gazebo (default):
  ros2 launch so_arm_100_bringup sim.launch.py

  # Launch with Isaac Sim:
  ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=isaac_sim

  # Launch with Isaac Sim in headless mode:
  ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=isaac_sim headless:=true

Requirements: 5.2, 5.3
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *args, **kwargs):
    """Select and include the appropriate backend launch file."""

    sim_backend = LaunchConfiguration('sim_backend').perform(context)

    # Validate sim_backend argument
    valid_backends = ('gazebo', 'isaac_sim')
    if sim_backend not in valid_backends:
        raise RuntimeError(
            f"Invalid sim_backend '{sim_backend}'. "
            f"Must be one of: {', '.join(valid_backends)}"
        )

    if sim_backend == 'gazebo':
        # Include existing Gazebo launch file with passthrough arguments
        so_arm_100_bringup_path = get_package_share_directory('so_arm_100_bringup')
        gazebo_launch_file = os.path.join(
            so_arm_100_bringup_path, 'launch', 'gz.launch.py'
        )

        # Collect Gazebo-specific arguments to forward
        dof = LaunchConfiguration('dof').perform(context)
        prefix = LaunchConfiguration('prefix').perform(context)
        world = LaunchConfiguration('world').perform(context)
        use_topic_hardware_interface = LaunchConfiguration(
            'use_topic_hardware_interface'
        ).perform(context)

        return [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(gazebo_launch_file),
                launch_arguments={
                    'dof': dof,
                    'prefix': prefix,
                    'world': world,
                    'use_topic_hardware_interface': use_topic_hardware_interface,
                }.items(),
            ),
        ]

    else:
        # Include Isaac Sim launch file
        so_arm_100_isaac_sim_path = get_package_share_directory('so_arm_100_isaac_sim')
        isaac_sim_launch_file = os.path.join(
            so_arm_100_isaac_sim_path, 'launch', 'isaac_sim.launch.py'
        )

        # Forward the headless argument to Isaac Sim launch
        headless = LaunchConfiguration('headless').perform(context)

        return [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(isaac_sim_launch_file),
                launch_arguments={
                    'headless': headless,
                }.items(),
            ),
        ]


def generate_launch_description():
    """Generate the unified simulation launch description."""

    return LaunchDescription([
        # -------------------------------------------------------------------
        # Shared arguments
        # -------------------------------------------------------------------
        DeclareLaunchArgument(
            'sim_backend',
            default_value='gazebo',
            choices=['gazebo', 'isaac_sim'],
            description=(
                'Simulation backend to use. '
                'Valid values: gazebo (default), isaac_sim'
            ),
        ),

        # -------------------------------------------------------------------
        # Gazebo-specific arguments (used when sim_backend:=gazebo)
        # -------------------------------------------------------------------
        DeclareLaunchArgument(
            'dof',
            default_value='5',
            description='DOF configuration - either 5 or 7 (Gazebo only)',
        ),
        DeclareLaunchArgument(
            'prefix',
            default_value='',
            description='Prefix of joint and link names (Gazebo only)',
        ),
        DeclareLaunchArgument(
            'world',
            default_value='empty',
            description='Gz sim World (Gazebo only)',
        ),
        DeclareLaunchArgument(
            'use_topic_hardware_interface',
            default_value='false',
            description=(
                'Use topic based hardware interface instead of gz_ros_control '
                '(Gazebo only)'
            ),
        ),

        # -------------------------------------------------------------------
        # Isaac Sim-specific arguments (used when sim_backend:=isaac_sim)
        # -------------------------------------------------------------------
        DeclareLaunchArgument(
            'headless',
            default_value='true',
            description='Run Isaac Sim in headless mode (Isaac Sim only)',
        ),

        # -------------------------------------------------------------------
        # Backend selection logic
        # -------------------------------------------------------------------
        OpaqueFunction(function=launch_setup),
    ])
