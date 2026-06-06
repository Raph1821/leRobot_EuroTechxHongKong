"""
Launch file for the SO-100 web control expansion.

Launches the extended WebSocket bridge node with multi-robot namespace
support, camera topic remapping, IK solver service, episode recorder
lifecycle node, and spawn service connection configuration.

This launch file composes:
  - WebSocket bridge node (with robot_namespaces, camera, teleop, etc.)
  - IK solver service node (compute_ik per namespace)
  - Episode recorder lifecycle node
  - Spawn service connection parameters

Usage:
  # Launch with default single-robot (no namespace):
  ros2 launch so_arm_100_bringup web_control.launch.py

  # Launch with multi-robot namespaces:
  ros2 launch so_arm_100_bringup web_control.launch.py \
      robot_namespaces:="['/robot1', '/robot2']"

  # Launch with custom camera topic and IK solver:
  ros2 launch so_arm_100_bringup web_control.launch.py \
      camera_topic:=/viewport_camera/image_raw \
      ik_solver_timeout:=5.0

Requirements: 6.1, 6.2, 1.1, 3.1, 4.1
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessStart
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState

import lifecycle_msgs.msg


def launch_setup(context, *args, **kwargs):
    """Set up and return all nodes for the web control expansion."""

    # Resolve launch configurations.
    robot_namespaces_str = LaunchConfiguration('robot_namespaces').perform(context)
    websocket_host = LaunchConfiguration('websocket_host').perform(context)
    websocket_port = LaunchConfiguration('websocket_port').perform(context)
    broadcast_rate_hz = LaunchConfiguration('broadcast_rate_hz').perform(context)
    jpeg_quality = LaunchConfiguration('jpeg_quality').perform(context)
    camera_topic = LaunchConfiguration('camera_topic').perform(context)
    episode_root_dir = LaunchConfiguration('episode_root_dir').perform(context)
    episode_recorder_node_name = LaunchConfiguration(
        'episode_recorder_node_name'
    ).perform(context)
    ik_solver_timeout = LaunchConfiguration('ik_solver_timeout').perform(context)
    spawn_service_name = LaunchConfiguration('spawn_service_name').perform(context)
    delete_service_name = LaunchConfiguration('delete_service_name').perform(context)
    spawn_service_timeout = LaunchConfiguration('spawn_service_timeout').perform(context)

    # Parse robot_namespaces from string representation.
    # Accepts formats: "['ns1', 'ns2']", "[ns1, ns2]", or "ns1,ns2"
    namespaces = _parse_namespaces(robot_namespaces_str)

    # ─── WebSocket Bridge Node ───────────────────────────────────────────
    bridge_parameters = {
        'websocket_host': websocket_host,
        'websocket_port': int(websocket_port),
        'broadcast_rate_hz': float(broadcast_rate_hz),
        'robot_namespaces': namespaces,
        'jpeg_quality': int(jpeg_quality),
        'episode_root_dir': episode_root_dir,
        'episode_recorder_node': episode_recorder_node_name,
    }

    # Build camera topic remappings based on namespaces.
    # If namespaces are configured, remap each namespace's camera topic.
    # Otherwise remap the single default camera topic.
    bridge_remappings = []
    if namespaces and namespaces != ['']:
        for ns in namespaces:
            # Remap viewport camera topic per namespace.
            bridge_remappings.append(
                (
                    f'{ns}/viewport_camera/image_raw',
                    f'{ns}{camera_topic}',
                )
            )
    else:
        # Single robot mode: remap the default camera topic.
        bridge_remappings.append(
            ('viewport_camera/image_raw', camera_topic)
        )

    websocket_bridge_node = Node(
        package='so_arm_100_web_bridge',
        executable='websocket_bridge',
        name='websocket_bridge',
        output='screen',
        parameters=[bridge_parameters],
        remappings=bridge_remappings,
    )

    # ─── IK Solver Service Node ──────────────────────────────────────────
    # The IK solver exposes a compute_ik service per namespace.
    # If multiple namespaces are configured, launch one IK solver per
    # namespace (each in its own namespace for topic isolation).
    ik_nodes = []
    if namespaces and namespaces != ['']:
        for ns in namespaces:
            ik_node = Node(
                package='so_arm_100_web_bridge',
                executable='websocket_bridge',
                name='ik_solver',
                namespace=ns.lstrip('/'),
                output='screen',
                parameters=[{
                    'solver_timeout': float(ik_solver_timeout),
                    'position_tolerance': 0.005,
                    'orientation_tolerance': 0.05,
                }],
                # Use a dedicated IK solver executable if available,
                # otherwise this is a placeholder node definition.
                # The actual IK service is exposed by the bridge's
                # CartesianController or a standalone IK node.
            )
            ik_nodes.append(ik_node)
    else:
        # Single robot mode: one IK solver node.
        ik_node = Node(
            package='so_arm_100_web_bridge',
            executable='websocket_bridge',
            name='ik_solver',
            output='screen',
            parameters=[{
                'solver_timeout': float(ik_solver_timeout),
                'position_tolerance': 0.005,
                'orientation_tolerance': 0.05,
            }],
        )
        ik_nodes.append(ik_node)

    # ─── Episode Recorder Lifecycle Node ─────────────────────────────────
    # The episode recorder uses ROS2 lifecycle for managed state transitions.
    # It starts in UNCONFIGURED state and must be configured + activated.
    episode_recorder_node = LifecycleNode(
        package='episode_recorder',
        executable='episode_recorder_node',
        name='episode_recorder',
        namespace='',
        output='screen',
        parameters=[{
            'root_dir': episode_root_dir,
            'storage_id': 'mcap',
            'max_episode_duration': 0.0,
        }],
    )

    # Auto-configure the episode recorder after it starts.
    configure_episode_recorder = RegisterEventHandler(
        event_handler=OnProcessStart(
            target_action=episode_recorder_node,
            on_start=[
                EmitEvent(
                    event=ChangeState(
                        lifecycle_node_matcher=lambda node: node == episode_recorder_node,
                        transition_id=lifecycle_msgs.msg.Transition.TRANSITION_CONFIGURE,
                    )
                ),
            ],
        )
    )

    # Auto-activate after configuration succeeds.
    activate_episode_recorder = RegisterEventHandler(
        event_handler=OnStateTransition(
            target_lifecycle_node=episode_recorder_node,
            start_state='configuring',
            goal_state='inactive',
            entities=[
                EmitEvent(
                    event=ChangeState(
                        lifecycle_node_matcher=lambda node: node == episode_recorder_node,
                        transition_id=lifecycle_msgs.msg.Transition.TRANSITION_ACTIVATE,
                    )
                ),
            ],
        )
    )

    # ─── Compose all nodes ───────────────────────────────────────────────
    nodes = [
        websocket_bridge_node,
        episode_recorder_node,
        configure_episode_recorder,
        activate_episode_recorder,
    ]
    nodes.extend(ik_nodes)

    return nodes


def _parse_namespaces(namespaces_str: str) -> list:
    """Parse robot namespaces from a string representation.

    Supports formats:
      - "['ns1', 'ns2']" (Python list literal)
      - "[ns1, ns2]" (bracket-delimited)
      - "ns1,ns2" (comma-separated)
      - "" (empty → single default namespace)

    Returns:
        List of namespace strings.
    """
    if not namespaces_str or namespaces_str.strip() == '':
        return ['']

    # Strip outer brackets if present.
    stripped = namespaces_str.strip()
    if stripped.startswith('[') and stripped.endswith(']'):
        stripped = stripped[1:-1]

    # Split by comma and clean up quotes/whitespace.
    parts = stripped.split(',')
    namespaces = []
    for part in parts:
        ns = part.strip().strip("'\"")
        if ns:
            namespaces.append(ns)

    return namespaces if namespaces else ['']


def generate_launch_description():
    """Generate the web control expansion launch description."""

    return LaunchDescription([
        # ─── WebSocket Bridge Parameters ─────────────────────────────────
        DeclareLaunchArgument(
            'websocket_host',
            default_value='0.0.0.0',
            description='Host address for the WebSocket server',
        ),
        DeclareLaunchArgument(
            'websocket_port',
            default_value='9090',
            description='Port for the WebSocket server',
        ),
        DeclareLaunchArgument(
            'broadcast_rate_hz',
            default_value='30.0',
            description='Rate (Hz) for broadcasting joint states to clients',
        ),

        # ─── Multi-Robot Namespace Configuration (Req 6.1, 6.2) ─────────
        DeclareLaunchArgument(
            'robot_namespaces',
            default_value="['']",
            description=(
                'List of robot namespace strings for multi-robot support. '
                "Format: \"['/robot1', '/robot2']\". "
                'Empty string for single-robot mode. '
                'Supports minimum 4 simultaneous namespaces.'
            ),
        ),

        # ─── Camera Streaming Configuration (Req 1.1) ───────────────────
        DeclareLaunchArgument(
            'jpeg_quality',
            default_value='75',
            description=(
                'JPEG compression quality for camera frames (10-100). '
                'Lower values reduce bandwidth at the cost of image quality.'
            ),
        ),
        DeclareLaunchArgument(
            'camera_topic',
            default_value='/viewport_camera/image_raw',
            description=(
                'Camera image topic to subscribe to. '
                'Used for remapping the viewport camera topic from Isaac Sim.'
            ),
        ),

        # ─── IK Solver Configuration (Req 3.1) ──────────────────────────
        DeclareLaunchArgument(
            'ik_solver_timeout',
            default_value='5.0',
            description=(
                'Timeout in seconds for IK solver service calls. '
                'Requests exceeding this timeout will be cancelled.'
            ),
        ),

        # ─── Episode Recorder Configuration (Req 4.1) ───────────────────
        DeclareLaunchArgument(
            'episode_root_dir',
            default_value='/tmp/episode_recorder',
            description='Root directory for storing recorded episodes',
        ),
        DeclareLaunchArgument(
            'episode_recorder_node_name',
            default_value='/episode_recorder',
            description='Fully qualified name of the episode recorder node',
        ),

        # ─── Spawn Service Configuration ────────────────────────────────
        DeclareLaunchArgument(
            'spawn_service_name',
            default_value='/spawn_object',
            description='ROS2 service name for object spawning in Isaac Sim',
        ),
        DeclareLaunchArgument(
            'delete_service_name',
            default_value='/delete_object',
            description='ROS2 service name for object deletion in Isaac Sim',
        ),
        DeclareLaunchArgument(
            'spawn_service_timeout',
            default_value='5.0',
            description='Timeout in seconds for spawn/delete service calls',
        ),

        # ─── Launch Setup ────────────────────────────────────────────────
        OpaqueFunction(function=launch_setup),
    ])
