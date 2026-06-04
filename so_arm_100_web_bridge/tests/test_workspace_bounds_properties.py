"""Property-based tests for workspace bounds validation.

Uses Hypothesis to verify that the workspace position validator accepts
positions if and only if they are within the defined workspace bounds:
x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3], z ∈ [0.0, 0.5].

Feature: web-control-expansion, Property 5: Workspace bounds validation
"""

import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from so_arm_100_web_bridge.message_schemas import (
    validate_workspace_position,
    WorkspaceBounds,
    WORKSPACE_BOUNDS,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for arbitrary finite floats (can be inside or outside bounds)
arbitrary_floats = st.floats(allow_nan=False, allow_infinity=False)

# Strategy for floats within workspace x bounds [-0.3, 0.3]
valid_x = st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False)

# Strategy for floats within workspace y bounds [-0.3, 0.3]
valid_y = st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False)

# Strategy for floats within workspace z bounds [0.0, 0.5]
valid_z = st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)

# Strategy for floats strictly outside workspace x bounds [-0.3, 0.3]
invalid_x = st.one_of(
    st.floats(min_value=-1e10, max_value=-0.3, allow_nan=False, allow_infinity=False,
              exclude_max=True),
    st.floats(min_value=0.3, max_value=1e10, allow_nan=False, allow_infinity=False,
              exclude_min=True),
)

# Strategy for floats strictly outside workspace y bounds [-0.3, 0.3]
invalid_y = st.one_of(
    st.floats(min_value=-1e10, max_value=-0.3, allow_nan=False, allow_infinity=False,
              exclude_max=True),
    st.floats(min_value=0.3, max_value=1e10, allow_nan=False, allow_infinity=False,
              exclude_min=True),
)

# Strategy for floats strictly outside workspace z bounds [0.0, 0.5]
invalid_z = st.one_of(
    st.floats(min_value=-1e10, max_value=0.0, allow_nan=False, allow_infinity=False,
              exclude_max=True),
    st.floats(min_value=0.5, max_value=1e10, allow_nan=False, allow_infinity=False,
              exclude_min=True),
)


# ---------------------------------------------------------------------------
# Property 5: Workspace bounds validation
# ---------------------------------------------------------------------------
# For any Cartesian goal position (x, y, z), the workspace validator SHALL
# accept the goal if and only if x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3], and
# z ∈ [0.0, 0.5] meters. All values outside these ranges SHALL be rejected
# with an appropriate error message.
#
# **Validates: Requirements 3.2**
# ---------------------------------------------------------------------------


class TestWorkspaceBoundsValidation:
    """Feature: web-control-expansion, Property 5: Workspace bounds validation."""

    @given(x=valid_x, y=valid_y, z=valid_z)
    @settings(max_examples=200)
    def test_valid_positions_accepted(self, x: float, y: float, z: float):
        """**Validates: Requirements 3.2**

        For any position where x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3], and
        z ∈ [0.0, 0.5], the validator SHALL accept the position.
        """
        position = [x, y, z]
        is_valid, error_msg = validate_workspace_position(position)

        assert is_valid is True, (
            f"Position {position} should be valid but was rejected: {error_msg}"
        )
        assert error_msg is None, (
            f"Valid position {position} should have no error message, got: {error_msg}"
        )

    @given(x=invalid_x, y=valid_y, z=valid_z)
    @settings(max_examples=200)
    def test_invalid_x_rejected(self, x: float, y: float, z: float):
        """**Validates: Requirements 3.2**

        For any position where x is outside [-0.3, 0.3], the validator
        SHALL reject the position with an appropriate error message.
        """
        position = [x, y, z]
        is_valid, error_msg = validate_workspace_position(position)

        assert is_valid is False, (
            f"Position {position} with x={x} outside bounds should be rejected"
        )
        assert error_msg is not None, (
            f"Rejected position should have an error message"
        )
        assert "x" in error_msg.lower() or "position" in error_msg.lower(), (
            f"Error message should reference position x: {error_msg}"
        )

    @given(x=valid_x, y=invalid_y, z=valid_z)
    @settings(max_examples=200)
    def test_invalid_y_rejected(self, x: float, y: float, z: float):
        """**Validates: Requirements 3.2**

        For any position where y is outside [-0.3, 0.3], the validator
        SHALL reject the position with an appropriate error message.
        """
        position = [x, y, z]
        is_valid, error_msg = validate_workspace_position(position)

        assert is_valid is False, (
            f"Position {position} with y={y} outside bounds should be rejected"
        )
        assert error_msg is not None, (
            f"Rejected position should have an error message"
        )
        assert "y" in error_msg.lower() or "position" in error_msg.lower(), (
            f"Error message should reference position y: {error_msg}"
        )

    @given(x=valid_x, y=valid_y, z=invalid_z)
    @settings(max_examples=200)
    def test_invalid_z_rejected(self, x: float, y: float, z: float):
        """**Validates: Requirements 3.2**

        For any position where z is outside [0.0, 0.5], the validator
        SHALL reject the position with an appropriate error message.
        """
        position = [x, y, z]
        is_valid, error_msg = validate_workspace_position(position)

        assert is_valid is False, (
            f"Position {position} with z={z} outside bounds should be rejected"
        )
        assert error_msg is not None, (
            f"Rejected position should have an error message"
        )
        assert "z" in error_msg.lower() or "position" in error_msg.lower(), (
            f"Error message should reference position z: {error_msg}"
        )

    @given(x=arbitrary_floats, y=arbitrary_floats, z=arbitrary_floats)
    @settings(max_examples=500)
    def test_acceptance_iff_within_bounds(self, x: float, y: float, z: float):
        """**Validates: Requirements 3.2**

        For any (x, y, z) position with finite float values, the validator
        accepts the position if and only if x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3],
        and z ∈ [0.0, 0.5].
        """
        position = [x, y, z]
        is_valid, error_msg = validate_workspace_position(position)

        x_in_bounds = WORKSPACE_BOUNDS.x_min <= x <= WORKSPACE_BOUNDS.x_max
        y_in_bounds = WORKSPACE_BOUNDS.y_min <= y <= WORKSPACE_BOUNDS.y_max
        z_in_bounds = WORKSPACE_BOUNDS.z_min <= z <= WORKSPACE_BOUNDS.z_max
        expected_valid = x_in_bounds and y_in_bounds and z_in_bounds

        assert is_valid == expected_valid, (
            f"Position {position}: expected valid={expected_valid}, got valid={is_valid}. "
            f"x_in_bounds={x_in_bounds}, y_in_bounds={y_in_bounds}, z_in_bounds={z_in_bounds}. "
            f"Error: {error_msg}"
        )

        if is_valid:
            assert error_msg is None, (
                f"Valid position should have no error message, got: {error_msg}"
            )
        else:
            assert error_msg is not None, (
                f"Invalid position {position} should have an error message"
            )
            assert len(error_msg) > 0, (
                f"Error message should be non-empty"
            )
