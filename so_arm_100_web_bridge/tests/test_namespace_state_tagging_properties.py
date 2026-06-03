"""Property-based tests for namespace state tagging.

Uses Hypothesis to verify that for any joint state from a namespaced topic,
the forwarded WebSocket message `robot_id` field exactly matches the source
namespace string.

Feature: web-control-expansion, Property 10: Namespace state tagging
"""

import json
import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings
from hypothesis import strategies as st

from so_arm_100_web_bridge.message_schemas import serialize_namespaced_joint_state


# ---------------------------------------------------------------------------
# Mock JointState message for testing
# ---------------------------------------------------------------------------


class MockStamp:
    """Mock ROS2 Time stamp."""

    def __init__(self, sec: int, nanosec: int):
        self.sec = sec
        self.nanosec = nanosec


class MockHeader:
    """Mock ROS2 Header."""

    def __init__(self, stamp: MockStamp):
        self.stamp = stamp


class MockJointState:
    """Mock ROS2 sensor_msgs/msg/JointState message."""

    def __init__(self, names, positions, velocities=None, efforts=None, sec=0, nanosec=0):
        self.header = MockHeader(MockStamp(sec, nanosec))
        self.name = names
        self.position = positions
        self.velocity = velocities if velocities is not None else []
        self.effort = efforts if efforts is not None else []


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for namespace strings: non-empty strings starting with "/"
# that represent valid ROS2 namespace prefixes (e.g., "/robot1", "/arm_left")
namespace_strategy = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_/"
    ),
    min_size=1,
    max_size=50,
).map(lambda s: "/" + s)

# Strategy for joint names (realistic robot joint names)
joint_name_strategy = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyz_"
    ),
    min_size=1,
    max_size=20,
)

# Strategy for joint positions (finite floats in typical joint range)
joint_position_strategy = st.floats(
    min_value=-6.28, max_value=6.28,
    allow_nan=False, allow_infinity=False,
)

# Strategy for generating a mock JointState message
joint_state_strategy = st.integers(min_value=1, max_value=6).flatmap(
    lambda n: st.fixed_dictionaries({
        "names": st.lists(joint_name_strategy, min_size=n, max_size=n),
        "positions": st.lists(joint_position_strategy, min_size=n, max_size=n),
        "velocities": st.lists(joint_position_strategy, min_size=n, max_size=n),
        "efforts": st.lists(joint_position_strategy, min_size=n, max_size=n),
        "sec": st.integers(min_value=0, max_value=2**31 - 1),
        "nanosec": st.integers(min_value=0, max_value=999999999),
    })
)


# ---------------------------------------------------------------------------
# Property 10: Namespace state tagging
# ---------------------------------------------------------------------------
# For any joint state message received from a namespaced topic, the forwarded
# WebSocket message SHALL contain a `robot_id` field whose value exactly
# matches the source namespace. Messages from different namespaces SHALL never
# share the same `robot_id` unless they originate from the same namespace.
#
# **Validates: Requirements 6.2**
# ---------------------------------------------------------------------------


class TestNamespaceStateTagging:
    """Feature: web-control-expansion, Property 10: Namespace state tagging."""

    @given(namespace=namespace_strategy, joint_data=joint_state_strategy)
    @settings(max_examples=200)
    def test_robot_id_matches_namespace(self, namespace: str, joint_data: dict):
        """**Validates: Requirements 6.2**

        For any namespace string (used as robot_id) and any mock joint state
        message, when serialize_namespaced_joint_state is called, the resulting
        JSON robot_id field exactly equals the input namespace string.
        """
        msg = MockJointState(
            names=joint_data["names"],
            positions=joint_data["positions"],
            velocities=joint_data["velocities"],
            efforts=joint_data["efforts"],
            sec=joint_data["sec"],
            nanosec=joint_data["nanosec"],
        )

        result_json = serialize_namespaced_joint_state(namespace, msg)
        result = json.loads(result_json)

        assert "robot_id" in result, (
            f"Serialized message must contain 'robot_id' field. Got keys: {list(result.keys())}"
        )
        assert result["robot_id"] == namespace, (
            f"robot_id should exactly match namespace. "
            f"Expected: {namespace!r}, Got: {result['robot_id']!r}"
        )

    @given(
        namespace_a=namespace_strategy,
        namespace_b=namespace_strategy,
        joint_data=joint_state_strategy,
    )
    @settings(max_examples=200)
    def test_different_namespaces_produce_different_robot_ids(
        self, namespace_a: str, namespace_b: str, joint_data: dict
    ):
        """**Validates: Requirements 6.2**

        Messages from different namespaces SHALL never share the same robot_id
        unless they originate from the same namespace. If two distinct namespace
        strings are used, their serialized robot_id fields must differ.
        """
        # Only test when namespaces are actually different
        if namespace_a == namespace_b:
            return

        msg = MockJointState(
            names=joint_data["names"],
            positions=joint_data["positions"],
            velocities=joint_data["velocities"],
            efforts=joint_data["efforts"],
            sec=joint_data["sec"],
            nanosec=joint_data["nanosec"],
        )

        result_a = json.loads(serialize_namespaced_joint_state(namespace_a, msg))
        result_b = json.loads(serialize_namespaced_joint_state(namespace_b, msg))

        assert result_a["robot_id"] != result_b["robot_id"], (
            f"Different namespaces must produce different robot_id values. "
            f"namespace_a={namespace_a!r}, namespace_b={namespace_b!r}, "
            f"but both produced robot_id={result_a['robot_id']!r}"
        )

    @given(namespace=namespace_strategy, joint_data=joint_state_strategy)
    @settings(max_examples=200)
    def test_message_type_is_joint_state(self, namespace: str, joint_data: dict):
        """**Validates: Requirements 6.2**

        The serialized message type field must be 'joint_state' for
        namespaced joint state messages.
        """
        msg = MockJointState(
            names=joint_data["names"],
            positions=joint_data["positions"],
            velocities=joint_data["velocities"],
            efforts=joint_data["efforts"],
            sec=joint_data["sec"],
            nanosec=joint_data["nanosec"],
        )

        result_json = serialize_namespaced_joint_state(namespace, msg)
        result = json.loads(result_json)

        assert result["type"] == "joint_state", (
            f"Message type must be 'joint_state', got: {result['type']!r}"
        )
