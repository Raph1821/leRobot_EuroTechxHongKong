"""Property-based tests for joint_validator module.

Uses Hypothesis to verify correctness properties across all valid inputs.

Feature: so100-isaacsim-web-control
"""

import math
import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from so_arm_100_web_bridge.joint_validator import (
    JOINT_CONFIGS,
    ALL_JOINT_NAMES,
    validate_joint_command,
    clamp_joint_value,
)

# Build a lookup dict for quick limit access in tests
_LIMITS = {jc.name: (jc.lower_limit, jc.upper_limit) for jc in JOINT_CONFIGS}


# ---------------------------------------------------------------------------
# Property 2: Joint position validation
# ---------------------------------------------------------------------------
# For any joint name from the defined set and for any floating-point position
# value, validate_joint_command accepts if and only if the position is within
# that joint's defined limits [lower_limit, upper_limit].
#
# **Validates: Requirements 4.6, 6.2, 6.3**
# ---------------------------------------------------------------------------


class TestJointPositionValidationProperty:
    """Feature: so100-isaacsim-web-control, Property 2: Joint position validation."""

    @given(
        joint_name=st.sampled_from(ALL_JOINT_NAMES),
        position=st.floats(allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_accepts_iff_within_limits(self, joint_name: str, position: float):
        """**Validates: Requirements 4.6, 6.2, 6.3**

        For any joint and any finite float position, validate_joint_command
        accepts the command if and only if position is within [lower, upper].
        """
        lower, upper = _LIMITS[joint_name]
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


# ---------------------------------------------------------------------------
# Property 5: Joint value clamping
# ---------------------------------------------------------------------------
# For any joint name and for any floating-point value, the clamped result is
# always within [lower_limit, upper_limit] for that joint. Additionally:
# - If value < lower_limit, result == lower_limit
# - If value > upper_limit, result == upper_limit
# - If lower_limit <= value <= upper_limit, result == value
#
# **Validates: Requirements 10.5**
# ---------------------------------------------------------------------------


class TestJointValueClampingProperty:
    """Feature: so100-isaacsim-web-control, Property 5: Joint value clamping."""

    @given(
        joint_name=st.sampled_from(ALL_JOINT_NAMES),
        value=st.floats(allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_clamped_result_within_limits(self, joint_name: str, value: float):
        """**Validates: Requirements 10.5**

        For any joint and any finite float value, the clamped result
        always satisfies lower_limit <= result <= upper_limit.
        """
        lower, upper = _LIMITS[joint_name]
        result = clamp_joint_value(joint_name, value)

        assert lower <= result <= upper, (
            f"Clamped value {result} for {joint_name} (input={value}) "
            f"not within [{lower}, {upper}]"
        )

    @given(
        joint_name=st.sampled_from(ALL_JOINT_NAMES),
        value=st.floats(allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_clamping_behavior_correctness(self, joint_name: str, value: float):
        """**Validates: Requirements 10.5**

        Verify the clamping function returns:
        - lower_limit if value < lower_limit
        - upper_limit if value > upper_limit
        - original value if within [lower_limit, upper_limit]
        """
        lower, upper = _LIMITS[joint_name]
        result = clamp_joint_value(joint_name, value)

        if value < lower:
            assert result == lower, (
                f"Expected lower_limit {lower} for {joint_name} "
                f"when value={value}, got {result}"
            )
        elif value > upper:
            assert result == upper, (
                f"Expected upper_limit {upper} for {joint_name} "
                f"when value={value}, got {result}"
            )
        else:
            assert result == value, (
                f"Expected original value {value} for {joint_name} "
                f"within [{lower}, {upper}], got {result}"
            )
