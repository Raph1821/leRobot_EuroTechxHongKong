"""Cartesian controller for SO-100 arm end-effector control via IK.

This module implements the CartesianController class that handles Cartesian
goal messages from WebSocket clients. It validates workspace bounds, calls
the IK solver service to compute joint positions, and sends trajectory goals
to the arm controller. It also computes forward kinematics from joint states
and publishes end-effector pose updates.

Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 3.7, 3.9
"""

import asyncio
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from so_arm_100_web_bridge.joint_validator import ARM_JOINT_NAMES
from so_arm_100_web_bridge.message_schemas import (
    serialize_end_effector_pose,
    serialize_error,
    validate_workspace_position,
)


# Default orientation when not provided in a Cartesian goal.
_DEFAULT_ORIENTATION = [0.0, 0.0, 0.0]

# Default time_from_start for trajectory goals (seconds).
_DEFAULT_TIME_FROM_START = 2.0

# IK service call timeout in seconds (Requirement 3.9).
_IK_TIMEOUT_SECONDS = 5.0

# DH parameters for SO-100 5-DOF arm (approximate link lengths in meters).
# These are used for forward kinematics computation.
_LINK_LENGTHS = {
    "l1": 0.045,   # Base to shoulder height
    "l2": 0.105,   # Upper arm length
    "l3": 0.105,   # Forearm length
    "l4": 0.090,   # Wrist length to end-effector
}


class CartesianController:
    """Controller for Cartesian (task-space) end-effector commands.

    Handles:
    - Validating Cartesian goals against workspace bounds
    - Calling the IK solver service to compute joint positions
    - Constructing and sending trajectory goals on successful IK
    - Reporting IK failures (no solution, timeout, service unavailable)
    - Computing forward kinematics from joint states
    - Publishing end-effector pose messages to clients

    Args:
        node: The parent ROS2 node used for creating service clients and logging.
        namespace: The robot namespace for topic/service prefixing.
        send_to_client: Async callback to send messages to a WebSocket client.
        publish_trajectory: Callback to publish a JointTrajectory message.
    """

    def __init__(
        self,
        node: Node,
        namespace: str = "",
        send_to_client: Optional[Callable] = None,
        publish_trajectory: Optional[Callable] = None,
    ):
        self._node = node
        self._namespace = namespace
        self._send_to_client = send_to_client
        self._publish_trajectory = publish_trajectory
        self._logger = node.get_logger()

        # Build the IK service name with namespace.
        service_name = f"{namespace}/compute_ik" if namespace else "/compute_ik"
        self._ik_service_name = service_name

        # IK service client will be created lazily or by the bridge integrator.
        # We store a reference for use in handle_cartesian_goal.
        self._ik_client = None

        # Latest joint positions for FK computation (protected by lock).
        self._latest_joint_positions: Optional[Dict[str, float]] = None
        self._joint_positions_lock = threading.Lock()

        # Asyncio event loop reference (set by the bridge).
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._logger.info(
            f"CartesianController initialized for namespace '{namespace}' "
            f"with IK service: {service_name}"
        )

    @property
    def ik_service_name(self) -> str:
        """The fully-qualified IK service name."""
        return self._ik_service_name

    def set_ik_client(self, client) -> None:
        """Set the ROS2 service client for the IK solver.

        Args:
            client: A ROS2 service client for the compute_ik service.
        """
        self._ik_client = client

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio event loop for scheduling coroutines.

        Args:
            loop: The running asyncio event loop.
        """
        self._loop = loop

    async def handle_cartesian_goal(
        self,
        ws,
        command: Dict[str, Any],
    ) -> None:
        """Handle an incoming Cartesian goal command from a WebSocket client.

        Validates workspace bounds, calls IK solver, and on success sends
        a trajectory goal to the arm controller. On failure, sends an
        appropriate error message to the client.

        Args:
            ws: The WebSocket connection of the requesting client.
            command: Validated command dictionary with keys:
                - position: [x, y, z] in meters
                - orientation: [roll, pitch, yaw] in radians (defaults applied)
                - time_from_start: seconds (default 2.0)
        """
        position = command.get("position", [0.0, 0.0, 0.0])
        orientation = command.get("orientation", list(_DEFAULT_ORIENTATION))
        time_from_start = command.get("time_from_start", _DEFAULT_TIME_FROM_START)

        # Validate workspace bounds (Requirement 3.2).
        is_valid, error_msg = validate_workspace_position(position)
        if not is_valid:
            error_json = serialize_error("VALIDATION_ERROR", error_msg)
            await self._send_message(ws, error_json)
            return

        # Check IK service availability.
        if self._ik_client is None:
            error_json = serialize_error(
                "SERVICE_UNAVAILABLE",
                "IK solver service is not configured",
            )
            await self._send_message(ws, error_json)
            return

        if not self._ik_client.service_is_ready():
            error_json = serialize_error(
                "SERVICE_UNAVAILABLE",
                f"IK solver service '{self._ik_service_name}' is not available",
            )
            await self._send_message(ws, error_json)
            return

        # Call IK solver service (Requirement 3.1).
        try:
            joint_positions = await self._call_ik_service(
                position, orientation, time_from_start
            )
        except IKTimeoutError:
            # Requirement 3.9: IK service timeout.
            error_json = serialize_error(
                "IK_TIMEOUT",
                f"IK solver did not respond within {_IK_TIMEOUT_SECONDS} seconds",
            )
            await self._send_message(ws, error_json)
            return
        except IKNoSolutionError as e:
            # Requirement 3.6: IK solver found no valid solution.
            error_json = serialize_error(
                "IK_NO_SOLUTION",
                str(e) or "Target pose is unreachable",
            )
            await self._send_message(ws, error_json)
            return
        except IKServiceError as e:
            # General service error.
            error_json = serialize_error(
                "SERVICE_UNAVAILABLE",
                f"IK service error: {e}",
            )
            await self._send_message(ws, error_json)
            return

        # Requirement 3.3: Construct and send trajectory goal.
        self._send_trajectory_goal(joint_positions, time_from_start)

    async def _call_ik_service(
        self,
        position: List[float],
        orientation: List[float],
        time_from_start: float,
    ) -> List[float]:
        """Call the IK solver service and return joint positions.

        Args:
            position: [x, y, z] target position in meters.
            orientation: [roll, pitch, yaw] target orientation in radians.
            time_from_start: Duration for the trajectory in seconds.

        Returns:
            List of 5 joint positions (one per arm joint).

        Raises:
            IKTimeoutError: If the service does not respond within timeout.
            IKNoSolutionError: If the solver cannot find a valid solution.
            IKServiceError: If the service call fails for other reasons.
        """
        # Build the service request.
        # The request type depends on the service definition (ComputeIK.srv).
        # We use a generic approach since the actual srv type may vary.
        request = self._build_ik_request(position, orientation, time_from_start)

        # Call the service with timeout (Requirement 3.9).
        try:
            future = self._ik_client.call_async(request)

            # Wait for the response with timeout.
            response = await asyncio.wait_for(
                self._future_to_awaitable(future),
                timeout=_IK_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Cancel the pending request if possible.
            future.cancel()
            raise IKTimeoutError(
                f"IK service did not respond within {_IK_TIMEOUT_SECONDS}s"
            )
        except Exception as e:
            raise IKServiceError(f"Service call failed: {e}")

        # Parse the response.
        if not response.success:
            error_message = getattr(response, "error_message", "Target pose is unreachable")
            raise IKNoSolutionError(error_message)

        # Extract joint positions from response.
        joint_positions = list(response.joint_positions)
        if len(joint_positions) != 5:
            raise IKServiceError(
                f"Expected 5 joint positions, got {len(joint_positions)}"
            )

        return joint_positions

    def _build_ik_request(
        self,
        position: List[float],
        orientation: List[float],
        time_from_start: float,
    ):
        """Build an IK service request message.

        This creates a request object compatible with the ComputeIK.srv
        service definition.

        Args:
            position: [x, y, z] in meters.
            orientation: [roll, pitch, yaw] in radians.
            time_from_start: Duration for the trajectory in seconds.

        Returns:
            A service request object.
        """
        # Import the service type dynamically to avoid hard dependency
        # when the service message package is not yet built.
        try:
            from so_arm_100_interfaces.srv import ComputeIK
            request = ComputeIK.Request()
            request.position = position
            request.orientation = orientation
            request.time_from_start = time_from_start
            return request
        except ImportError:
            # Fallback: create a simple namespace object for testing.
            # In production, the service interface must be available.
            self._logger.warn(
                "ComputeIK service type not available. "
                "Using fallback request structure."
            )
            return _FallbackIKRequest(position, orientation, time_from_start)

    async def _future_to_awaitable(self, future):
        """Convert a ROS2 Future to an asyncio-awaitable coroutine.

        Args:
            future: A rclpy Future object from an async service call.

        Returns:
            The result of the future when it completes.
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, future.result)
        return result

    def _send_trajectory_goal(
        self,
        joint_positions: List[float],
        time_from_start: float,
    ) -> None:
        """Construct and publish a trajectory goal from IK solution.

        Creates a single-point JointTrajectory message with the solved
        joint positions and the specified time_from_start duration.

        Args:
            joint_positions: List of 5 joint positions from IK solver.
            time_from_start: Duration for reaching the target in seconds.
        """
        if self._publish_trajectory is None:
            self._logger.warn(
                "Cannot send trajectory goal: publish_trajectory callback not set"
            )
            return

        traj_msg = JointTrajectory()
        traj_msg.joint_names = list(ARM_JOINT_NAMES)

        point = JointTrajectoryPoint()
        point.positions = joint_positions
        point.velocities = [0.0] * len(joint_positions)

        # Convert time_from_start to Duration message fields.
        point.time_from_start.sec = int(time_from_start)
        point.time_from_start.nanosec = int(
            (time_from_start - int(time_from_start)) * 1e9
        )

        traj_msg.points = [point]

        self._publish_trajectory(traj_msg)

    def update_joint_positions(self, joint_positions: Dict[str, float]) -> None:
        """Update the cached joint positions from a joint state message.

        Called by the bridge node when a new joint state is received.
        Used for computing forward kinematics.

        Args:
            joint_positions: Dictionary mapping joint names to positions in radians.
        """
        with self._joint_positions_lock:
            self._latest_joint_positions = dict(joint_positions)

    def compute_forward_kinematics(self) -> Optional[Dict[str, List[float]]]:
        """Compute the end-effector pose from current joint positions.

        Uses a simplified forward kinematics model for the SO-100 5-DOF arm.
        Returns position [x, y, z] in meters and orientation [roll, pitch, yaw]
        in radians relative to the base_link frame.

        Returns:
            Dictionary with 'position' and 'orientation' keys, or None if
            no joint state is available.
        """
        with self._joint_positions_lock:
            if self._latest_joint_positions is None:
                return None
            positions = dict(self._latest_joint_positions)

        # Extract joint angles in order.
        try:
            q1 = positions.get("Shoulder_Rotation", 0.0)
            q2 = positions.get("Shoulder_Pitch", 0.0)
            q3 = positions.get("Elbow", 0.0)
            q4 = positions.get("Wrist_Pitch", 0.0)
            q5 = positions.get("Wrist_Roll", 0.0)
        except (KeyError, TypeError):
            return None

        # Forward kinematics for a 5-DOF arm (simplified model).
        # Joint 1: Shoulder rotation (about Z-axis at base)
        # Joint 2: Shoulder pitch (about Y-axis)
        # Joint 3: Elbow (about Y-axis)
        # Joint 4: Wrist pitch (about Y-axis)
        # Joint 5: Wrist roll (about X-axis at end-effector)
        l1 = _LINK_LENGTHS["l1"]
        l2 = _LINK_LENGTHS["l2"]
        l3 = _LINK_LENGTHS["l3"]
        l4 = _LINK_LENGTHS["l4"]

        # Compute end-effector position using geometric approach.
        # The arm operates in a plane rotated by q1 about Z.
        # Within that plane, the reach is determined by q2, q3, q4.
        pitch_total = q2 + q3 + q4

        # Radial distance from Z-axis in the arm plane.
        r = (l2 * math.cos(q2) + l3 * math.cos(q2 + q3) +
             l4 * math.cos(pitch_total))

        # Height (Z component).
        z = (l1 + l2 * math.sin(q2) + l3 * math.sin(q2 + q3) +
             l4 * math.sin(pitch_total))

        # Project onto world X-Y plane using shoulder rotation.
        x = r * math.cos(q1)
        y = r * math.sin(q1)

        # End-effector orientation (simplified).
        # Roll is determined by wrist roll joint.
        # Pitch is the cumulative pitch of the arm.
        # Yaw follows the shoulder rotation.
        roll = q5
        pitch = pitch_total
        yaw = q1

        return {
            "position": [x, y, z],
            "orientation": [roll, pitch, yaw],
        }

    def get_end_effector_pose_message(self) -> Optional[str]:
        """Compute FK and serialize the end-effector pose for WebSocket clients.

        Returns:
            JSON string of the end_effector_pose message, or None if
            joint positions are not available.
        """
        fk_result = self.compute_forward_kinematics()
        if fk_result is None:
            return None

        return serialize_end_effector_pose(
            position=fk_result["position"],
            orientation=fk_result["orientation"],
        )

    async def _send_message(self, ws, message: str) -> None:
        """Send a message to a WebSocket client.

        Uses the configured send_to_client callback if available,
        otherwise attempts direct send.

        Args:
            ws: The WebSocket connection.
            message: JSON string to send.
        """
        if self._send_to_client is not None:
            await self._send_to_client(ws, message)
        else:
            try:
                await ws.send(message)
            except Exception as e:
                self._logger.debug(f"Error sending to client: {e}")


# ─── IK Error Types ──────────────────────────────────────────────────────────


class IKTimeoutError(Exception):
    """Raised when the IK service does not respond within the timeout."""
    pass


class IKNoSolutionError(Exception):
    """Raised when the IK solver cannot find a valid solution."""
    pass


class IKServiceError(Exception):
    """Raised when the IK service call fails for a general reason."""
    pass


# ─── Fallback Request (for testing without service interfaces) ────────────────


class _FallbackIKRequest:
    """Minimal request object for when ComputeIK.srv is not available.

    This is used only during testing or development when the service
    interface package has not been built.
    """

    def __init__(
        self,
        position: List[float],
        orientation: List[float],
        time_from_start: float,
    ):
        self.position = position
        self.orientation = orientation
        self.time_from_start = time_from_start
