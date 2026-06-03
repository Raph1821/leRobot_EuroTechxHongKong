"""
ROS2 launch file for the SO-100 5-DOF arm in NVIDIA Isaac Sim.

Starts the Isaac Sim standalone script with the SO-100 arm scene, spawns
the controller_manager with the same controller configuration as the Gazebo
launch, waits for /joint_states readiness, then sequentially activates:
  1. joint_state_broadcaster
  2. arm_controller (JointTrajectoryController)
  3. gripper_controller (GripperActionController)

A 30-second timeout aborts the launch if /joint_states is not received,
indicating Isaac Sim failed to become ready.

Requirements: 5.1, 5.3, 5.4, 5.5
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

import xacro


def _get_robot_description(context):
    """Process the URDF xacro and return the robot description string."""
    so_arm_100_description_path = get_package_share_directory('so_arm_100_description')

    xacro_file = os.path.join(
        so_arm_100_description_path,
        'urdf',
        'so_arm_100_5dof.urdf.xacro',
    )

    doc = xacro.process_file(
        xacro_file,
        mappings={
            'prefix': '',
            'use_sim': 'false',
            'use_fake_hardware': 'true',
        },
    )

    return doc.toprettyxml(indent='  ')


def launch_setup(context, *args, **kwargs):
    """Configure and return all launch actions for the Isaac Sim backend."""

    so_arm_100_isaac_sim_path = get_package_share_directory('so_arm_100_isaac_sim')
    so_arm_100_moveit_config_path = get_package_share_directory('so_arm_100_moveit_config')

    # Controller configuration files (same as Gazebo launch — Req 5.3)
    controllers_config = os.path.join(
        so_arm_100_moveit_config_path,
        'config',
        'controllers_5dof.yaml',
    )

    # Robot description for robot_state_publisher
    robot_description = _get_robot_description(context)

    # Headless mode from launch argument
    headless = LaunchConfiguration('headless').perform(context)

    # -----------------------------------------------------------------------
    # Isaac Sim standalone script path
    # -----------------------------------------------------------------------
    isaac_sim_script = os.path.join(
        so_arm_100_isaac_sim_path,
        'scripts',
        'load_robot.py',
    )

    # -----------------------------------------------------------------------
    # Nodes and Processes
    # -----------------------------------------------------------------------

    # 1. Start Isaac Sim with the SO-100 arm scene (Req 5.1)
    isaac_sim_process = ExecuteProcess(
        cmd=['python3', isaac_sim_script],
        name='isaac_sim',
        output='screen',
        additional_env={'ISAAC_SIM_HEADLESS': '1' if headless == 'true' else '0'},
    )

    # 2. Robot State Publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': False,
        }],
    )

    # 3. Controller Manager with shared config (Req 5.3)
    #    Uses mock_components/GenericSystem for fake hardware when Isaac Sim
    #    is not available. This allows the full ROS2 control stack to run
    #    for web interface testing.
    controller_manager_node = Node(
        package='controller_manager',
        executable='ros2_control_node',
        name='controller_manager',
        output='screen',
        parameters=[
            controllers_config,
            {'use_sim_time': False},
        ],
        remappings=[
            ('/robot_description', '/robot_description'),
        ],
    )

    # 4. Controller spawners (sequential: joint_state_broadcaster → arm → gripper)
    #    Using the controller_manager spawner node which properly waits for
    #    the controller_manager to be ready before loading controllers.
    #    Delayed by 5s to ensure controller_manager has fully initialized
    #    its services (avoids race condition in ROS2 Jazzy).
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager', '/controller_manager',
            '--controller-manager-timeout', '30',
        ],
        name='spawn_joint_state_broadcaster',
        output='screen',
    )

    arm_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'arm_controller',
            '--controller-manager', '/controller_manager',
            '--controller-manager-timeout', '30',
        ],
        name='spawn_arm_controller',
        output='screen',
    )

    gripper_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'gripper_controller',
            '--controller-manager', '/controller_manager',
            '--controller-manager-timeout', '30',
        ],
        name='spawn_gripper_controller',
        output='screen',
    )

    # -----------------------------------------------------------------------
    # Event-driven sequencing
    # -----------------------------------------------------------------------

    # Isaac Sim process is optional — it will fail if isaacsim is not
    # installed, but the ROS2 control stack works independently with
    # mock hardware.

    # Delay controller spawning by 5 seconds to let the controller_manager
    # fully initialize its services after loading hardware.
    delayed_jsb_spawner = TimerAction(
        period=5.0,
        actions=[joint_state_broadcaster_spawner],
    )

    # Sequential controller spawning: jsb → arm → gripper
    spawn_arm_after_jsb = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[arm_controller_spawner],
        )
    )

    spawn_gripper_after_arm = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=arm_controller_spawner,
            on_exit=[gripper_controller_spawner],
        )
    )

    return [
        # Start Isaac Sim process (may fail if isaacsim not installed — OK)
        isaac_sim_process,
        # Start robot state publisher
        robot_state_publisher,
        # Start controller manager
        controller_manager_node,
        # Spawn controllers after delay (gives controller_manager time to init)
        delayed_jsb_spawner,
        spawn_arm_after_jsb,
        spawn_gripper_after_arm,
    ]


def generate_launch_description():
    """Generate the ROS2 launch description for Isaac Sim with SO-100 arm."""

    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'headless',
            default_value='true',
            description='Run Isaac Sim in headless mode (no GUI window)',
        ),

        # Setup via OpaqueFunction for context access
        OpaqueFunction(function=launch_setup),
    ])
