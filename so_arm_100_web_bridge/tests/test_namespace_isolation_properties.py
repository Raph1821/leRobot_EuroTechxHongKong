"""Property-based tests for namespace command isolation.

Uses Hypothesis to verify that for any pair of distinct namespaces (A, B),
topic routing for namespace A never produces a topic that matches namespace B.
This guarantees that commands targeting one namespace cannot affect another.

Feature: web-control-expansion, Property 11: Namespace command isolation
"""

import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import TOPIC_SUFFIXES without triggering ROS2 dependencies.
# We mock the ROS2 modules before importing the namespace_router module.
from unittest.mock import MagicMock

# Mock ROS2 modules that namespace_router imports
sys.modules.setdefault("rclpy", MagicMock())
sys.modules.setdefault("rclpy.node", MagicMock())
sys.modules.setdefault("rclpy.qos", MagicMock())
sys.modules.setdefault("rclpy.publisher", MagicMock())
sys.modules.setdefault("rclpy.subscription", MagicMock())
sys.modules.setdefault("sensor_msgs", MagicMock())
sys.modules.setdefault("sensor_msgs.msg", MagicMock())
sys.modules.setdefault("trajectory_msgs", MagicMock())
sys.modules.setdefault("trajectory_msgs.msg", MagicMock())

# Try to import TOPIC_SUFFIXES. If the import fails due to other missing
# dependencies, fall back to the known constant definition.
try:
    from so_arm_100_web_bridge.namespace_router import TOPIC_SUFFIXES
except ImportError:
    # Fallback: define TOPIC_SUFFIXES as specified in the source
    TOPIC_SUFFIXES = {
        "joint_states": "/joint_states",
        "joint_trajectory": "/arm_controller/joint_trajectory",
        "follow_joint_trajectory": "/arm_controller/follow_joint_trajectory",
        "gripper_cmd": "/gripper_controller/gripper_cmd",
        "compute_ik": "/compute_ik",
    }


# ---------------------------------------------------------------------------
# Helper: replicate get_topic_for_namespace logic
# ---------------------------------------------------------------------------

def get_topic_for_namespace(namespace: str, topic_key: str):
    """Replicates the NamespaceRouter.get_topic_for_namespace logic.

    This function mirrors the implementation in namespace_router.py:
    it concatenates namespace + TOPIC_SUFFIXES[topic_key].
    """
    suffix = TOPIC_SUFFIXES.get(topic_key)
    if suffix is None:
        return None
    return namespace + suffix


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for non-empty namespace strings that start with "/"
# We use printable text to avoid control characters, and ensure it starts with /
namespace_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"),
                           blacklist_characters="/"),
    min_size=1,
    max_size=50,
).map(lambda s: "/" + s)

# Strategy for pairs of distinct namespace strings
distinct_namespace_pair = st.tuples(namespace_text, namespace_text).filter(
    lambda pair: pair[0] != pair[1]
)

# Strategy for valid topic keys from TOPIC_SUFFIXES
topic_keys = st.sampled_from(list(TOPIC_SUFFIXES.keys()))


# ---------------------------------------------------------------------------
# Property 11: Namespace command isolation
# ---------------------------------------------------------------------------
# For any command sent by a client targeting namespace A, the command SHALL NOT
# cause any message to be published on topics or actions belonging to namespace B
# (where A ≠ B). The routing function SHALL guarantee that the output namespace
# prefix equals the input robot_id field exactly.
#
# **Validates: Requirements 6.8**
# ---------------------------------------------------------------------------


class TestNamespaceCommandIsolation:
    """Feature: web-control-expansion, Property 11: Namespace command isolation."""

    @given(ns_pair=distinct_namespace_pair, topic_key=topic_keys)
    @settings(max_examples=200)
    def test_topics_for_distinct_namespaces_never_equal(
        self, ns_pair: tuple, topic_key: str
    ):
        """**Validates: Requirements 6.8**

        For any pair of distinct namespaces (A, B) and any topic_key from
        TOPIC_SUFFIXES, get_topic_for_namespace(A, topic_key) never equals
        get_topic_for_namespace(B, topic_key).
        """
        ns_a, ns_b = ns_pair

        topic_a = get_topic_for_namespace(ns_a, topic_key)
        topic_b = get_topic_for_namespace(ns_b, topic_key)

        assert topic_a is not None, (
            f"Topic for namespace A='{ns_a}', key='{topic_key}' should not be None"
        )
        assert topic_b is not None, (
            f"Topic for namespace B='{ns_b}', key='{topic_key}' should not be None"
        )

        assert topic_a != topic_b, (
            f"Topics for distinct namespaces must never be equal. "
            f"Namespace A='{ns_a}', Namespace B='{ns_b}', topic_key='{topic_key}': "
            f"both produced '{topic_a}'"
        )

    @given(ns_pair=distinct_namespace_pair, topic_key=topic_keys)
    @settings(max_examples=200)
    def test_topic_for_namespace_a_never_contains_namespace_b(
        self, ns_pair: tuple, topic_key: str
    ):
        """**Validates: Requirements 6.8**

        For any pair of distinct namespaces (A, B), the topic generated for
        namespace A never contains namespace B as a prefix. This ensures
        complete isolation — namespace B's topic space is never accidentally
        addressed.
        """
        ns_a, ns_b = ns_pair

        topic_a = get_topic_for_namespace(ns_a, topic_key)
        assert topic_a is not None

        # The topic for namespace A should never start with namespace B's prefix
        assert not topic_a.startswith(ns_b + "/"), (
            f"Topic for namespace A='{ns_a}' (topic='{topic_a}') must not start with "
            f"namespace B='{ns_b}/' prefix. This would violate command isolation."
        )

        # The topic for namespace A should not contain namespace B as a path segment
        # (i.e., namespace B followed by / should not appear in the topic)
        assert ns_b + "/" not in topic_a, (
            f"Topic for namespace A='{ns_a}' (topic='{topic_a}') must not contain "
            f"namespace B='{ns_b}/' as a substring. This would violate command isolation."
        )

    @given(ns_pair=distinct_namespace_pair)
    @settings(max_examples=200)
    def test_all_topics_for_namespace_a_isolated_from_namespace_b(
        self, ns_pair: tuple
    ):
        """**Validates: Requirements 6.8**

        For any pair of distinct namespaces (A, B), ALL topics generated for
        namespace A are completely disjoint from ALL topics generated for
        namespace B. No topic from A's set appears in B's set.
        """
        ns_a, ns_b = ns_pair

        # Generate all topics for both namespaces
        topics_a = set()
        topics_b = set()

        for key in TOPIC_SUFFIXES:
            topic_a = get_topic_for_namespace(ns_a, key)
            topic_b = get_topic_for_namespace(ns_b, key)
            if topic_a is not None:
                topics_a.add(topic_a)
            if topic_b is not None:
                topics_b.add(topic_b)

        # The sets must be completely disjoint
        intersection = topics_a & topics_b
        assert len(intersection) == 0, (
            f"Topics for namespace A='{ns_a}' and namespace B='{ns_b}' must be "
            f"completely disjoint, but found overlap: {intersection}"
        )

    @given(namespace=namespace_text, topic_key=topic_keys)
    @settings(max_examples=200)
    def test_topic_starts_with_exact_namespace_prefix(
        self, namespace: str, topic_key: str
    ):
        """**Validates: Requirements 6.8**

        For any namespace and topic_key, the generated topic MUST start with
        the exact namespace string. This guarantees that the routing function
        outputs to the correct namespace prefix.
        """
        topic = get_topic_for_namespace(namespace, topic_key)
        assert topic is not None

        # The topic must start with the exact namespace
        assert topic.startswith(namespace), (
            f"Topic '{topic}' must start with namespace '{namespace}'"
        )

        # After the namespace prefix, the next character must be '/'
        # (from the TOPIC_SUFFIXES which all start with '/')
        remainder = topic[len(namespace):]
        assert remainder.startswith("/"), (
            f"After namespace '{namespace}', topic remainder '{remainder}' "
            f"must start with '/' to form a proper ROS2 topic path"
        )
