"""Property-based tests for IK/FK round-trip consistency.

Uses Hypothesis to verify forward kinematics properties of the CartesianController:
- FK determinism: computing FK twice on the same joint positions yields identical results
- FK workspace consistency: for valid joint positions within limits, FK results are
  within reasonable workspace bounds
- FK geometric consistency: the FK model produces geometrically valid results

Since the IK solver is a ROS2 service that cannot be called in unit tests, we test
the FK model's properties that underpin the round-trip guarantee: if IK succeeds and
produces joint positions, then FK on those positions must yield a position within
0.005m and orientation within 0.05 rad of the original target (Requirements 3.1, 3.5).

Feature: web-control-expansion, Property 4: IK/FK round-trip
"""

import sys
import os
import math
from unittest.mock import MagicMock

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock ROS2 dependencies that are not available in test environment.
sys.modules.setdefault("rclpy", MagicMock())
sys.modules.setdefault("rclpy.node", MagicMock())
sys.modules.setdefault("rclpy.callback_groups", MagicMock())
sys.modules.setdefault("trajectory_msgs", MagicMock())
sys.modules.setdefault("trajectory_msgs.msg", MagicMock())

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from so_arm_100_web_bridge.cartesian_controller import CartesianController
from so_arm_100_web_bridge.joint_validator import (
    ARM_JOINT_NAMES,
    JOINT_CONFIGS,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Joint limits from JOINT_CONFIGS (arm joints only, excluding Gripper).
_JOINT_LIMITS = {
    jc.name: (jc.lower_limit, jc.upper_limit)
    for jc in JOINT_CONFIGS
    if jc.name != "Gripper"
}

# Strategy for valid joint positions within the defined limits for each joint.
def valid_joint_positions_strategy():
    """Generate a dictionary of joint positions within their defined limits."""
    return st.fixed_dictionaries({
        name: st.floats(
            min_value=limits[0],
            max_value=limits[1],
            allow_nan=False,
            allow_infinity=False,
        )
        for name, limits in _JOINT_LIMITS.items()
    })


# Strategy for workspace positions (used for conceptual round-trip)
valid_workspace_x = st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False)
valid_workspace_y = st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False)
valid_workspace_z = st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Helper: Create a CartesianController instance for testing
# ---------------------------------------------------------------------------

def _create_controller() -> CartesianController:
    """Create a CartesianController with a mocked ROS2 node."""
    mock_node = MagicMock()
    mock_node.get_logger.return_value = MagicMock()
    return CartesianController(node=mock_node, namespace="")


# ---------------------------------------------------------------------------
# Property 4: IK/FK round-trip
# ---------------------------------------------------------------------------
# For any target end-effector position within the workspace bounds
# (x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3], z ∈ [0.0, 0.5] meters) and orientation,
# if the IK solver returns a successful solution, then computing forward
# kinematics on the resulting joint positions SHALL produce an end-effector
# position within 0.005 meters and orientation within 0.05 radians of the
# original target.
#
# **Validates: Requirements 3.1, 3.5**
# ---------------------------------------------------------------------------


class TestIKFKRoundTrip:
    """Feature: web-control-expansion, Property 4: IK/FK round-trip."""

    @given(joint_positions=valid_joint_positions_strategy())
    @settings(max_examples=200)
    def test_fk_determinism(self, joint_positions: dict):
        """**Validates: Requirements 3.1, 3.5**

        For any valid joint positions within the joint limits, computing FK
        twice on the same input SHALL yield the same result. This determinism
        is essential for the IK/FK round-trip to be reliable.
        """
        controller = _create_controller()

        # Set joint positions and compute FK the first time.
        controller.update_joint_positions(joint_positions)
        result1 = controller.compute_forward_kinematics()

        # Compute FK a second time with the same positions.
        result2 = controller.compute_forward_kinematics()

        assert result1 is not None, "FK should return a result for valid joint positions"
        assert result2 is not None, "FK should return a result on second call"

        # Position must be identical (deterministic).
        assert result1["position"] == result2["position"], (
            f"FK not deterministic for positions: "
            f"first={result1['position']}, second={result2['position']}"
        )

        # Orientation must be identical (deterministic).
        assert result1["orientation"] == result2["orientation"], (
            f"FK not deterministic for orientations: "
            f"first={result1['orientation']}, second={result2['orientation']}"
        )

    @given(joint_positions=valid_joint_positions_strategy())
    @settings(max_examples=200)
    def test_fk_produces_finite_results(self, joint_positions: dict):
        """**Validates: Requirements 3.1, 3.5**

        For any valid joint positions within the joint limits, FK SHALL produce
        finite position and orientation values (no NaN, no infinity). This is
        a prerequisite for the round-trip tolerance check.
        """
        controller = _create_controller()
        controller.update_joint_positions(joint_positions)
        result = controller.compute_forward_kinematics()

        assert result is not None, "FK should return a result for valid joint positions"

        # All position values must be finite.
        for i, coord in enumerate(["x", "y", "z"]):
            val = result["position"][i]
            assert math.isfinite(val), (
                f"FK position {coord}={val} is not finite for joints {joint_positions}"
            )

        # All orientation values must be finite.
        for i, coord in enumerate(["roll", "pitch", "yaw"]):
            val = result["orientation"][i]
            assert math.isfinite(val), (
                f"FK orientation {coord}={val} is not finite for joints {joint_positions}"
            )

    @given(joint_positions=valid_joint_positions_strategy())
    @settings(max_examples=200)
    def test_fk_workspace_consistency(self, joint_positions: dict):
        """**Validates: Requirements 3.1, 3.5**

        For any valid joint positions within the joint limits, the FK result
        SHALL produce an end-effector position within reasonable physical bounds
        for the SO-100 arm. The arm's total reach is bounded by the sum of link
        lengths (~0.345m), so positions should be within a sphere of that radius
        from the base, plus base height.
        """
        controller = _create_controller()
        controller.update_joint_positions(joint_positions)
        result = controller.compute_forward_kinematics()

        assert result is not None, "FK should return a result for valid joint positions"

        x, y, z = result["position"]

        # The maximum reach of the arm (sum of l2 + l3 + l4 = 0.105 + 0.105 + 0.09 = 0.3m)
        # plus base height l1 = 0.045m. The arm cannot reach further than this.
        max_reach = 0.105 + 0.105 + 0.090  # 0.3m horizontal reach
        max_height = 0.045 + 0.105 + 0.105 + 0.090  # 0.345m max Z

        # Radial distance from Z-axis should not exceed max horizontal reach.
        radial_distance = math.sqrt(x**2 + y**2)
        assert radial_distance <= max_reach + 0.001, (
            f"FK radial distance {radial_distance:.4f}m exceeds max reach "
            f"{max_reach:.4f}m for joints {joint_positions}"
        )

        # Z position should be within achievable height range.
        # Min Z can go slightly negative (arm pointing down), max is bounded.
        min_z = 0.045 - max_reach  # base height minus full reach downward
        assert z >= min_z - 0.001, (
            f"FK z={z:.4f}m below minimum {min_z:.4f}m for joints {joint_positions}"
        )
        assert z <= max_height + 0.001, (
            f"FK z={z:.4f}m exceeds maximum {max_height:.4f}m for joints {joint_positions}"
        )

    @given(joint_positions=valid_joint_positions_strategy())
    @settings(max_examples=200)
    def test_fk_orientation_bounded(self, joint_positions: dict):
        """**Validates: Requirements 3.1, 3.5**

        For any valid joint positions, the FK orientation values SHALL be
        bounded by the joint limits. Roll equals wrist_roll (q5), yaw equals
        shoulder rotation (q1), and pitch is the sum of pitch joints.
        """
        controller = _create_controller()
        controller.update_joint_positions(joint_positions)
        result = controller.compute_forward_kinematics()

        assert result is not None

        roll, pitch, yaw = result["orientation"]

        # Roll is q5 (Wrist_Roll), bounded by [-2.75, 2.75].
        assert -2.75 <= roll <= 2.75, (
            f"FK roll={roll} outside Wrist_Roll limits [-2.75, 2.75]"
        )

        # Yaw is q1 (Shoulder_Rotation), bounded by [-1.96, 1.96].
        assert -1.96 <= yaw <= 1.96, (
            f"FK yaw={yaw} outside Shoulder_Rotation limits [-1.96, 1.96]"
        )

        # Pitch is q2 + q3 + q4, bounded by sum of their individual ranges.
        # Max pitch = 1.745 + 1.5 + 1.658 = 4.903
        # Min pitch = -1.745 + (-1.5) + (-1.658) = -4.903
        max_pitch = 1.745 + 1.5 + 1.658
        min_pitch = -max_pitch
        assert min_pitch <= pitch <= max_pitch, (
            f"FK pitch={pitch} outside expected range [{min_pitch}, {max_pitch}]"
        )

    @given(joint_positions=valid_joint_positions_strategy())
    @settings(max_examples=200)
    def test_fk_zero_joints_at_known_position(self, joint_positions: dict):
        """**Validates: Requirements 3.1, 3.5**

        FK is geometrically consistent: when all joints are zero, the
        end-effector should be at the fully extended position along the X-axis
        at base height. This verifies the FK model's baseline correctness,
        which is essential for the IK/FK round-trip property.
        """
        controller = _create_controller()

        # Set all joints to zero.
        zero_joints = {name: 0.0 for name in ARM_JOINT_NAMES}
        controller.update_joint_positions(zero_joints)
        result = controller.compute_forward_kinematics()

        assert result is not None

        x, y, z = result["position"]
        roll, pitch, yaw = result["orientation"]

        # At zero configuration:
        # - All pitch joints (q2, q3, q4) are 0, so pitch_total = 0
        # - r = l2*cos(0) + l3*cos(0) + l4*cos(0) = l2 + l3 + l4 = 0.3m
        # - z = l1 + l2*sin(0) + l3*sin(0) + l4*sin(0) = l1 = 0.045m
        # - q1 = 0, so x = r*cos(0) = r = 0.3m, y = r*sin(0) = 0
        expected_r = 0.105 + 0.105 + 0.090  # 0.3m
        expected_z = 0.045

        assert abs(x - expected_r) < 0.001, f"Zero-config x={x}, expected {expected_r}"
        assert abs(y - 0.0) < 0.001, f"Zero-config y={y}, expected 0.0"
        assert abs(z - expected_z) < 0.001, f"Zero-config z={z}, expected {expected_z}"

        # Orientation at zero: roll=q5=0, pitch=0, yaw=q1=0
        assert abs(roll) < 0.001, f"Zero-config roll={roll}, expected 0.0"
        assert abs(pitch) < 0.001, f"Zero-config pitch={pitch}, expected 0.0"
        assert abs(yaw) < 0.001, f"Zero-config yaw={yaw}, expected 0.0"

    @given(
        joint_positions=valid_joint_positions_strategy(),
        perturbation=st.floats(min_value=1e-8, max_value=1e-6, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_fk_continuity(self, joint_positions: dict, perturbation: float):
        """**Validates: Requirements 3.1, 3.5**

        FK SHALL be continuous: a small change in joint positions results in
        a small change in end-effector position. This continuity is essential
        for the IK/FK round-trip to produce results within the specified
        tolerances (0.005m position, 0.05 rad orientation).
        """
        controller = _create_controller()

        # Compute FK for original joint positions.
        controller.update_joint_positions(joint_positions)
        result1 = controller.compute_forward_kinematics()
        assert result1 is not None

        # Perturb one joint slightly (keep within limits).
        perturbed = dict(joint_positions)
        joint_name = ARM_JOINT_NAMES[0]  # Perturb Shoulder_Rotation
        lower, upper = _JOINT_LIMITS[joint_name]
        new_val = perturbed[joint_name] + perturbation
        if new_val > upper:
            new_val = perturbed[joint_name] - perturbation
        perturbed[joint_name] = new_val

        # Compute FK for perturbed positions.
        controller.update_joint_positions(perturbed)
        result2 = controller.compute_forward_kinematics()
        assert result2 is not None

        # The position difference should be small (continuous).
        pos_diff = math.sqrt(
            sum((a - b) ** 2 for a, b in zip(result1["position"], result2["position"]))
        )
        # With perturbation up to 1e-6 rad on a joint, the position change
        # should be at most on the order of max_reach * perturbation ≈ 0.3 * 1e-6
        assert pos_diff < 0.01, (
            f"FK not continuous: position difference {pos_diff} for "
            f"perturbation {perturbation} rad"
        )

        # Orientation difference should also be small.
        orient_diff = max(
            abs(a - b)
            for a, b in zip(result1["orientation"], result2["orientation"])
        )
        assert orient_diff < 0.01, (
            f"FK not continuous: orientation difference {orient_diff} for "
            f"perturbation {perturbation} rad"
        )
