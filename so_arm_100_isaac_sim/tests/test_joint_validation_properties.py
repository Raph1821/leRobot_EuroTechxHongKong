"""Property-based tests for joint position validation in the Isaac Sim bridge context.

Tests that the joint position validator correctly accepts positions within defined
limits and rejects positions outside those limits for all SO-100 arm joints.

Feature: so100-isaacsim-web-control
"""

import sys
import os

# Add the web bridge package to the path for testing
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "so_arm_100_web_bridge"),
)

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from so_arm_100_web_bridge.joint_validator import (
    JOINT_CONFIGS,
    ALL_JOINT_NAMES,
    validate_joint_command,
)

# Joint names used by the Isaac Sim bridge (all 6 joints)
JOINT_NAMES = ALL_JOINT_NAMES

# Joint limits as defined in the design document and URDF for Isaac Sim configuration
JOINT_LIMITS = {jc.name: (jc.lower_limit, jc.upper_limit) for jc in JOINT_CONFIGS}


# ---------------------------------------------------------------------------
# Property 2: Joint position validation (Isaac Sim bridge)
# ---------------------------------------------------------------------------
# For any joint name from the set {Shoulder_Rotation, Shoulder_Pitch, Elbow,
# Wrist_Pitch, Wrist_Roll, Gripper} and for any floating-point position value,
# the joint command validator accepts the command if and only if the position
# is within that joint's defined limits.
#
# Joint limits (from URDF / design doc):
#   Shoulder_Rotation: [-1.96, 1.96]
#   Shoulder_Pitch: [-1.745, 1.745]
#   Elbow: [-1.5, 1.5]
#   Wrist_Pitch: [-1.658, 1.658]
#   Wrist_Roll: [-2.75, 2.75]
#   Gripper: [-0.1792, 1.5708]
#
# **Validates: Requirements 4.6, 6.2, 6.3**
# ---------------------------------------------------------------------------


class TestJointPositionValidationProperty:
    """Feature: so100-isaacsim-web-control, Property 2: Joint position validation."""

    @given(
        joint_name=st.sampled_from(JOINT_NAMES),
        position=st.floats(allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_accepts_iff_within_limits(self, joint_name: str, position: float):
        """**Validates: Requirements 4.6, 6.2, 6.3**

        For any joint name and any finite float position value, the validator
        accepts if and only if position is within the joint's defined limits
        [lower_limit, upper_limit].
        """
        lower, upper = JOINT_LIMITS[joint_name]
        is_valid, error = validate_joint_command(joint_name, position)

        within_limits = lower <= position <= upper

        if within_limits:
            assert is_valid is True, (
                f"Expected valid for {joint_name}={position} "
                f"within [{lower}, {upper}], got error: {error}"
            )
            assert error is None
        else:
            assert is_valid is False, (
                f"Expected invalid for {joint_name}={position} "
                f"outside [{lower}, {upper}]"
            )
            assert error is not None
            assert joint_name in error

    @given(
        joint_name=st.sampled_from(JOINT_NAMES),
        position=st.floats(
            min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=200)
    def test_boundary_acceptance_rejection(self, joint_name: str, position: float):
        """**Validates: Requirements 4.6, 6.2, 6.3**

        For positions in a practical range around the joint limits, verify
        the validator correctly classifies boundary values.
        """
        lower, upper = JOINT_LIMITS[joint_name]
        is_valid, error = validate_joint_command(joint_name, position)

        if lower <= position <= upper:
            assert is_valid is True, (
                f"Position {position} is within [{lower}, {upper}] for "
                f"{joint_name} but was rejected: {error}"
            )
        else:
            assert is_valid is False, (
                f"Position {position} is outside [{lower}, {upper}] for "
                f"{joint_name} but was accepted"
            )

    @given(joint_name=st.sampled_from(JOINT_NAMES))
    @settings(max_examples=50)
    def test_exact_limits_are_accepted(self, joint_name: str):
        """**Validates: Requirements 4.6, 6.2, 6.3**

        The exact lower and upper limit values for any joint are always
        accepted by the validator.
        """
        lower, upper = JOINT_LIMITS[joint_name]

        is_valid_lower, error_lower = validate_joint_command(joint_name, lower)
        assert is_valid_lower is True, (
            f"Lower limit {lower} for {joint_name} was rejected: {error_lower}"
        )

        is_valid_upper, error_upper = validate_joint_command(joint_name, upper)
        assert is_valid_upper is True, (
            f"Upper limit {upper} for {joint_name} was rejected: {error_upper}"
        )
