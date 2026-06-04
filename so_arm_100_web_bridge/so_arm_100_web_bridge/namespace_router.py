"""Multi-robot namespace routing for the WebSocket bridge.

This module implements namespace-based routing of commands and joint states
for multiple robot instances. Each configured namespace gets independent
subscriptions and publishers, with strict isolation guaranteeing that
commands targeting one namespace never affect another.

The NamespaceRouter:
- Reads the `robot_namespaces` ROS2 parameter (list of namespace strings)
- Creates per-namespace subscriptions to joint state topics
- Routes commands to the correct namespace based on the client's active_robot_id
- Monitors namespace health (marks offline after 5s without joint state)
- Notifies clients within 2s when a namespace recovers
- Supports a minimum of 4 simultaneous namespaces

Requirements: 6.1, 6.2, 6.7, 6.8, 6.9
"""

import asyncio
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.publisher import Publisher
from rclpy.subscription import Subscription

from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from so_arm_100_web_bridge.message_schemas import (
    serialize_robot_list,
    serialize_robot_status_change,
    serialize_namespaced_joint_state,
)


# ─── Constants ───────────────────────────────────────────────────────────────

# Time in seconds without a joint state message before a namespace is offline.
HEALTH_TIMEOUT_SEC = 5.0

# Maximum time in seconds to notify clients after namespace recovers.
RECOVERY_NOTIFY_DEADLINE_SEC = 2.0

# Minimum number of simultaneous namespaces supported.
MIN_SUPPORTED_NAMESPACES = 4

# Standard ROS2 topic suffixes for command routing.
TOPIC_SUFFIXES = {
    "joint_states": "/joint_states",
    "joint_trajectory": "/arm_controller/joint_trajectory",
    "follow_joint_trajectory": "/arm_controller/follow_joint_trajectory",
    "gripper_cmd": "/gripper_controller/gripper_cmd",
    "compute_ik": "/compute_ik",
}


# ─── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class NamespaceState:
    """Tracks the state for a single robot namespace."""

    namespace: str
    status: str = "offline"  # "online" or "offline"
    last_joint_state_time: float = 0.0
    last_joint_state_msg: Optional[str] = None
    subscription: Optional[Subscription] = None
    trajectory_publisher: Optional[Publisher] = None


# ─── NamespaceRouter Class ───────────────────────────────────────────────────


class NamespaceRouter:
    """Routes commands and joint states across multiple robot namespaces.

    This class manages per-namespace ROS2 subscriptions and publishers,
    monitors health, and ensures strict command isolation between namespaces.

    Args:
        node: The parent ROS2 node (WebSocketBridgeNode) used to create
            subscriptions, publishers, and timers.
        namespaces: List of namespace strings (e.g., ["/robot1", "/robot2"]).
        on_joint_state: Async callback invoked when a namespaced joint state
            is received. Signature: (namespace: str, serialized_msg: str) -> None
        on_status_change: Async callback invoked when a namespace status
            changes. Signature: (robot_id: str, status: str) -> None
        loop: The asyncio event loop for scheduling async callbacks.
    """

    def __init__(
        self,
        node: Node,
        namespaces: List[str],
        on_joint_state: Callable[[str, str], Any],
        on_status_change: Callable[[str, str], Any],
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self._node = node
        self._on_joint_state = on_joint_state
        self._on_status_change = on_status_change
        self._loop = loop

        # Per-namespace state, keyed by namespace string.
        self._namespace_states: Dict[str, NamespaceState] = {}
        self._lock = threading.Lock()

        # QoS for joint state subscriptions (best effort, keep last 1).
        self._qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Initialize all configured namespaces.
        for ns in namespaces:
            self._setup_namespace(ns)

        # Create a timer for health monitoring (runs at 1 Hz).
        self._health_timer = self._node.create_timer(
            1.0, self._check_namespace_health
        )

        self._node.get_logger().info(
            f"NamespaceRouter initialized with {len(namespaces)} namespace(s): "
            f"{namespaces}"
        )

    # ─── Setup ───────────────────────────────────────────────────────────

    def _setup_namespace(self, namespace: str) -> None:
        """Create subscriptions and publishers for a single namespace.

        Args:
            namespace: The ROS2 namespace string (e.g., "/robot1").
        """
        state = NamespaceState(namespace=namespace)

        # Subscribe to /{namespace}/joint_states.
        topic = namespace + TOPIC_SUFFIXES["joint_states"]
        state.subscription = self._node.create_subscription(
            JointState,
            topic,
            lambda msg, ns=namespace: self._joint_state_callback(ns, msg),
            self._qos,
        )

        # Publisher for /{namespace}/arm_controller/joint_trajectory.
        traj_topic = namespace + TOPIC_SUFFIXES["joint_trajectory"]
        state.trajectory_publisher = self._node.create_publisher(
            JointTrajectory,
            traj_topic,
            10,
        )

        with self._lock:
            self._namespace_states[namespace] = state

        self._node.get_logger().debug(
            f"Namespace '{namespace}' configured: subscribed to {topic}, "
            f"publishing to {traj_topic}"
        )

    # ─── Joint State Handling ────────────────────────────────────────────

    def _joint_state_callback(self, namespace: str, msg: JointState) -> None:
        """Handle incoming joint state for a specific namespace.

        Updates the namespace state, checks for recovery from offline,
        serializes the message, and invokes the joint state callback.

        Args:
            namespace: The namespace this joint state belongs to.
            msg: The ROS2 JointState message.
        """
        now = time.time()
        serialized = serialize_namespaced_joint_state(namespace, msg)
        was_offline = False

        with self._lock:
            state = self._namespace_states.get(namespace)
            if state is None:
                return

            state.last_joint_state_time = now
            state.last_joint_state_msg = serialized

            if state.status == "offline":
                was_offline = True
                state.status = "online"

        # If recovering from offline, notify clients.
        if was_offline:
            self._node.get_logger().info(
                f"Namespace '{namespace}' recovered (now online)"
            )
            self._notify_status_change(namespace, "online")

        # Forward joint state to the callback.
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._invoke_joint_state_callback(namespace, serialized),
                self._loop,
            )
        else:
            # Synchronous fallback (for testing).
            self._on_joint_state(namespace, serialized)

    async def _invoke_joint_state_callback(
        self, namespace: str, serialized: str
    ) -> None:
        """Invoke the joint state callback asynchronously."""
        await self._on_joint_state(namespace, serialized)

    # ─── Health Monitoring ───────────────────────────────────────────────

    def _check_namespace_health(self) -> None:
        """Periodic health check for all namespaces.

        Called by the ROS2 timer at 1 Hz. Marks namespaces as offline
        if no joint state has been received within HEALTH_TIMEOUT_SEC.
        """
        now = time.time()
        newly_offline: List[str] = []

        with self._lock:
            for ns, state in self._namespace_states.items():
                if state.status == "online":
                    elapsed = now - state.last_joint_state_time
                    if elapsed > HEALTH_TIMEOUT_SEC:
                        state.status = "offline"
                        newly_offline.append(ns)

        # Notify clients for each namespace that went offline.
        for ns in newly_offline:
            self._node.get_logger().warn(
                f"Namespace '{ns}' marked offline "
                f"(no joint state for >{HEALTH_TIMEOUT_SEC}s)"
            )
            self._notify_status_change(ns, "offline")

    def _notify_status_change(self, robot_id: str, status: str) -> None:
        """Notify clients of a namespace status change.

        Args:
            robot_id: The namespace identifier.
            status: The new status ("online" or "offline").
        """
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._invoke_status_change_callback(robot_id, status),
                self._loop,
            )
        else:
            # Synchronous fallback (for testing).
            self._on_status_change(robot_id, status)

    async def _invoke_status_change_callback(
        self, robot_id: str, status: str
    ) -> None:
        """Invoke the status change callback asynchronously."""
        await self._on_status_change(robot_id, status)

    # ─── Command Routing ─────────────────────────────────────────────────

    def route_trajectory_command(
        self, robot_id: str, trajectory_msg: JointTrajectory
    ) -> bool:
        """Route a joint trajectory command to the specified namespace.

        Ensures command isolation: the trajectory is published ONLY to
        the specified namespace's topic. If the namespace is unknown or
        offline, the command is rejected.

        Args:
            robot_id: The target namespace (e.g., "/robot1").
            trajectory_msg: The JointTrajectory message to publish.

        Returns:
            True if the command was routed successfully, False otherwise.
        """
        with self._lock:
            state = self._namespace_states.get(robot_id)
            if state is None:
                self._node.get_logger().warn(
                    f"Cannot route command: unknown namespace '{robot_id}'"
                )
                return False
            if state.status == "offline":
                self._node.get_logger().warn(
                    f"Cannot route command: namespace '{robot_id}' is offline"
                )
                return False
            publisher = state.trajectory_publisher

        if publisher is None:
            return False

        publisher.publish(trajectory_msg)
        return True

    def get_topic_for_namespace(
        self, namespace: str, topic_key: str
    ) -> Optional[str]:
        """Get the full ROS2 topic path for a namespace and topic key.

        Ensures command isolation by constructing the path from the
        namespace prefix and the standard topic suffix.

        Args:
            namespace: The namespace prefix (e.g., "/robot1").
            topic_key: The topic key from TOPIC_SUFFIXES (e.g.,
                "joint_trajectory", "gripper_cmd", "compute_ik").

        Returns:
            The full topic path (e.g., "/robot1/arm_controller/joint_trajectory"),
            or None if the topic key is unrecognized.
        """
        suffix = TOPIC_SUFFIXES.get(topic_key)
        if suffix is None:
            return None
        return namespace + suffix

    # ─── Status and Queries ──────────────────────────────────────────────

    def get_robot_list(self) -> List[Dict[str, str]]:
        """Get the current list of robots with their statuses.

        Returns:
            A list of dictionaries with "robot_id" and "status" keys,
            suitable for serialization via serialize_robot_list.
        """
        with self._lock:
            return [
                {"robot_id": ns, "status": state.status}
                for ns, state in self._namespace_states.items()
            ]

    def get_robot_list_message(self) -> str:
        """Get a serialized robot list message for sending to clients.

        Returns:
            A JSON string conforming to the RobotListMessage schema.
        """
        return serialize_robot_list(self.get_robot_list())

    def is_namespace_valid(self, namespace: str) -> bool:
        """Check if a namespace is configured.

        Args:
            namespace: The namespace string to check.

        Returns:
            True if the namespace is in the configured list.
        """
        with self._lock:
            return namespace in self._namespace_states

    def is_namespace_online(self, namespace: str) -> bool:
        """Check if a namespace is online (receiving joint states).

        Args:
            namespace: The namespace string to check.

        Returns:
            True if the namespace is configured and online.
        """
        with self._lock:
            state = self._namespace_states.get(namespace)
            if state is None:
                return False
            return state.status == "online"

    def get_latest_joint_state(self, namespace: str) -> Optional[str]:
        """Get the most recently received joint state for a namespace.

        Args:
            namespace: The namespace to query.

        Returns:
            The serialized joint state JSON string, or None if no joint
            state has been received for this namespace.
        """
        with self._lock:
            state = self._namespace_states.get(namespace)
            if state is None:
                return None
            return state.last_joint_state_msg

    def get_namespace_count(self) -> int:
        """Get the number of configured namespaces.

        Returns:
            The count of configured namespaces.
        """
        with self._lock:
            return len(self._namespace_states)

    # ─── Cleanup ─────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Clean up all subscriptions, publishers, and timers.

        Should be called when the bridge node is shutting down.
        """
        if self._health_timer is not None:
            self._health_timer.cancel()
            self._health_timer = None

        with self._lock:
            for state in self._namespace_states.values():
                if state.subscription is not None:
                    self._node.destroy_subscription(state.subscription)
                    state.subscription = None
                if state.trajectory_publisher is not None:
                    self._node.destroy_publisher(state.trajectory_publisher)
                    state.trajectory_publisher = None

        self._node.get_logger().info("NamespaceRouter destroyed")
