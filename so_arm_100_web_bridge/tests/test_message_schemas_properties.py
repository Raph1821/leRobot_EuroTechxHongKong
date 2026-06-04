"""Property-based tests for message_schemas module.

Uses Hypothesis to verify correctness properties of message serialization
and deserialization across all valid and invalid inputs.

Feature: so100-isaacsim-web-control
"""

import json
import math
import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.strategies import composite

from so_arm_100_web_bridge.message_schemas import (
    serialize_joint_state,
    deserialize_command,
)
from so_arm_100_web_bridge.joint_validator import ALL_JOINT_NAMES


# ---------------------------------------------------------------------------
# Helpers: Mock ROS2 JointState message for testing serialize_joint_state
# ---------------------------------------------------------------------------

class MockStamp:
    """Mock for builtin_interfaces/msg/Time."""

    def __init__(self, sec: int, nanosec: int):
        self.sec = sec
        self.nanosec = nanosec


class MockHeader:
    """Mock for std_msgs/msg/Header."""

    def __init__(self, stamp: MockStamp):
        self.stamp = stamp


class MockJointState:
    """Mock for sensor_msgs/msg/JointState."""

    def __init__(self, names, positions, velocities, efforts, sec=0, nanosec=0):
        self.header = MockHeader(MockStamp(sec, nanosec))
        self.name = names
        self.position = positions
        self.velocity = velocities
        self.effort = efforts


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for finite floats suitable for joint positions/velocities/efforts
finite_floats = st.floats(
    allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0
)

# Strategy for timestamps
timestamp_sec = st.integers(min_value=0, max_value=2_000_000_000)
timestamp_nanosec = st.integers(min_value=0, max_value=999_999_999)


@composite
def joint_state_messages(draw):
    """Generate valid mock JointState messages with 6 joints."""
    names = list(ALL_JOINT_NAMES)
    positions = [draw(finite_floats) for _ in range(6)]
    velocities = [draw(finite_floats) for _ in range(6)]
    efforts = [draw(finite_floats) for _ in range(6)]
    sec = draw(timestamp_sec)
    nanosec = draw(timestamp_nanosec)
    return MockJointState(names, positions, velocities, efforts, sec, nanosec)


@composite
def malformed_json_strings(draw):
    """Generate strings that are NOT valid JSON."""
    # Various ways to produce invalid JSON
    strategy = st.one_of(
        # Random text that won't parse as JSON
        st.text(min_size=1, max_size=100).filter(lambda s: _is_not_valid_json(s)),
        # Truncated JSON objects
        st.just("{\"type\": \"joint_command\""),
        st.just("{\"incomplete"),
        st.just("[1, 2, 3"),
        # Empty string
        st.just(""),
        # Just whitespace
        st.just("   "),
    )
    return draw(strategy)


@composite
def wrong_schema_messages(draw):
    """Generate valid JSON that does NOT conform to any recognized schema."""
    strategy = st.one_of(
        # Unknown message type
        st.just(json.dumps({"type": "unknown_type", "data": 123})),
        # Missing type field
        st.just(json.dumps({"joints": [{"name": "Shoulder_Rotation", "position": 0.5}]})),
        # Type is not a string
        st.just(json.dumps({"type": 12345})),
        # Valid type but missing required fields
        st.just(json.dumps({"type": "joint_command"})),
        st.just(json.dumps({"type": "gripper_command"})),
        st.just(json.dumps({"type": "trajectory_goal"})),
        # joint_command with invalid joint name
        st.just(json.dumps({
            "type": "joint_command",
            "joints": [{"name": "InvalidJoint", "position": 0.5}]
        })),
        # joint_command with non-numeric position
        st.just(json.dumps({
            "type": "joint_command",
            "joints": [{"name": "Shoulder_Rotation", "position": "not_a_number"}]
        })),
        # gripper_command with non-numeric position
        st.just(json.dumps({"type": "gripper_command", "position": "abc"})),
        # trajectory_goal with empty waypoints
        st.just(json.dumps({"type": "trajectory_goal", "waypoints": []})),
        # Non-object JSON (array, number, string, null, bool)
        st.just(json.dumps([1, 2, 3])),
        st.just(json.dumps(42)),
        st.just(json.dumps("just a string")),
        st.just(json.dumps(None)),
        st.just(json.dumps(True)),
        # joint_command with joints as non-array
        st.just(json.dumps({"type": "joint_command", "joints": "not_an_array"})),
        # trajectory_goal with waypoints missing positions
        st.just(json.dumps({
            "type": "trajectory_goal",
            "waypoints": [{"time_from_start": 1.0}]
        })),
        # trajectory_goal with negative time_from_start
        st.just(json.dumps({
            "type": "trajectory_goal",
            "waypoints": [{"positions": {"Shoulder_Rotation": 0.0}, "time_from_start": -1.0}]
        })),
    )
    return draw(strategy)


def _is_not_valid_json(s: str) -> bool:
    """Check that a string is NOT valid JSON."""
    try:
        json.loads(s)
        return False
    except (json.JSONDecodeError, ValueError):
        return True


# ---------------------------------------------------------------------------
# Property 1: JointState serialization round-trip
# ---------------------------------------------------------------------------
# For any valid JointState message containing 6 joint names, positions,
# velocities, and efforts arrays, serializing it to the WebSocket JSON format
# and then deserializing back should produce an equivalent JointState with all
# field values preserved (names, positions to float64 precision, velocities,
# and efforts).
#
# **Validates: Requirements 6.1**
# ---------------------------------------------------------------------------


class TestJointStateSerializationRoundTrip:
    """Feature: so100-isaacsim-web-control, Property 1: JointState serialization round-trip."""

    @given(msg=joint_state_messages())
    @settings(max_examples=200)
    def test_serialize_then_deserialize_preserves_fields(self, msg: MockJointState):
        """**Validates: Requirements 6.1**

        For any valid JointState message, serializing to JSON and parsing
        back preserves all fields: type, timestamp, joint names, positions,
        velocities, and efforts.
        """
        # Serialize
        json_str = serialize_joint_state(msg)

        # Deserialize (parse JSON back)
        parsed = json.loads(json_str)

        # Verify message type
        assert parsed["type"] == "joint_state"

        # Verify timestamp matches
        expected_timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        assert abs(parsed["timestamp"] - expected_timestamp) < 1e-6, (
            f"Timestamp mismatch: expected {expected_timestamp}, got {parsed['timestamp']}"
        )

        # Verify joint names preserved
        assert parsed["joints"]["names"] == list(msg.name)

        # Verify positions preserved (float64 precision)
        for i, (expected, actual) in enumerate(
            zip(msg.position, parsed["joints"]["positions"])
        ):
            assert expected == actual, (
                f"Position mismatch at index {i}: expected {expected}, got {actual}"
            )

        # Verify velocities preserved
        for i, (expected, actual) in enumerate(
            zip(msg.velocity, parsed["joints"]["velocities"])
        ):
            assert expected == actual, (
                f"Velocity mismatch at index {i}: expected {expected}, got {actual}"
            )

        # Verify efforts preserved
        for i, (expected, actual) in enumerate(
            zip(msg.effort, parsed["joints"]["efforts"])
        ):
            assert expected == actual, (
                f"Effort mismatch at index {i}: expected {expected}, got {actual}"
            )

    @given(msg=joint_state_messages())
    @settings(max_examples=200)
    def test_serialization_produces_valid_json(self, msg: MockJointState):
        """**Validates: Requirements 6.1**

        For any valid JointState message, serialization always produces
        a parseable JSON string with the correct structure.
        """
        json_str = serialize_joint_state(msg)

        # Must be valid JSON
        parsed = json.loads(json_str)

        # Must have required top-level keys
        assert "type" in parsed
        assert "timestamp" in parsed
        assert "joints" in parsed

        # Joints must have required sub-keys
        joints = parsed["joints"]
        assert "names" in joints
        assert "positions" in joints
        assert "velocities" in joints
        assert "efforts" in joints

        # All arrays must have same length as input names
        n = len(msg.name)
        assert len(joints["names"]) == n
        assert len(joints["positions"]) == n
        assert len(joints["velocities"]) == n
        assert len(joints["efforts"]) == n


# ---------------------------------------------------------------------------
# Property 3: Malformed message rejection
# ---------------------------------------------------------------------------
# For any WebSocket message that is not valid JSON, or is valid JSON but does
# not conform to a recognized message schema (missing required fields, unknown
# message type, unrecognized joint names), the message validator SHALL reject
# the message and produce an error response containing a human-readable reason
# string.
#
# **Validates: Requirements 6.6**
# ---------------------------------------------------------------------------


class TestMalformedMessageRejection:
    """Feature: so100-isaacsim-web-control, Property 3: Malformed message rejection."""

    @given(bad_json=malformed_json_strings())
    @settings(max_examples=200)
    def test_invalid_json_produces_error(self, bad_json: str):
        """**Validates: Requirements 6.6**

        For any string that is not valid JSON, deserialize_command SHALL
        return an error response with PARSE_ERROR code and a human-readable
        message.
        """
        result = deserialize_command(bad_json)

        assert result["type"] == "error", (
            f"Expected error response for invalid JSON: {bad_json!r}, got {result}"
        )
        assert result["code"] == "PARSE_ERROR", (
            f"Expected PARSE_ERROR code for invalid JSON: {bad_json!r}, "
            f"got code: {result['code']}"
        )
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0, "Error message must be non-empty"

    @given(bad_schema=wrong_schema_messages())
    @settings(max_examples=200)
    def test_wrong_schema_produces_error(self, bad_schema: str):
        """**Validates: Requirements 6.6**

        For any valid JSON that does not conform to a recognized message
        schema (missing fields, unknown type, invalid joint names),
        deserialize_command SHALL return an error response with a
        human-readable message string.
        """
        result = deserialize_command(bad_schema)

        assert result["type"] == "error", (
            f"Expected error response for invalid schema: {bad_schema}, got {result}"
        )
        assert result["code"] in ("PARSE_ERROR", "VALIDATION_ERROR"), (
            f"Expected PARSE_ERROR or VALIDATION_ERROR code, got: {result['code']}"
        )
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0, "Error message must be non-empty"
