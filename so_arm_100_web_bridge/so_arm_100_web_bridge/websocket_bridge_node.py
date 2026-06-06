"""WebSocket bridge node for SO-100 arm web control.

This module implements a ROS2 node that bridges ROS2 topics and actions
to WebSocket connections, enabling browser-based control of the robot arm.

Subscribes to /joint_states and forwards to all connected WebSocket clients
as JSON at >=30 Hz. Accepts joint position commands, gripper commands,
trajectory goals, camera stream control, spawn/delete requests, Cartesian
goals, episode control, teleop velocity/mode commands, and robot selection
from clients, validates them, and dispatches to the appropriate handlers.

Extended with:
- Per-client state (camera streaming, teleop, namespace selection)
- Camera streaming pipeline (CameraStreamHandler)
- Object spawning/deletion (SpawnHandler)
- Cartesian control via IK (CartesianController)
- Episode recording/replay (EpisodeHandler)
- Teleoperation velocity commands (TeleopHandler)
- Multi-robot namespace routing (NamespaceRouter)

Requirements: 1.5, 2.2, 3.2, 4.1, 5.3, 6.1, 6.2, 6.3
"""

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory, GripperCommand

import websockets
from websockets.server import serve

from so_arm_100_web_bridge.joint_validator import ARM_JOINT_NAMES
from so_arm_100_web_bridge.message_schemas import (
    deserialize_command,
    serialize_error,
    serialize_joint_state,
    serialize_trajectory_status,
)
try:
    from so_arm_100_web_bridge.camera_stream_handler import CameraStreamHandler
    _CAMERA_AVAILABLE = True
except (ImportError, AttributeError) as _cam_err:
    CameraStreamHandler = None  # type: ignore
    _CAMERA_AVAILABLE = False
from so_arm_100_web_bridge.spawn_handler import SpawnHandler
from so_arm_100_web_bridge.cartesian_controller import CartesianController
from so_arm_100_web_bridge.episode_handler import EpisodeHandler
from so_arm_100_web_bridge.teleop_handler import TeleopHandler
from so_arm_100_web_bridge.namespace_router import NamespaceRouter


@dataclass
class ClientState:
    """State tracked per WebSocket client on the bridge.

    Each connected client has independent settings for camera streaming,
    teleop mode, active robot namespace, and a frame queue for camera data.
    """

    websocket: Any
    camera_streaming: bool = False
    teleop_enabled: bool = False
    velocity_scale: float = 0.05
    active_robot_id: str = ""
    frame_queue: deque = field(default_factory=lambda: deque(maxlen=2))
    connected_at: float = field(default_factory=time.time)


class WebSocketBridgeNode(Node):
    """ROS2 node that bridges joint states and commands over WebSocket.

    This node:
    - Subscribes to /joint_states and caches the latest state
    - Runs an asyncio WebSocket server that accepts multiple clients
    - Forwards joint states to all connected clients at >=30 Hz
    - Accepts joint_command, gripper_command, and trajectory_goal messages
    - Routes new message types to specialized handlers (camera, spawn,
      cartesian, episode, teleop, namespace)
    - Maintains per-client state for camera streaming, teleop, and namespace
    - Validates incoming commands and publishes to ROS2 topics/actions
    - Reports trajectory execution status back to the requesting client
    """

    def __init__(self):
        super().__init__('websocket_bridge')

        # Declare parameters with defaults.
        self.declare_parameter('websocket_host', '0.0.0.0')
        self.declare_parameter('websocket_port', 9090)
        self.declare_parameter('broadcast_rate_hz', 30.0)
        self.declare_parameter('robot_namespaces', [''])
        self.declare_parameter('jpeg_quality', 75)
        self.declare_parameter('episode_root_dir', '/tmp/episode_recorder')
        self.declare_parameter('episode_recorder_node', '/episode_recorder')

        self._ws_host = self.get_parameter('websocket_host').value
        self._ws_port = self.get_parameter('websocket_port').value
        self._broadcast_rate = self.get_parameter('broadcast_rate_hz').value
        self._robot_namespaces = self.get_parameter('robot_namespaces').value
        self._jpeg_quality = self.get_parameter('jpeg_quality').value
        self._episode_root_dir = self.get_parameter('episode_root_dir').value
        self._episode_recorder_node = self.get_parameter('episode_recorder_node').value

        # Latest joint state (protected by lock for thread safety).
        self._latest_joint_state: Optional[str] = None
        self._latest_joint_state_lock = threading.Lock()
        self._has_received_joint_state = False

        # Per-client state tracking (replaces the simple set of clients).
        self._client_states: Dict[Any, ClientState] = {}
        self._client_states_lock = threading.Lock()

        # Set of connected WebSocket clients (kept for backward compat).
        self._ws_clients: Set[websockets.WebSocketServerProtocol] = set()
        self._ws_clients_lock = threading.Lock()

        # Clients awaiting initial joint state (connected before first /joint_states).
        self._deferred_clients: Set[websockets.WebSocketServerProtocol] = set()
        self._deferred_clients_lock = threading.Lock()

        # QoS for joint_states subscriber (best effort, keep last 1).
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # ROS2 subscriber for /joint_states.
        self._joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self._joint_state_callback,
            qos_profile,
        )

        # ROS2 publisher for joint trajectory commands.
        self._trajectory_pub = self.create_publisher(
            JointTrajectory,
            '/arm_controller/joint_trajectory',
            10,
        )

        # Action clients.
        self._gripper_action_client = ActionClient(
            self,
            GripperCommand,
            '/gripper_controller/gripper_cmd',
        )

        self._follow_trajectory_action_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/arm_controller/follow_joint_trajectory',
        )

        # Asyncio event loop (will be set when the server starts).
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # ─── Initialize New Handlers ─────────────────────────────────────

        # Camera stream handler (optional — requires OpenCV/NumPy).
        if _CAMERA_AVAILABLE:
            self._camera_handler = CameraStreamHandler(
                node=self,
                namespace=self._robot_namespaces[0] if self._robot_namespaces else "",
                jpeg_quality=self._jpeg_quality,
                send_callback=self._async_send_to_client,
            )
        else:
            self._camera_handler = None
            self.get_logger().warn(
                'CameraStreamHandler unavailable (missing cv2/numpy). '
                'Camera streaming disabled.'
            )

        # Spawn handler (uses placeholder service types that will be resolved
        # at runtime when the actual service interface packages are available).
        self._spawn_handler = self._create_spawn_handler()

        # Cartesian controller.
        self._cartesian_controller = CartesianController(
            node=self,
            namespace=self._robot_namespaces[0] if self._robot_namespaces else "",
            send_to_client=self._async_send_to_client,
            publish_trajectory=self._publish_trajectory,
        )

        # Episode handler.
        self._episode_handler = EpisodeHandler(
            node=self,
            recorder_node_name=self._episode_recorder_node,
            root_dir=self._episode_root_dir,
            send_to_client=self._async_send_to_client,
        )

        # Teleop handler.
        self._teleop_handler = TeleopHandler(
            node=self,
            namespace=self._robot_namespaces[0] if self._robot_namespaces else "",
            send_to_client=self._async_send_to_client,
        )

        # Namespace router (for multi-robot support).
        # Filter out empty namespace strings to avoid issues.
        valid_namespaces = [ns for ns in self._robot_namespaces if ns]
        self._namespace_router = NamespaceRouter(
            node=self,
            namespaces=valid_namespaces,
            on_joint_state=self._on_namespaced_joint_state,
            on_status_change=self._on_robot_status_change,
        ) if valid_namespaces else None

        self.get_logger().info(
            f'WebSocket bridge node initialized. '
            f'Server will listen on ws://{self._ws_host}:{self._ws_port}'
        )
        if valid_namespaces:
            self.get_logger().info(
                f'Configured robot namespaces: {valid_namespaces}'
            )

    def _create_spawn_handler(self) -> Optional[SpawnHandler]:
        """Create the SpawnHandler with available service types.

        Attempts to import the service interface types. If not available,
        creates the handler with a fallback (None) and logs a warning.
        """
        try:
            from so_arm_100_interfaces.srv import SpawnObject, DeleteObject
            return SpawnHandler(
                node=self,
                spawn_service_type=SpawnObject,
                delete_service_type=DeleteObject,
                send_to_client=self._async_send_to_client,
            )
        except ImportError:
            self.get_logger().warn(
                'SpawnObject/DeleteObject service types not available. '
                'Spawn handler will not be initialized. '
                'Install so_arm_100_interfaces to enable object spawning.'
            )
            return None

    def _publish_trajectory(self, traj_msg: JointTrajectory) -> None:
        """Callback for CartesianController to publish trajectory messages.

        Args:
            traj_msg: The JointTrajectory message to publish.
        """
        self._trajectory_pub.publish(traj_msg)

    async def _async_send_to_client(self, ws, message: str) -> None:
        """Async callback for handlers to send messages to clients.

        This wraps _send_to_client for use as a callback by handlers.
        """
        await self._send_to_client(ws, message)

    # ─── Namespaced Joint State Callback ─────────────────────────────────

    async def _on_namespaced_joint_state(
        self, namespace: str, serialized_msg: str
    ) -> None:
        """Callback from NamespaceRouter when a namespaced joint state arrives.

        Forwards the joint state to all clients subscribed to this namespace
        (i.e., clients whose active_robot_id matches the namespace).

        Args:
            namespace: The robot namespace that published the joint state.
            serialized_msg: The serialized JSON joint state message.
        """
        with self._client_states_lock:
            subscribed_clients = [
                state.websocket
                for state in self._client_states.values()
                if state.active_robot_id == namespace
            ]

        for client in subscribed_clients:
            await self._send_to_client(client, serialized_msg)

    async def _on_robot_status_change(
        self, robot_id: str, status: str
    ) -> None:
        """Callback from NamespaceRouter when a robot's online status changes.

        Notifies all connected clients of the status change.

        Args:
            robot_id: The namespace identifier.
            status: "online" or "offline".
        """
        from so_arm_100_web_bridge.message_schemas import serialize_robot_status_change
        status_msg = serialize_robot_status_change(robot_id, status)

        with self._client_states_lock:
            all_clients = [
                state.websocket for state in self._client_states.values()
            ]

        for client in all_clients:
            await self._send_to_client(client, status_msg)

    # ─── Joint State Subscriber Callback ─────────────────────────────────

    def _joint_state_callback(self, msg: JointState):
        """Handle incoming /joint_states messages.

        Serializes the message to JSON and caches it. If there are deferred
        clients waiting for the first joint state, sends it to them.
        Also updates the CartesianController's joint positions for FK.
        """
        serialized = serialize_joint_state(msg)

        with self._latest_joint_state_lock:
            self._latest_joint_state = serialized
            self._has_received_joint_state = True

        # Update CartesianController with latest joint positions for FK.
        joint_positions = {}
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                joint_positions[name] = msg.position[i]
        self._cartesian_controller.update_joint_positions(joint_positions)

        # Send to deferred clients (those connected before first joint state).
        with self._deferred_clients_lock:
            if self._deferred_clients:
                deferred = self._deferred_clients.copy()
                self._deferred_clients.clear()

                if self._loop is not None:
                    for client in deferred:
                        asyncio.run_coroutine_threadsafe(
                            self._send_to_client(client, serialized),
                            self._loop,
                        )

    async def _send_to_client(self, ws, message: str):
        """Send a message to a single client, handling disconnections."""
        try:
            await ws.send(message)
        except websockets.exceptions.ConnectionClosed:
            self._remove_client(ws)
        except Exception as e:
            self.get_logger().debug(f'Error sending to client: {e}')
            self._remove_client(ws)

    def _remove_client(self, ws):
        """Remove a client from all tracking sets and clean up handler state."""
        with self._ws_clients_lock:
            self._ws_clients.discard(ws)
        with self._deferred_clients_lock:
            self._deferred_clients.discard(ws)

        # Clean up per-client state.
        with self._client_states_lock:
            self._client_states.pop(ws, None)

        # Notify handlers of client disconnect.
        if self._camera_handler is not None:
            self._camera_handler.remove_client(ws)
        self._teleop_handler.unregister_client(ws)
        if self._spawn_handler is not None:
            self._spawn_handler.remove_client(ws)

    async def _handle_client(self, ws):
        """Handle a new WebSocket client connection.

        Sends the most recent joint state within 100ms of connection.
        If no joint state has been received yet, defers sending until one arrives.
        Also sends the robot_list message on connection and initializes
        per-client state.
        """
        # Register the client.
        with self._ws_clients_lock:
            self._ws_clients.add(ws)

        # Initialize per-client state.
        client_state = ClientState(websocket=ws)
        # Default the active_robot_id to the first configured namespace.
        if self._namespace_router and self._namespace_router.get_namespace_count() > 0:
            robot_list = self._namespace_router.get_robot_list()
            if robot_list:
                client_state.active_robot_id = robot_list[0]['robot_id']

        with self._client_states_lock:
            self._client_states[ws] = client_state

        # Register with teleop handler.
        self._teleop_handler.register_client(ws)

        self.get_logger().info(
            f'Client connected. Total clients: {len(self._ws_clients)}'
        )

        # Send robot_list message on connection (Requirement 6.3).
        if self._namespace_router:
            robot_list_msg = self._namespace_router.get_robot_list_message()
            try:
                await ws.send(robot_list_msg)
            except websockets.exceptions.ConnectionClosed:
                self._remove_client(ws)
                return

        # Send initial joint state or defer.
        with self._latest_joint_state_lock:
            if self._has_received_joint_state and self._latest_joint_state is not None:
                try:
                    await ws.send(self._latest_joint_state)
                except websockets.exceptions.ConnectionClosed:
                    self._remove_client(ws)
                    return
            else:
                # Defer until first joint state arrives.
                with self._deferred_clients_lock:
                    self._deferred_clients.add(ws)

        # Listen for incoming messages from this client.
        try:
            async for message in ws:
                await self._handle_message(ws, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.get_logger().warn(f'Client handler error: {e}')
        finally:
            self._remove_client(ws)
            self.get_logger().info(
                f'Client disconnected. Total clients: {len(self._ws_clients)}'
            )

    async def _handle_message(self, ws, raw_message: str):
        """Parse, validate, and dispatch a command message from a client.

        Routes to the appropriate handler based on the message type field.
        """
        result = deserialize_command(raw_message)

        if result.get('type') == 'error':
            # Validation failed — send error back to the client.
            error_json = serialize_error(result['code'], result['message'])
            await self._send_to_client(ws, error_json)
            return

        msg_type = result['type']

        # ─── Original handlers ───────────────────────────────────────────
        if msg_type == 'joint_command':
            self._handle_joint_command(result)
        elif msg_type == 'gripper_command':
            await self._handle_gripper_command(ws, result)
        elif msg_type == 'trajectory_goal':
            await self._handle_trajectory_goal(ws, result)

        # ─── Camera stream control ──────────────────────────────────────
        elif msg_type == 'camera_stream_control':
            await self._handle_camera_stream_control(ws, result)

        # ─── Object spawning ────────────────────────────────────────────
        elif msg_type == 'spawn_object':
            await self._handle_spawn_object(ws, result)
        elif msg_type == 'delete_object':
            await self._handle_delete_object(ws, result)

        # ─── Cartesian control ──────────────────────────────────────────
        elif msg_type == 'cartesian_goal':
            await self._cartesian_controller.handle_cartesian_goal(ws, result)

        # ─── Episode control ────────────────────────────────────────────
        elif msg_type == 'episode_control':
            await self._episode_handler.handle_command(ws, result)

        # ─── Teleoperation ──────────────────────────────────────────────
        elif msg_type == 'teleop_mode':
            await self._handle_teleop_mode(ws, result)
        elif msg_type == 'teleop_velocity':
            await self._handle_teleop_velocity(ws, result)

        # ─── Multi-robot namespace selection ────────────────────────────
        elif msg_type == 'select_robot':
            await self._handle_select_robot(ws, result)

    # ─── New Message Handlers ────────────────────────────────────────────

    async def _handle_camera_stream_control(self, ws, command: dict):
        """Handle camera_stream_control messages to toggle per-client streaming.

        Updates the client state and enables/disables streaming in the
        CameraStreamHandler.

        Requirement 1.5: Toggle to enable/disable camera streaming.
        """
        enabled = command.get('enabled', False)

        with self._client_states_lock:
            state = self._client_states.get(ws)
            if state:
                state.camera_streaming = enabled

        if enabled:
            if self._camera_handler is not None:
                self._camera_handler.enable_streaming(ws)
        else:
            if self._camera_handler is not None:
                self._camera_handler.disable_streaming(ws)

    async def _handle_spawn_object(self, ws, command: dict):
        """Handle spawn_object messages by delegating to SpawnHandler."""
        if self._spawn_handler is None:
            error_json = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Object spawning is not available. '
                'The spawn service interface is not installed.',
            )
            await self._send_to_client(ws, error_json)
            return

        await self._spawn_handler.handle_spawn(ws, command)

    async def _handle_delete_object(self, ws, command: dict):
        """Handle delete_object messages by delegating to SpawnHandler."""
        if self._spawn_handler is None:
            error_json = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Object deletion is not available. '
                'The spawn service interface is not installed.',
            )
            await self._send_to_client(ws, error_json)
            return

        await self._spawn_handler.handle_delete(ws, command)

    async def _handle_teleop_mode(self, ws, command: dict):
        """Handle teleop_mode messages to toggle per-client teleop state.

        Updates both the ClientState and the TeleopHandler's tracking.
        """
        enabled = command.get('enabled', False)
        velocity_scale = command.get('velocity_scale')

        # Update per-client state.
        with self._client_states_lock:
            state = self._client_states.get(ws)
            if state:
                state.teleop_enabled = enabled
                if velocity_scale is not None:
                    state.velocity_scale = velocity_scale

        # Delegate to TeleopHandler.
        error_msg = self._teleop_handler.handle_teleop_mode(ws, command)
        if error_msg is not None:
            await self._send_to_client(ws, error_msg)

    async def _handle_teleop_velocity(self, ws, command: dict):
        """Handle teleop_velocity messages by delegating to TeleopHandler."""
        error_msg = self._teleop_handler.handle_teleop_velocity(ws, command)
        if error_msg is not None:
            await self._send_to_client(ws, error_msg)

    async def _handle_select_robot(self, ws, command: dict):
        """Handle select_robot messages to update client's active namespace.

        Validates the namespace, updates client state, and sends the
        latest joint state for the selected robot if available.
        """
        robot_id = command.get('robot_id', '')

        # Validate the namespace exists.
        if self._namespace_router is None:
            error_json = serialize_error(
                'SERVICE_UNAVAILABLE',
                'Multi-robot namespace routing is not configured.',
            )
            await self._send_to_client(ws, error_json)
            return

        if not self._namespace_router.is_namespace_valid(robot_id):
            robot_list = self._namespace_router.get_robot_list()
            valid_ids = [r['robot_id'] for r in robot_list]
            error_json = serialize_error(
                'UNKNOWN_NAMESPACE',
                f"Unknown namespace '{robot_id}'. "
                f"Valid namespaces: {valid_ids}",
            )
            await self._send_to_client(ws, error_json)
            return

        # Update client state.
        with self._client_states_lock:
            state = self._client_states.get(ws)
            if state:
                state.active_robot_id = robot_id

        # Send the latest joint state for the selected namespace if available.
        latest_js = self._namespace_router.get_latest_joint_state(robot_id)
        if latest_js is not None:
            await self._send_to_client(ws, latest_js)

    # ─── Original Command Handlers ───────────────────────────────────────

    def _handle_joint_command(self, command: dict):
        """Publish a JointTrajectory message for the given joint command.

        Creates a single-point trajectory with 0.1s duration for immediate
        execution of the commanded positions.
        """
        traj_msg = JointTrajectory()
        traj_msg.header.stamp = self.get_clock().now().to_msg()

        joint_names = []
        positions = []

        for joint_entry in command['joints']:
            joint_names.append(joint_entry['name'])
            positions.append(joint_entry['position'])

        traj_msg.joint_names = joint_names

        point = JointTrajectoryPoint()
        point.positions = positions
        point.velocities = [0.0] * len(positions)
        point.time_from_start.sec = 0
        point.time_from_start.nanosec = 100_000_000  # 0.1 seconds

        traj_msg.points = [point]

        self._trajectory_pub.publish(traj_msg)

    async def _handle_gripper_command(self, ws, command: dict):
        """Send a GripperCommand action goal for the given gripper position."""
        goal_msg = GripperCommand.Goal()
        goal_msg.command.position = command['position']
        goal_msg.command.max_effort = 0.0  # No effort limit

        if not self._gripper_action_client.wait_for_server(timeout_sec=1.0):
            error_json = serialize_error(
                'ACTION_UNAVAILABLE',
                'Gripper action server is not available',
            )
            await self._send_to_client(ws, error_json)
            return

        send_goal_future = self._gripper_action_client.send_goal_async(goal_msg)

        # Use a callback to handle the result without blocking.
        send_goal_future.add_done_callback(
            lambda future: self._on_gripper_goal_response(ws, future)
        )

    def _on_gripper_goal_response(self, ws, future):
        """Handle the gripper action goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._send_to_client(
                            ws,
                            serialize_trajectory_status(
                                'aborted', 'Gripper goal was rejected'
                            ),
                        ),
                        self._loop,
                    )
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda f: self._on_gripper_result(ws, f)
            )
        except Exception as e:
            self.get_logger().warn(f'Gripper goal response error: {e}')

    def _on_gripper_result(self, ws, future):
        """Handle the gripper action result."""
        try:
            result = future.result()
            # GripperCommand doesn't have a standard status field like
            # FollowJointTrajectory, so we just report success.
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_client(
                        ws,
                        serialize_trajectory_status(
                            'succeeded', 'Gripper command completed'
                        ),
                    ),
                    self._loop,
                )
        except Exception as e:
            self.get_logger().warn(f'Gripper result error: {e}')
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_client(
                        ws,
                        serialize_trajectory_status(
                            'aborted', f'Gripper command failed: {e}'
                        ),
                    ),
                    self._loop,
                )

    async def _handle_trajectory_goal(self, ws, command: dict):
        """Send a FollowJointTrajectory action goal for the given waypoints."""
        goal_msg = FollowJointTrajectory.Goal()

        trajectory = JointTrajectory()
        trajectory.header.stamp = self.get_clock().now().to_msg()

        # Use the standard arm joint names in order.
        trajectory.joint_names = list(ARM_JOINT_NAMES)

        for wp in command['waypoints']:
            point = JointTrajectoryPoint()

            # Build positions array in joint_names order.
            positions = []
            for joint_name in ARM_JOINT_NAMES:
                positions.append(wp['positions'].get(joint_name, 0.0))

            point.positions = positions
            point.velocities = [0.0] * len(positions)

            # Convert time_from_start to Duration.
            time_secs = wp['time_from_start']
            point.time_from_start.sec = int(time_secs)
            point.time_from_start.nanosec = int(
                (time_secs - int(time_secs)) * 1e9
            )

            trajectory.points.append(point)

        goal_msg.trajectory = trajectory

        if not self._follow_trajectory_action_client.wait_for_server(
            timeout_sec=1.0
        ):
            error_json = serialize_error(
                'ACTION_UNAVAILABLE',
                'FollowJointTrajectory action server is not available',
            )
            await self._send_to_client(ws, error_json)
            return

        # Send status: executing.
        await self._send_to_client(
            ws,
            serialize_trajectory_status('executing', 'Trajectory goal sent'),
        )

        send_goal_future = (
            self._follow_trajectory_action_client.send_goal_async(goal_msg)
        )

        send_goal_future.add_done_callback(
            lambda future: self._on_trajectory_goal_response(ws, future)
        )

    def _on_trajectory_goal_response(self, ws, future):
        """Handle the FollowJointTrajectory goal response."""
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._send_to_client(
                            ws,
                            serialize_trajectory_status(
                                'aborted', 'Trajectory goal was rejected'
                            ),
                        ),
                        self._loop,
                    )
                return

            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(
                lambda f: self._on_trajectory_result(ws, f)
            )
        except Exception as e:
            self.get_logger().warn(f'Trajectory goal response error: {e}')
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_client(
                        ws,
                        serialize_trajectory_status(
                            'aborted', f'Trajectory goal failed: {e}'
                        ),
                    ),
                    self._loop,
                )

    def _on_trajectory_result(self, ws, future):
        """Handle the FollowJointTrajectory action result.

        Reports trajectory status (succeeded/aborted/preempted) back to
        the client that sent the goal.
        """
        try:
            result = future.result()
            error_code = result.result.error_code

            if error_code == FollowJointTrajectory.Result.SUCCESSFUL:
                status = 'succeeded'
                message = 'Trajectory execution completed successfully'
            elif error_code == FollowJointTrajectory.Result.GOAL_TOLERANCE_VIOLATED:
                status = 'aborted'
                message = 'Trajectory aborted: goal tolerance violated'
            elif error_code == FollowJointTrajectory.Result.PATH_TOLERANCE_VIOLATED:
                status = 'aborted'
                message = 'Trajectory aborted: path tolerance violated'
            elif error_code == FollowJointTrajectory.Result.INVALID_GOAL:
                status = 'aborted'
                message = 'Trajectory aborted: invalid goal'
            elif error_code == FollowJointTrajectory.Result.INVALID_JOINTS:
                status = 'aborted'
                message = 'Trajectory aborted: invalid joints'
            elif error_code == FollowJointTrajectory.Result.OLD_HEADER_TIMESTAMP:
                status = 'aborted'
                message = 'Trajectory aborted: old header timestamp'
            else:
                # Treat unknown/negative codes as preempted or aborted.
                if error_code < 0:
                    status = 'preempted'
                    message = f'Trajectory preempted (error_code: {error_code})'
                else:
                    status = 'aborted'
                    message = (
                        f'Trajectory failed with error code: {error_code}'
                    )

            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_client(
                        ws, serialize_trajectory_status(status, message)
                    ),
                    self._loop,
                )
        except Exception as e:
            self.get_logger().warn(f'Trajectory result error: {e}')
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_client(
                        ws,
                        serialize_trajectory_status(
                            'aborted', f'Trajectory execution error: {e}'
                        ),
                    ),
                    self._loop,
                )

    async def _broadcast_joint_states(self):
        """Periodically broadcast the latest joint state to all clients.

        Runs at the configured broadcast rate (default 30 Hz).
        """
        interval = 1.0 / self._broadcast_rate

        while True:
            await asyncio.sleep(interval)

            with self._latest_joint_state_lock:
                state_json = self._latest_joint_state

            if state_json is None:
                continue

            with self._ws_clients_lock:
                clients = self._ws_clients.copy()

            if not clients:
                continue

            # Broadcast to all connected clients concurrently.
            send_tasks = [
                self._send_to_client(client, state_json) for client in clients
            ]
            await asyncio.gather(*send_tasks, return_exceptions=True)

    async def _run_websocket_server(self):
        """Start the WebSocket server and broadcast loop."""
        self._loop = asyncio.get_event_loop()

        # Set the event loop on handlers that need it.
        if self._camera_handler is not None:
            self._camera_handler.set_event_loop(self._loop)
        self._cartesian_controller.set_event_loop(self._loop)
        if self._namespace_router:
            self._namespace_router._loop = self._loop

        # Start the broadcast task.
        broadcast_task = asyncio.create_task(self._broadcast_joint_states())

        self.get_logger().info(
            f'Starting WebSocket server on ws://{self._ws_host}:{self._ws_port}'
        )

        async with serve(
            self._handle_client,
            self._ws_host,
            self._ws_port,
            max_size=1_048_576,  # 1 MB max message size
        ) as server:
            self.get_logger().info('WebSocket server is running.')
            # Run forever until cancelled.
            await asyncio.Future()

    def run(self):
        """Run the node with both ROS2 spinning and the WebSocket server.

        Uses a separate thread for ROS2 spinning so the asyncio event loop
        can manage the WebSocket server on the main thread.
        """
        # Start ROS2 spin in a background thread.
        spin_thread = threading.Thread(target=self._spin_ros, daemon=True)
        spin_thread.start()

        # Run the asyncio WebSocket server on the main thread.
        try:
            asyncio.run(self._run_websocket_server())
        except KeyboardInterrupt:
            pass
        finally:
            self.get_logger().info('WebSocket bridge shutting down.')
            # Clean up handlers.
            if self._camera_handler is not None:
                self._camera_handler.destroy()
            if self._namespace_router:
                self._namespace_router.destroy()

    def _spin_ros(self):
        """Spin the ROS2 node in a background thread."""
        try:
            rclpy.spin(self)
        except Exception:
            pass


def main(args=None):
    """Entry point for the websocket_bridge node."""
    rclpy.init(args=args)

    node = WebSocketBridgeNode()

    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
