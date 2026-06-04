"""Teleoperation velocity handler for the SO-100 web bridge.

This module implements the TeleopHandler class that processes Cartesian
velocity commands from WebSocket clients, converts them to joint velocities
via an IK solver service, and forwards them to the arm controller.

It tracks per-client teleop state (enabled/disabled, velocity scale) and
ensures zero-velocity commands are sent when a client disables teleop or
disconnects.

Requirements: 5.3, 5.7, 5.8, 5.9
"""

import threading
from typing import Any, Callable, Dict, List, Optional

from rclpy.node import Node

from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from so_arm_100_web_bridge.joint_validator import ARM_JOINT_NAMES
from so_arm_100_web_bridge.message_schemas import serialize_error


# Default velocity scale factor (m/s).
_DEFAULT_VELOCITY_SCALE = 0.05

# Velocity scale bounds.
_MIN_VELOCITY_SCALE = 0.01
_MAX_VELOCITY_SCALE = 0.2

# Duration for velocity command trajectory points (seconds).
# Short duration allows smooth streaming at 20 Hz.
_VELOCITY_COMMAND_DURATION_SEC = 0.05


class TeleopClientState:
    """Per-client teleoperation state.

    Attributes:
        enabled: Whether teleop mode is active for this client.
        velocity_scale: The velocity scale factor applied to commands.
    """

    def __init__(self):
        self.enabled: bool = False
        self.velocity_scale: float = _DEFAULT_VELOCITY_SCALE


class TeleopHandler:
    """Processes teleoperation velocity commands from WebSocket clients.

    Converts Cartesian velocity commands to joint velocity commands via
    a simplified Jacobian-based IK approach and forwards them to the arm
    controller. Handles per-client teleop state and sends zero-velocity
    on disable/disconnect.

    Args:
        node: The parent ROS2 node for creating publishers and logging.
        namespace: The robot namespace prefix for topic routing.
        send_to_client: Async callback to send messages to a specific client.
    """

    def __init__(
        self,
        node: Node,
        namespace: str = "",
        send_to_client: Optional[Callable] = None,
    ):
        self._node = node
        self._namespace = namespace
        self._send_to_client = send_to_client

        # Per-client teleop state, keyed by client identifier.
        self._client_states: Dict[Any, TeleopClientState] = {}
        self._client_states_lock = threading.Lock()

        # Publisher for joint velocity commands via JointTrajectory.
        topic = f"{namespace}/arm_controller/joint_trajectory" if namespace else "/arm_controller/joint_trajectory"
        self._velocity_pub = node.create_publisher(
            JointTrajectory,
            topic,
            10,
        )

        self._node.get_logger().info(
            f"TeleopHandler initialized, publishing to {topic}"
        )

    def register_client(self, client_id: Any) -> None:
        """Register a new client with default teleop state (disabled).

        Args:
            client_id: Unique identifier for the WebSocket client.
        """
        with self._client_states_lock:
            self._client_states[client_id] = TeleopClientState()

    def unregister_client(self, client_id: Any) -> None:
        """Unregister a client and send zero-velocity if teleop was enabled.

        Ensures the arm stops moving when a client disconnects while
        teleop is active. (Req 5.8)

        Args:
            client_id: Unique identifier for the WebSocket client.
        """
        with self._client_states_lock:
            state = self._client_states.pop(client_id, None)

        if state is not None and state.enabled:
            # Send zero-velocity to stop the arm.
            self._publish_zero_velocity()

    def handle_teleop_mode(self, client_id: Any, data: Dict[str, Any]) -> Optional[str]:
        """Handle a teleop_mode message to enable/disable teleop for a client.

        When teleop is disabled, sends zero-velocity to halt the arm. (Req 5.7)

        Args:
            client_id: Unique identifier for the WebSocket client.
            data: Validated teleop_mode message dict with 'enabled' and
                  optional 'velocity_scale' fields.

        Returns:
            None on success, or a JSON error string if the client is unknown.
        """
        enabled = data["enabled"]
        velocity_scale = data.get("velocity_scale")

        with self._client_states_lock:
            state = self._client_states.get(client_id)
            if state is None:
                return serialize_error(
                    "INTERNAL_ERROR",
                    "Teleop handler: unknown client",
                )

            was_enabled = state.enabled
            state.enabled = enabled

            if velocity_scale is not None:
                state.velocity_scale = velocity_scale

        # If teleop was just disabled, send zero-velocity. (Req 5.7)
        if was_enabled and not enabled:
            self._publish_zero_velocity()

        return None

    def handle_teleop_velocity(
        self, client_id: Any, data: Dict[str, Any]
    ) -> Optional[str]:
        """Handle a teleop_velocity message by converting to joint velocities.

        Converts Cartesian velocity (linear + angular) to joint velocities
        via a simplified IK approach and publishes to the arm controller.
        If IK fails (singularity/boundary), the command is discarded and
        the arm holds its current position. (Req 5.9)

        Args:
            client_id: Unique identifier for the WebSocket client.
            data: Validated teleop_velocity message dict with 'linear' and
                  'angular' fields.

        Returns:
            None on success, or a JSON error string on failure.
        """
        with self._client_states_lock:
            state = self._client_states.get(client_id)
            if state is None:
                return serialize_error(
                    "INTERNAL_ERROR",
                    "Teleop handler: unknown client",
                )

            if not state.enabled:
                return serialize_error(
                    "TELEOP_DISABLED",
                    "Teleoperation is not enabled for this client",
                )

            velocity_scale = state.velocity_scale

        linear = data["linear"]  # [vx, vy, vz] m/s
        angular = data["angular"]  # [wx, wy, wz] rad/s

        # Check if this is a zero-velocity command (all inputs released).
        is_zero = all(v == 0.0 for v in linear) and all(w == 0.0 for w in angular)

        if is_zero:
            self._publish_zero_velocity()
            return None

        # Convert Cartesian velocity to joint velocities.
        joint_velocities = self._compute_joint_velocities(
            linear, angular, velocity_scale
        )

        if joint_velocities is None:
            # IK failure (singularity/boundary) — discard command,
            # arm holds current position. (Req 5.9)
            return serialize_error(
                "IK_VELOCITY_FAILED",
                "Cannot compute joint velocities for the requested "
                "Cartesian velocity (singularity or workspace boundary)",
            )

        # Publish joint velocity command to the arm controller.
        self._publish_joint_velocities(joint_velocities)
        return None

    def is_teleop_enabled(self, client_id: Any) -> bool:
        """Check whether teleop mode is enabled for a given client.

        Args:
            client_id: Unique identifier for the WebSocket client.

        Returns:
            True if teleop is enabled for the client, False otherwise.
        """
        with self._client_states_lock:
            state = self._client_states.get(client_id)
            return state.enabled if state is not None else False

    def get_velocity_scale(self, client_id: Any) -> float:
        """Get the velocity scale factor for a given client.

        Args:
            client_id: Unique identifier for the WebSocket client.

        Returns:
            The velocity scale factor, or the default if client is unknown.
        """
        with self._client_states_lock:
            state = self._client_states.get(client_id)
            return state.velocity_scale if state is not None else _DEFAULT_VELOCITY_SCALE

    def _compute_joint_velocities(
        self,
        linear: List[float],
        angular: List[float],
        velocity_scale: float,
    ) -> Optional[List[float]]:
        """Convert Cartesian velocity to joint velocities via simplified IK.

        Uses a simplified Jacobian-based mapping for the SO-100 5-DOF arm.
        The mapping distributes linear velocities across the arm joints and
        angular velocities to the wrist joints.

        For a full implementation, this would call the IK solver service to
        compute the Jacobian inverse at the current configuration. The
        simplified approach here provides a reasonable approximation for
        teleoperation.

        Args:
            linear: [vx, vy, vz] Cartesian linear velocity in m/s.
            angular: [wx, wy, wz] Cartesian angular velocity in rad/s.
            velocity_scale: Scale factor to apply to the velocity.

        Returns:
            A list of 5 joint velocities in rad/s, one per arm joint, in
            the order defined by ARM_JOINT_NAMES. Returns None if IK fails
            (e.g., computed velocities exceed safe limits).
        """
        vx, vy, vz = linear
        wx, wy, wz = angular

        # Apply velocity scale factor.
        vx *= velocity_scale
        vy *= velocity_scale
        vz *= velocity_scale
        wx *= velocity_scale
        wy *= velocity_scale
        wz *= velocity_scale

        # Simplified Jacobian-based mapping for SO-100 5-DOF arm:
        # Joint 0 (Shoulder_Rotation): controlled by XY motion
        # Joint 1 (Shoulder_Pitch): controlled by Z and forward reach
        # Joint 2 (Elbow): controlled by Z and forward reach
        # Joint 3 (Wrist_Pitch): controlled by pitch angular velocity
        # Joint 4 (Wrist_Roll): controlled by roll/yaw angular velocity

        # Map Cartesian velocities to joint velocities.
        # Shoulder rotation responds to lateral (X) velocity.
        shoulder_rotation_vel = -vx * 2.0

        # Shoulder pitch responds to Z (vertical) and Y (forward) velocity.
        shoulder_pitch_vel = -vz * 2.0 + vy * 1.5

        # Elbow responds to Z and Y in the opposite sense to shoulder.
        elbow_vel = vz * 1.5 - vy * 1.0

        # Wrist pitch responds to pitch angular velocity (wy).
        wrist_pitch_vel = wy * 1.0

        # Wrist roll responds to yaw/roll angular velocity (wz).
        wrist_roll_vel = wz * 1.0

        joint_velocities = [
            shoulder_rotation_vel,
            shoulder_pitch_vel,
            elbow_vel,
            wrist_pitch_vel,
            wrist_roll_vel,
        ]

        # Safety check: reject if any joint velocity exceeds safe limits.
        # This approximates IK failure at singularities or workspace boundaries.
        max_joint_velocity = 2.0  # rad/s safety limit
        for jv in joint_velocities:
            if abs(jv) > max_joint_velocity:
                return None

        return joint_velocities

    def _publish_joint_velocities(self, joint_velocities: List[float]) -> None:
        """Publish joint velocity commands to the arm controller.

        Constructs a JointTrajectory message with a single point that
        specifies the desired joint velocities and a short time horizon.

        Args:
            joint_velocities: List of 5 joint velocities in rad/s,
                ordered according to ARM_JOINT_NAMES.
        """
        traj_msg = JointTrajectory()
        traj_msg.header.stamp = self._node.get_clock().now().to_msg()
        traj_msg.joint_names = list(ARM_JOINT_NAMES)

        point = JointTrajectoryPoint()
        # For velocity mode, we set velocities and leave positions empty
        # (or set to current position). The controller interprets the
        # velocities for the specified duration.
        point.velocities = joint_velocities
        point.positions = []  # Empty: let the controller handle position
        point.time_from_start.sec = 0
        point.time_from_start.nanosec = int(
            _VELOCITY_COMMAND_DURATION_SEC * 1e9
        )

        traj_msg.points = [point]
        self._velocity_pub.publish(traj_msg)

    def _publish_zero_velocity(self) -> None:
        """Publish a zero-velocity command to halt all arm joints.

        Called when a client disables teleop or disconnects to ensure
        the arm stops moving. (Req 5.7, 5.8)
        """
        zero_velocities = [0.0] * len(ARM_JOINT_NAMES)
        self._publish_joint_velocities(zero_velocities)
