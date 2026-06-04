"""Property-based tests for namespace command routing.

Uses Hypothesis to verify that for any valid namespace string and any
command type (topic key), the resulting ROS2 topic path is exactly the
concatenation of the namespace prefix and the standard topic suffix.

Feature: web-control-expansion, Property 9: Namespace command routing
"""

import sys
import os
from unittest.mock import MagicMock

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock ROS2 dependencies that are not available in the test environment
sys.modules.setdefault("rclpy", MagicMock())
sys.modules.setdefault("rclpy.node", MagicMock())
sys.modules.setdefault("rclpy.qos", MagicMock())
sys.modules.setdefault("rclpy.publisher", MagicMock())
sys.modules.setdefault("rclpy.subscription", MagicMock())
sys.modules.setdefault("sensor_msgs", MagicMock())
sys.modules.setdefault("sensor_msgs.msg", MagicMock())
sys.modules.setdefault("trajectory_msgs", MagicMock())
sys.modules.setdefault("trajectory_msgs.msg", MagicMock())

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from so_arm_100_web_bridge.namespace_router import (
    TOPIC_SUFFIXES,
    NamespaceRouter,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for valid ROS2 namespace strings: non-empty, starts with "/"
# Uses text with a restricted alphabet typical of ROS2 namespace characters.
valid_namespace = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_/"
    ),
    min_size=1,
    max_size=50,
).map(lambda s: "/" + s.lstrip("/"))  # Ensure it always starts with exactly one "/"

# Strategy for valid topic keys from the TOPIC_SUFFIXES dictionary
valid_topic_key = st.sampled_from(list(TOPIC_SUFFIXES.keys()))

# Strategy for invalid topic keys (strings not in TOPIC_SUFFIXES)
invalid_topic_key = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s not in TOPIC_SUFFIXES)


# ---------------------------------------------------------------------------
# Property 9: Namespace command routing
# ---------------------------------------------------------------------------
# For any valid robot namespace string and for any command type
# (joint_command, gripper_command, trajectory_goal, cartesian_goal),
# the resulting ROS2 topic or service path SHALL be the concatenation
# of the namespace prefix and the standard topic suffix.
#
# **Validates: Requirements 6.1**
# ---------------------------------------------------------------------------


class TestNamespaceCommandRouting:
    """Feature: web-control-expansion, Property 9: Namespace command routing."""

    @given(namespace=valid_namespace, topic_key=valid_topic_key)
    @settings(max_examples=200)
    def test_topic_path_equals_namespace_plus_suffix(
        self, namespace: str, topic_key: str
    ):
        """**Validates: Requirements 6.1**

        For any valid namespace string (non-empty, starts with "/") and any
        topic_key from TOPIC_SUFFIXES, get_topic_for_namespace returns exactly
        namespace + TOPIC_SUFFIXES[topic_key].
        """
        # Call the function directly (it's a pure function, no ROS2 node needed)
        result = NamespaceRouter.get_topic_for_namespace(None, namespace, topic_key)

        expected = namespace + TOPIC_SUFFIXES[topic_key]

        assert result == expected, (
            f"For namespace='{namespace}' and topic_key='{topic_key}', "
            f"expected '{expected}' but got '{result}'"
        )

    @given(namespace=valid_namespace, topic_key=valid_topic_key)
    @settings(max_examples=200)
    def test_result_starts_with_namespace(
        self, namespace: str, topic_key: str
    ):
        """**Validates: Requirements 6.1**

        For any valid namespace and topic_key, the resulting topic path
        must start with the namespace prefix, ensuring routing isolation.
        """
        result = NamespaceRouter.get_topic_for_namespace(None, namespace, topic_key)

        assert result is not None, (
            f"Valid topic_key '{topic_key}' should not return None"
        )
        assert result.startswith(namespace), (
            f"Topic path '{result}' should start with namespace '{namespace}'"
        )

    @given(namespace=valid_namespace, topic_key=valid_topic_key)
    @settings(max_examples=200)
    def test_result_ends_with_standard_suffix(
        self, namespace: str, topic_key: str
    ):
        """**Validates: Requirements 6.1**

        For any valid namespace and topic_key, the resulting topic path
        must end with the standard suffix for that command type.
        """
        result = NamespaceRouter.get_topic_for_namespace(None, namespace, topic_key)

        expected_suffix = TOPIC_SUFFIXES[topic_key]
        assert result is not None, (
            f"Valid topic_key '{topic_key}' should not return None"
        )
        assert result.endswith(expected_suffix), (
            f"Topic path '{result}' should end with suffix '{expected_suffix}'"
        )

    @given(namespace=valid_namespace, topic_key=invalid_topic_key)
    @settings(max_examples=100)
    def test_invalid_topic_key_returns_none(
        self, namespace: str, topic_key: str
    ):
        """**Validates: Requirements 6.1**

        For any namespace and an unrecognized topic_key (not in TOPIC_SUFFIXES),
        get_topic_for_namespace returns None.
        """
        result = NamespaceRouter.get_topic_for_namespace(None, namespace, topic_key)

        assert result is None, (
            f"Invalid topic_key '{topic_key}' should return None, got '{result}'"
        )
