"""Property-based tests for spawn request validation.

Uses Hypothesis to verify that validate_spawn_request accepts requests if and
only if all values are within defined bounds and the dimension array length
matches the object type.

Feature: web-control-expansion, Property 3: Spawn request validation
"""

import math
import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, assume, note
from hypothesis import strategies as st
from hypothesis.strategies import composite

from so_arm_100_web_bridge.message_schemas import (
    validate_spawn_request,
    SpawnBounds,
    SPAWN_BOUNDS,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid object types and their expected dimension array lengths
OBJECT_TYPES = {"box": 3, "sphere": 1, "cylinder": 2}

# Default bounds for reference
BOUNDS = SPAWN_BOUNDS


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


@composite
def valid_dimensions(draw, object_type: str):
    """Generate valid dimensions for a given object type.

    Each dimension is in (0.0, 2.0] (exclusive lower, inclusive upper).
    """
    n = OBJECT_TYPES[object_type]
    dims = []
    for _ in range(n):
        # Use min_value slightly above 0 to satisfy exclusive lower bound
        dim = draw(
            st.floats(
                min_value=1e-10,
                max_value=BOUNDS.max_dimension,
                allow_nan=False,
                allow_infinity=False,
            ).filter(lambda x: x > BOUNDS.min_dimension)
        )
        dims.append(dim)
    return dims


@composite
def valid_position(draw):
    """Generate a valid position [x, y, z] within [-10.0, 10.0]."""
    return [
        draw(st.floats(
            min_value=BOUNDS.min_position,
            max_value=BOUNDS.max_position,
            allow_nan=False,
            allow_infinity=False,
        ))
        for _ in range(3)
    ]


@composite
def valid_orientation(draw):
    """Generate valid orientation [roll, pitch, yaw] within [-π, π]."""
    return [
        draw(st.floats(
            min_value=BOUNDS.min_orientation,
            max_value=BOUNDS.max_orientation,
            allow_nan=False,
            allow_infinity=False,
        ))
        for _ in range(3)
    ]


@composite
def valid_color(draw):
    """Generate valid color [r, g, b, a] within [0.0, 1.0]."""
    return [
        draw(st.floats(
            min_value=BOUNDS.min_color,
            max_value=BOUNDS.max_color,
            allow_nan=False,
            allow_infinity=False,
        ))
        for _ in range(4)
    ]


@composite
def valid_mass(draw):
    """Generate valid mass in (0.0, 50.0] (exclusive lower, inclusive upper)."""
    return draw(
        st.floats(
            min_value=1e-10,
            max_value=BOUNDS.max_mass,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.min_mass)
    )


@composite
def valid_spawn_request(draw):
    """Generate a complete valid spawn request."""
    object_type = draw(st.sampled_from(list(OBJECT_TYPES.keys())))
    dimensions = draw(valid_dimensions(object_type))
    position = draw(valid_position())
    orientation = draw(valid_orientation())
    color = draw(valid_color())
    mass = draw(valid_mass())

    return {
        "object_type": object_type,
        "dimensions": dimensions,
        "position": position,
        "orientation": orientation,
        "color": color,
        "mass": mass,
    }


@composite
def invalid_dimension_value(draw):
    """Generate a dimension that is out of bounds (<=0 or >2.0)."""
    return draw(st.one_of(
        # Zero or negative (violates > 0 constraint)
        st.floats(
            min_value=-100.0,
            max_value=0.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        # Exceeds max (>2.0)
        st.floats(
            min_value=2.0 + 1e-10,
            max_value=1000.0,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.max_dimension),
    ))


@composite
def invalid_position_value(draw):
    """Generate a position coordinate out of bounds (<-10 or >10)."""
    return draw(st.one_of(
        st.floats(
            min_value=-1000.0,
            max_value=-10.0 - 1e-10,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x < BOUNDS.min_position),
        st.floats(
            min_value=10.0 + 1e-10,
            max_value=1000.0,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.max_position),
    ))


@composite
def invalid_orientation_value(draw):
    """Generate an orientation value out of bounds (< -π or > π)."""
    return draw(st.one_of(
        st.floats(
            min_value=-100.0,
            max_value=-math.pi - 1e-10,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x < BOUNDS.min_orientation),
        st.floats(
            min_value=math.pi + 1e-10,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.max_orientation),
    ))


@composite
def invalid_color_value(draw):
    """Generate a color value out of bounds (<0.0 or >1.0)."""
    return draw(st.one_of(
        st.floats(
            min_value=-100.0,
            max_value=-1e-10,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x < BOUNDS.min_color),
        st.floats(
            min_value=1.0 + 1e-10,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.max_color),
    ))


@composite
def invalid_mass_value(draw):
    """Generate a mass value out of bounds (<=0 or >50)."""
    return draw(st.one_of(
        # Zero or negative (violates > 0 constraint)
        st.floats(
            min_value=-100.0,
            max_value=0.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        # Exceeds max (>50)
        st.floats(
            min_value=50.0 + 1e-10,
            max_value=1000.0,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda x: x > BOUNDS.max_mass),
    ))


# ---------------------------------------------------------------------------
# Helper: manually check if a request should be valid
# ---------------------------------------------------------------------------


def should_be_valid(data: dict) -> bool:
    """Determine if a spawn request should pass validation based on bounds.

    Returns True if and only if all values satisfy the defined constraints.
    """
    object_type = data.get("object_type")
    if object_type not in OBJECT_TYPES:
        return False

    dimensions = data.get("dimensions", [])
    if len(dimensions) != OBJECT_TYPES[object_type]:
        return False

    for dim in dimensions:
        if not isinstance(dim, (int, float)):
            return False
        if dim <= BOUNDS.min_dimension or dim > BOUNDS.max_dimension:
            return False

    position = data.get("position", [])
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return False
    for coord in position:
        if not isinstance(coord, (int, float)):
            return False
        if coord < BOUNDS.min_position or coord > BOUNDS.max_position:
            return False

    orientation = data.get("orientation", [])
    if not isinstance(orientation, (list, tuple)) or len(orientation) != 3:
        return False
    for angle in orientation:
        if not isinstance(angle, (int, float)):
            return False
        if angle < BOUNDS.min_orientation or angle > BOUNDS.max_orientation:
            return False

    color = data.get("color", [])
    if not isinstance(color, (list, tuple)) or len(color) != 4:
        return False
    for c in color:
        if not isinstance(c, (int, float)):
            return False
        if c < BOUNDS.min_color or c > BOUNDS.max_color:
            return False

    mass = data.get("mass")
    if not isinstance(mass, (int, float)):
        return False
    if mass <= BOUNDS.min_mass or mass > BOUNDS.max_mass:
        return False

    return True


# ---------------------------------------------------------------------------
# Property 3: Spawn request validation
# ---------------------------------------------------------------------------
# For any spawn request containing an object type (box, sphere, cylinder),
# dimensions, position (x, y, z), orientation (roll, pitch, yaw), color (RGBA),
# and mass, the validator SHALL accept the request if and only if:
# - all dimensions are in (0.0, 2.0]
# - all position coordinates are in [-10.0, 10.0]
# - all orientation values are in [-π, π]
# - all color values are in [0.0, 1.0]
# - mass is in (0.0, 50.0]
# - the dimension array length matches the object type (3 for box, 1 for
#   sphere, 2 for cylinder)
#
# **Validates: Requirements 2.2, 2.8**
# ---------------------------------------------------------------------------


class TestSpawnRequestValidation:
    """Feature: web-control-expansion, Property 3: Spawn request validation."""

    @given(data=valid_spawn_request())
    @settings(max_examples=200)
    def test_valid_requests_are_accepted(self, data: dict):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request where all values are within defined bounds
        and dimension array length matches object type, the validator
        SHALL accept the request.
        """
        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is True, (
            f"Expected valid request to be accepted but got error: {error_msg}\n"
            f"Request: {data}"
        )
        assert error_msg is None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        bad_dim=invalid_dimension_value(),
        position=valid_position(),
        orientation=valid_orientation(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_invalid_dimension_rejected(
        self, object_type, bad_dim, position, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with at least one dimension value outside
        (0.0, 2.0], the validator SHALL reject the request.
        """
        n = OBJECT_TYPES[object_type]
        # Replace the first dimension with an invalid value
        dimensions = [bad_dim] + [1.0] * (n - 1)

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid dimension {bad_dim}, "
            f"but request was accepted"
        )
        assert error_msg is not None
        assert isinstance(error_msg, str)
        assert len(error_msg) > 0

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        dimensions_strategy=st.data(),
        bad_coord=invalid_position_value(),
        orientation=valid_orientation(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_invalid_position_rejected(
        self, object_type, dimensions_strategy, bad_coord, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with at least one position coordinate outside
        [-10.0, 10.0], the validator SHALL reject the request.
        """
        dimensions = dimensions_strategy.draw(valid_dimensions(object_type))
        # Place bad coordinate at a random index
        idx = dimensions_strategy.draw(st.integers(min_value=0, max_value=2))
        position = [0.0, 0.0, 0.0]
        position[idx] = bad_coord

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid position[{idx}] = {bad_coord}, "
            f"but request was accepted"
        )
        assert error_msg is not None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        dimensions_strategy=st.data(),
        bad_angle=invalid_orientation_value(),
        position=valid_position(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_invalid_orientation_rejected(
        self, object_type, dimensions_strategy, bad_angle, position, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with at least one orientation value outside
        [-π, π], the validator SHALL reject the request.
        """
        dimensions = dimensions_strategy.draw(valid_dimensions(object_type))
        idx = dimensions_strategy.draw(st.integers(min_value=0, max_value=2))
        orientation = [0.0, 0.0, 0.0]
        orientation[idx] = bad_angle

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid orientation[{idx}] = {bad_angle}, "
            f"but request was accepted"
        )
        assert error_msg is not None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        dimensions_strategy=st.data(),
        bad_color=invalid_color_value(),
        position=valid_position(),
        orientation=valid_orientation(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_invalid_color_rejected(
        self, object_type, dimensions_strategy, bad_color, position, orientation, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with at least one color value outside
        [0.0, 1.0], the validator SHALL reject the request.
        """
        dimensions = dimensions_strategy.draw(valid_dimensions(object_type))
        idx = dimensions_strategy.draw(st.integers(min_value=0, max_value=3))
        color = [0.5, 0.5, 0.5, 1.0]
        color[idx] = bad_color

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid color[{idx}] = {bad_color}, "
            f"but request was accepted"
        )
        assert error_msg is not None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        dimensions_strategy=st.data(),
        bad_mass=invalid_mass_value(),
        position=valid_position(),
        orientation=valid_orientation(),
        color=valid_color(),
    )
    @settings(max_examples=200)
    def test_invalid_mass_rejected(
        self, object_type, dimensions_strategy, bad_mass, position, orientation, color
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with mass outside (0.0, 50.0], the validator
        SHALL reject the request.
        """
        dimensions = dimensions_strategy.draw(valid_dimensions(object_type))

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": bad_mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid mass = {bad_mass}, "
            f"but request was accepted"
        )
        assert error_msg is not None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        wrong_len_delta=st.integers(min_value=1, max_value=5),
        position=valid_position(),
        orientation=valid_orientation(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_wrong_dimension_count_rejected(
        self, object_type, wrong_len_delta, position, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request where the dimension array length does NOT
        match the object type (3 for box, 1 for sphere, 2 for cylinder),
        the validator SHALL reject the request.
        """
        expected_len = OBJECT_TYPES[object_type]
        # Create dimensions with wrong length (either too few or too many)
        wrong_len = expected_len + wrong_len_delta
        dimensions = [1.0] * wrong_len

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for {object_type} with {wrong_len} dimensions "
            f"(expected {expected_len}), but request was accepted"
        )
        assert error_msg is not None
        assert "dimension" in error_msg.lower() or str(expected_len) in error_msg

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        fewer_delta=st.integers(min_value=1, max_value=2),
        position=valid_position(),
        orientation=valid_orientation(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_too_few_dimensions_rejected(
        self, object_type, fewer_delta, position, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request where the dimension array is shorter than
        required by the object type, the validator SHALL reject it.
        """
        expected_len = OBJECT_TYPES[object_type]
        wrong_len = max(0, expected_len - fewer_delta)
        assume(wrong_len != expected_len)  # ensure it's actually wrong
        dimensions = [1.0] * wrong_len

        data = {
            "object_type": object_type,
            "dimensions": dimensions,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for {object_type} with {wrong_len} dimensions "
            f"(expected {expected_len}), but request was accepted"
        )
        assert error_msg is not None

    @given(
        invalid_type=st.text(min_size=1, max_size=20).filter(
            lambda t: t not in OBJECT_TYPES
        ),
        position=valid_position(),
        orientation=valid_orientation(),
        color=valid_color(),
        mass=valid_mass(),
    )
    @settings(max_examples=200)
    def test_invalid_object_type_rejected(
        self, invalid_type, position, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any spawn request with an unrecognized object_type, the
        validator SHALL reject the request.
        """
        data = {
            "object_type": invalid_type,
            "dimensions": [1.0],
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)

        assert is_valid is False, (
            f"Expected rejection for invalid object_type '{invalid_type}', "
            f"but request was accepted"
        )
        assert error_msg is not None

    @given(
        object_type=st.sampled_from(list(OBJECT_TYPES.keys())),
        dimensions=st.data(),
        position=st.lists(
            st.floats(
                min_value=-20.0, max_value=20.0,
                allow_nan=False, allow_infinity=False,
            ),
            min_size=3,
            max_size=3,
        ),
        orientation=st.lists(
            st.floats(
                min_value=-5.0, max_value=5.0,
                allow_nan=False, allow_infinity=False,
            ),
            min_size=3,
            max_size=3,
        ),
        color=st.lists(
            st.floats(
                min_value=-1.0, max_value=2.0,
                allow_nan=False, allow_infinity=False,
            ),
            min_size=4,
            max_size=4,
        ),
        mass=st.floats(
            min_value=-10.0, max_value=100.0,
            allow_nan=False, allow_infinity=False,
        ),
    )
    @settings(max_examples=300)
    def test_validation_accepts_iff_all_within_bounds(
        self, object_type, dimensions, position, orientation, color, mass
    ):
        """**Validates: Requirements 2.2, 2.8**

        For any combination of object_type, dimensions, position, orientation,
        color, and mass, the validator accepts if and only if all values are
        within defined bounds and dimension array length matches object type.

        This is the core biconditional property: valid ⟺ all constraints met.
        """
        dims = dimensions.draw(
            st.lists(
                st.floats(
                    min_value=-1.0, max_value=5.0,
                    allow_nan=False, allow_infinity=False,
                ),
                min_size=0,
                max_size=5,
            )
        )

        data = {
            "object_type": object_type,
            "dimensions": dims,
            "position": position,
            "orientation": orientation,
            "color": color,
            "mass": mass,
        }

        is_valid, error_msg = validate_spawn_request(data)
        expected_valid = should_be_valid(data)

        if expected_valid:
            assert is_valid is True, (
                f"Expected request to be accepted (all values in bounds) "
                f"but got error: {error_msg}\nRequest: {data}"
            )
            assert error_msg is None
        else:
            assert is_valid is False, (
                f"Expected request to be rejected (some values out of bounds) "
                f"but request was accepted.\nRequest: {data}"
            )
            assert error_msg is not None
            assert isinstance(error_msg, str)
            assert len(error_msg) > 0
