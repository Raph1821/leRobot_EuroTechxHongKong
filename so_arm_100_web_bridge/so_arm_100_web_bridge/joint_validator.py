"""Joint limit validation logic for SO-100 arm.

This module provides validation and clamping functions for joint positions,
ensuring commands stay within the defined limits for each joint.

Joint limits are sourced from the SO-100 5-DOF URDF
(so_arm_100_description/urdf/so_arm_100_5dof_arm.urdf.xacro).
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class JointConfig:
    """Configuration for a single robot joint."""

    name: str
    lower_limit: float  # radians
    upper_limit: float  # radians


# Joint configurations with limits from the URDF xacro file.
# The SO-100 arm has 5 DOF arm joints plus 1 gripper joint (6 total).
JOINT_CONFIGS = [
    JointConfig("Shoulder_Rotation", -1.96, 1.96),
    JointConfig("Shoulder_Pitch", -1.745, 1.745),
    JointConfig("Elbow", -1.5, 1.5),
    JointConfig("Wrist_Pitch", -1.658, 1.658),
    JointConfig("Wrist_Roll", -2.75, 2.75),
    JointConfig("Gripper", -0.1792, 1.5708),
]

# Lookup dictionary for quick access by joint name.
_JOINT_CONFIG_MAP = {jc.name: jc for jc in JOINT_CONFIGS}

# Valid joint names for arm joints (excludes Gripper).
ARM_JOINT_NAMES = [jc.name for jc in JOINT_CONFIGS if jc.name != "Gripper"]

# All valid joint names including Gripper.
ALL_JOINT_NAMES = [jc.name for jc in JOINT_CONFIGS]

# Gripper limits (convenience constants).
GRIPPER_LOWER_LIMIT = -0.1792
GRIPPER_UPPER_LIMIT = 1.5708


def validate_joint_command(name: str, position: float) -> Tuple[bool, Optional[str]]:
    """Validate a joint position command against the joint's defined limits.

    Args:
        name: The joint name (e.g., "Shoulder_Rotation", "Elbow").
        position: The commanded position in radians.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message) describing the issue.
    """
    config = _JOINT_CONFIG_MAP.get(name)
    if config is None:
        valid_names = ", ".join(ALL_JOINT_NAMES)
        return (False, f"Unknown joint name '{name}'. Valid joints: {valid_names}")

    if position < config.lower_limit or position > config.upper_limit:
        return (
            False,
            f"Joint '{name}' position {position} exceeds limit "
            f"[{config.lower_limit}, {config.upper_limit}]",
        )

    return (True, None)


def validate_gripper_command(position: float) -> Tuple[bool, Optional[str]]:
    """Validate a gripper position command against the gripper's defined limits.

    The gripper (Jaw) joint has a range of [-0.1792, 1.5708] radians.

    Args:
        position: The commanded gripper position in radians.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message) describing the issue.
    """
    if position < GRIPPER_LOWER_LIMIT or position > GRIPPER_UPPER_LIMIT:
        return (
            False,
            f"Gripper position {position} exceeds limit "
            f"[{GRIPPER_LOWER_LIMIT}, {GRIPPER_UPPER_LIMIT}]",
        )

    return (True, None)


def clamp_joint_value(name: str, value: float) -> float:
    """Clamp a joint value to the nearest valid limit for the given joint.

    If the value is below the lower limit, returns the lower limit.
    If the value is above the upper limit, returns the upper limit.
    If the value is within limits, returns the original value.

    Args:
        name: The joint name (e.g., "Shoulder_Rotation", "Gripper").
        value: The value to clamp in radians.

    Returns:
        The clamped value, guaranteed to be within
        [lower_limit, upper_limit] for the specified joint.

    Raises:
        ValueError: If the joint name is not recognized.
    """
    config = _JOINT_CONFIG_MAP.get(name)
    if config is None:
        valid_names = ", ".join(ALL_JOINT_NAMES)
        raise ValueError(f"Unknown joint name '{name}'. Valid joints: {valid_names}")

    if value < config.lower_limit:
        return config.lower_limit
    if value > config.upper_limit:
        return config.upper_limit
    return value
