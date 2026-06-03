"""Unit tests for joint_validator module."""

import sys
import os

# Add the package to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from so_arm_100_web_bridge.joint_validator import (
    JOINT_CONFIGS,
    ALL_JOINT_NAMES,
    ARM_JOINT_NAMES,
    GRIPPER_LOWER_LIMIT,
    GRIPPER_UPPER_LIMIT,
    validate_joint_command,
    validate_gripper_command,
    clamp_joint_value,
)

import pytest


class TestJointConfigs:
    """Tests for JOINT_CONFIGS data."""

    def test_has_six_joints(self):
        assert len(JOINT_CONFIGS) == 6

    def test_joint_names_match_urdf(self):
        expected = [
            "Shoulder_Rotation",
            "Shoulder_Pitch",
            "Elbow",
            "Wrist_Pitch",
            "Wrist_Roll",
            "Gripper",
        ]
        assert [jc.name for jc in JOINT_CONFIGS] == expected

    def test_arm_joint_names_excludes_gripper(self):
        assert "Gripper" not in ARM_JOINT_NAMES
        assert len(ARM_JOINT_NAMES) == 5

    def test_all_joint_names_includes_gripper(self):
        assert "Gripper" in ALL_JOINT_NAMES
        assert len(ALL_JOINT_NAMES) == 6

    def test_limits_match_urdf(self):
        """Verify limits match the URDF xacro file exactly."""
        limits = {jc.name: (jc.lower_limit, jc.upper_limit) for jc in JOINT_CONFIGS}
        assert limits["Shoulder_Rotation"] == (-1.96, 1.96)
        assert limits["Shoulder_Pitch"] == (-1.745, 1.745)
        assert limits["Elbow"] == (-1.5, 1.5)
        assert limits["Wrist_Pitch"] == (-1.658, 1.658)
        assert limits["Wrist_Roll"] == (-2.75, 2.75)
        assert limits["Gripper"] == (-0.1792, 1.5708)

    def test_lower_limit_less_than_upper_for_all(self):
        for jc in JOINT_CONFIGS:
            assert jc.lower_limit < jc.upper_limit, f"{jc.name} limits invalid"


class TestValidateJointCommand:
    """Tests for validate_joint_command function."""

    def test_valid_position_at_zero(self):
        is_valid, error = validate_joint_command("Shoulder_Rotation", 0.0)
        assert is_valid is True
        assert error is None

    def test_valid_at_lower_limit(self):
        is_valid, error = validate_joint_command("Elbow", -1.5)
        assert is_valid is True
        assert error is None

    def test_valid_at_upper_limit(self):
        is_valid, error = validate_joint_command("Elbow", 1.5)
        assert is_valid is True
        assert error is None

    def test_invalid_below_lower_limit(self):
        is_valid, error = validate_joint_command("Elbow", -1.6)
        assert is_valid is False
        assert error is not None
        assert "Elbow" in error
        assert "-1.5" in error

    def test_invalid_above_upper_limit(self):
        is_valid, error = validate_joint_command("Shoulder_Rotation", 2.0)
        assert is_valid is False
        assert error is not None
        assert "Shoulder_Rotation" in error

    def test_unknown_joint_name(self):
        is_valid, error = validate_joint_command("NonExistentJoint", 0.0)
        assert is_valid is False
        assert error is not None
        assert "Unknown joint name" in error
        assert "NonExistentJoint" in error

    def test_gripper_joint_can_be_validated(self):
        is_valid, error = validate_joint_command("Gripper", 1.0)
        assert is_valid is True
        assert error is None

    def test_gripper_joint_invalid_above(self):
        is_valid, error = validate_joint_command("Gripper", 2.0)
        assert is_valid is False
        assert error is not None


class TestValidateGripperCommand:
    """Tests for validate_gripper_command function."""

    def test_valid_at_zero(self):
        is_valid, error = validate_gripper_command(0.0)
        assert is_valid is True
        assert error is None

    def test_valid_at_lower_limit(self):
        is_valid, error = validate_gripper_command(-0.1792)
        assert is_valid is True
        assert error is None

    def test_valid_at_upper_limit(self):
        is_valid, error = validate_gripper_command(1.5708)
        assert is_valid is True
        assert error is None

    def test_invalid_below_lower(self):
        is_valid, error = validate_gripper_command(-0.2)
        assert is_valid is False
        assert error is not None
        assert "-0.1792" in error

    def test_invalid_above_upper(self):
        is_valid, error = validate_gripper_command(1.6)
        assert is_valid is False
        assert error is not None
        assert "1.5708" in error

    def test_valid_mid_range(self):
        is_valid, error = validate_gripper_command(0.7)
        assert is_valid is True
        assert error is None


class TestClampJointValue:
    """Tests for clamp_joint_value function."""

    def test_value_within_limits_unchanged(self):
        assert clamp_joint_value("Elbow", 0.5) == 0.5

    def test_value_below_lower_limit_clamped(self):
        assert clamp_joint_value("Elbow", -3.0) == -1.5

    def test_value_above_upper_limit_clamped(self):
        assert clamp_joint_value("Elbow", 3.0) == 1.5

    def test_value_at_lower_limit_unchanged(self):
        assert clamp_joint_value("Shoulder_Rotation", -1.96) == -1.96

    def test_value_at_upper_limit_unchanged(self):
        assert clamp_joint_value("Shoulder_Rotation", 1.96) == 1.96

    def test_gripper_clamped_above(self):
        assert clamp_joint_value("Gripper", 2.0) == 1.5708

    def test_gripper_clamped_below(self):
        assert clamp_joint_value("Gripper", -1.0) == -0.1792

    def test_unknown_joint_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown joint name"):
            clamp_joint_value("FakeJoint", 0.0)

    def test_clamp_result_always_within_limits(self):
        """For all joints, clamped values should be within bounds."""
        for jc in JOINT_CONFIGS:
            result_low = clamp_joint_value(jc.name, -999.0)
            assert result_low == jc.lower_limit

            result_high = clamp_joint_value(jc.name, 999.0)
            assert result_high == jc.upper_limit

            result_mid = clamp_joint_value(jc.name, 0.0)
            assert jc.lower_limit <= result_mid <= jc.upper_limit
