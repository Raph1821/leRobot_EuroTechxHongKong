"""WebSocket message serialization and validation schemas.

This module defines the JSON message schemas for communication between
the WebSocket bridge and browser clients, including serialization of
ROS2 messages and validation of incoming commands.

Message Protocol (matching web_interface/src/types.ts):
  Server → Client: joint_state, error, trajectory_status, sim_status,
                   camera_frame, spawn_confirm, delete_confirm,
                   end_effector_pose, episode_list, recording_status,
                   robot_list, robot_status_change
  Client → Server: joint_command, gripper_command, trajectory_goal,
                   camera_stream_control, spawn_object, delete_object,
                   cartesian_goal, episode_control, teleop_velocity,
                   teleop_mode, select_robot
"""

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from so_arm_100_web_bridge.joint_validator import (
    ALL_JOINT_NAMES,
    ARM_JOINT_NAMES,
    validate_gripper_command,
    validate_joint_command,
)


# ─── Validation Bounds Dataclasses ───────────────────────────────────────────


@dataclass(frozen=True)
class SpawnBounds:
    """Validation bounds for spawn object requests."""

    min_dimension: float = 0.0  # exclusive lower bound (> 0)
    max_dimension: float = 2.0  # inclusive upper bound
    min_position: float = -10.0  # inclusive
    max_position: float = 10.0  # inclusive
    min_orientation: float = -math.pi  # -π, inclusive
    max_orientation: float = math.pi  # +π, inclusive
    min_mass: float = 0.0  # exclusive lower bound (> 0)
    max_mass: float = 50.0  # inclusive upper bound
    min_color: float = 0.0  # inclusive
    max_color: float = 1.0  # inclusive


@dataclass(frozen=True)
class WorkspaceBounds:
    """Reachable workspace of the SO-100 arm in base_link frame."""

    x_min: float = -0.3
    x_max: float = 0.3
    y_min: float = -0.3
    y_max: float = 0.3
    z_min: float = 0.0
    z_max: float = 0.5


# Module-level default instances for use by validators.
SPAWN_BOUNDS = SpawnBounds()
WORKSPACE_BOUNDS = WorkspaceBounds()

# Expected dimension array lengths per object type.
_DIMENSION_LENGTHS = {
    "box": 3,       # [length, width, height]
    "sphere": 1,    # [radius]
    "cylinder": 2,  # [radius, height]
}

# Valid object types for spawn requests.
_VALID_OBJECT_TYPES = set(_DIMENSION_LENGTHS.keys())

# Valid episode control commands.
_VALID_EPISODE_COMMANDS = {
    "start_recording",
    "stop_recording",
    "discard_recording",
    "list_episodes",
    "replay_episode",
    "stop_replay",
}

# Valid message types that can be received from clients.
_VALID_CLIENT_MESSAGE_TYPES = {
    "joint_command",
    "gripper_command",
    "trajectory_goal",
    "camera_stream_control",
    "spawn_object",
    "delete_object",
    "cartesian_goal",
    "episode_control",
    "teleop_velocity",
    "teleop_mode",
    "select_robot",
}


def serialize_joint_state(msg) -> str:
    """Serialize a ROS2 sensor_msgs/JointState message to JSON.

    Converts a ROS2 JointState message into the WebSocket JSON format
    expected by the web interface client.

    Args:
        msg: A ROS2 sensor_msgs/msg/JointState message with fields:
            - header.stamp (with sec and nanosec)
            - name: list of joint name strings
            - position: list of float positions
            - velocity: list of float velocities
            - effort: list of float efforts

    Returns:
        A JSON string conforming to the JointStateMessage schema:
        {
            "type": "joint_state",
            "timestamp": <float seconds>,
            "joints": {
                "names": [...],
                "positions": [...],
                "velocities": [...],
                "efforts": [...]
            }
        }
    """
    # Extract timestamp from ROS2 header.
    stamp = msg.header.stamp
    timestamp = stamp.sec + stamp.nanosec * 1e-9

    # Build arrays, padding with 0.0 if velocity/effort are shorter than names.
    names = list(msg.name)
    positions = list(msg.position)
    velocities = list(msg.velocity) if msg.velocity else [0.0] * len(names)
    efforts = list(msg.effort) if msg.effort else [0.0] * len(names)

    # Pad velocities and efforts to match the number of joints if needed.
    while len(velocities) < len(names):
        velocities.append(0.0)
    while len(efforts) < len(names):
        efforts.append(0.0)

    payload = {
        "type": "joint_state",
        "timestamp": timestamp,
        "joints": {
            "names": names,
            "positions": positions,
            "velocities": velocities,
            "efforts": efforts,
        },
    }

    return json.dumps(payload)


def serialize_error(code: str, message: str) -> str:
    """Serialize an error response to JSON.

    Args:
        code: Error code string (e.g., "VALIDATION_ERROR", "PARSE_ERROR").
        message: Human-readable error description.

    Returns:
        A JSON string conforming to the ErrorMessage schema.
    """
    payload = {
        "type": "error",
        "code": code,
        "message": message,
    }
    return json.dumps(payload)


def serialize_trajectory_status(status: str, message: str) -> str:
    """Serialize a trajectory status message to JSON.

    Args:
        status: One of "executing", "succeeded", "aborted", "preempted".
        message: Human-readable status description.

    Returns:
        A JSON string conforming to the TrajectoryStatusMessage schema.
    """
    payload = {
        "type": "trajectory_status",
        "status": status,
        "message": message,
    }
    return json.dumps(payload)


def serialize_sim_status(state: str) -> str:
    """Serialize a simulation status message to JSON.

    Args:
        state: One of "running", "paused", "disconnected".

    Returns:
        A JSON string conforming to the SimStatusMessage schema.
    """
    payload = {
        "type": "sim_status",
        "state": state,
    }
    return json.dumps(payload)


# ─── New Serialization Functions ─────────────────────────────────────────────


def serialize_camera_frame(
    timestamp: float,
    width: int,
    height: int,
    quality: int,
    data_base64: str,
) -> str:
    """Serialize a camera frame to JSON for sending to WebSocket clients.

    Args:
        timestamp: Frame timestamp in seconds (epoch).
        width: Image width in pixels.
        height: Image height in pixels.
        quality: JPEG compression quality (10-100).
        data_base64: Base64-encoded JPEG image data.

    Returns:
        A JSON string conforming to the CameraFrameMessage schema.
    """
    payload = {
        "type": "camera_frame",
        "timestamp": timestamp,
        "width": width,
        "height": height,
        "encoding": "jpeg",
        "quality": quality,
        "data": data_base64,
    }
    return json.dumps(payload)


def serialize_spawn_confirm(
    object_id: str,
    object_type: str,
    dimensions: List[float],
    position: List[float],
    orientation: List[float],
    color: List[float],
    mass: float,
) -> str:
    """Serialize a spawn confirmation message to JSON.

    Args:
        object_id: The unique identifier assigned to the spawned object.
        object_type: The type of object ("box", "sphere", "cylinder").
        dimensions: Dimension values matching the object type.
        position: [x, y, z] position in meters.
        orientation: [roll, pitch, yaw] in radians.
        color: [r, g, b, a] color values (0.0-1.0).
        mass: Object mass in kilograms.

    Returns:
        A JSON string conforming to the SpawnConfirmMessage schema.
    """
    payload = {
        "type": "spawn_confirm",
        "object_id": object_id,
        "object_type": object_type,
        "dimensions": dimensions,
        "position": position,
        "orientation": orientation,
        "color": color,
        "mass": mass,
    }
    return json.dumps(payload)


def serialize_delete_confirm(object_id: str) -> str:
    """Serialize a delete confirmation message to JSON.

    Args:
        object_id: The unique identifier of the deleted object.

    Returns:
        A JSON string conforming to the DeleteConfirmMessage schema.
    """
    payload = {
        "type": "delete_confirm",
        "object_id": object_id,
    }
    return json.dumps(payload)


def serialize_end_effector_pose(
    position: List[float],
    orientation: List[float],
) -> str:
    """Serialize end-effector pose to JSON.

    Args:
        position: [x, y, z] in meters.
        orientation: [roll, pitch, yaw] in radians.

    Returns:
        A JSON string conforming to the EndEffectorPoseMessage schema.
    """
    payload = {
        "type": "end_effector_pose",
        "position": position,
        "orientation": orientation,
    }
    return json.dumps(payload)


def serialize_episode_list(
    episodes: List[Dict[str, Any]],
) -> str:
    """Serialize episode list to JSON.

    Args:
        episodes: List of episode records, each with keys:
            id, name, timestamp, duration_seconds.

    Returns:
        A JSON string conforming to the EpisodeListMessage schema.
    """
    payload = {
        "type": "episode_list",
        "episodes": episodes,
    }
    return json.dumps(payload)


def serialize_recording_status(
    state: str,
    elapsed_seconds: Optional[float] = None,
    total_seconds: Optional[float] = None,
    episode_id: Optional[str] = None,
) -> str:
    """Serialize recording status to JSON.

    Args:
        state: One of "idle", "recording", "replaying".
        elapsed_seconds: Elapsed time in seconds (for recording/replaying).
        total_seconds: Total duration in seconds (for replay progress).
        episode_id: Episode identifier (for replaying state).

    Returns:
        A JSON string conforming to the RecordingStatusMessage schema.
    """
    payload: Dict[str, Any] = {
        "type": "recording_status",
        "state": state,
    }
    if elapsed_seconds is not None:
        payload["elapsed_seconds"] = elapsed_seconds
    if total_seconds is not None:
        payload["total_seconds"] = total_seconds
    if episode_id is not None:
        payload["episode_id"] = episode_id
    return json.dumps(payload)


def serialize_robot_list(
    robots: List[Dict[str, str]],
) -> str:
    """Serialize robot namespace list to JSON.

    Args:
        robots: List of robot entries, each with keys: robot_id, status.

    Returns:
        A JSON string conforming to the RobotListMessage schema.
    """
    payload = {
        "type": "robot_list",
        "robots": robots,
    }
    return json.dumps(payload)


def serialize_robot_status_change(robot_id: str, status: str) -> str:
    """Serialize a robot status change notification to JSON.

    Args:
        robot_id: The namespace identifier of the robot.
        status: One of "online" or "offline".

    Returns:
        A JSON string conforming to the RobotStatusChangeMessage schema.
    """
    payload = {
        "type": "robot_status_change",
        "robot_id": robot_id,
        "status": status,
    }
    return json.dumps(payload)


def serialize_namespaced_joint_state(robot_id: str, msg) -> str:
    """Serialize a ROS2 JointState message with a robot namespace tag.

    Args:
        robot_id: The namespace identifier of the robot (e.g., "/robot1").
        msg: A ROS2 sensor_msgs/msg/JointState message.

    Returns:
        A JSON string conforming to the NamespacedJointStateMessage schema.
    """
    stamp = msg.header.stamp
    timestamp = stamp.sec + stamp.nanosec * 1e-9

    names = list(msg.name)
    positions = list(msg.position)
    velocities = list(msg.velocity) if msg.velocity else [0.0] * len(names)
    efforts = list(msg.effort) if msg.effort else [0.0] * len(names)

    while len(velocities) < len(names):
        velocities.append(0.0)
    while len(efforts) < len(names):
        efforts.append(0.0)

    payload = {
        "type": "joint_state",
        "robot_id": robot_id,
        "timestamp": timestamp,
        "joints": {
            "names": names,
            "positions": positions,
            "velocities": velocities,
            "efforts": efforts,
        },
    }
    return json.dumps(payload)


# ─── Spawn Request Validation ────────────────────────────────────────────────


def validate_spawn_request(
    data: Dict[str, Any],
    bounds: Optional[SpawnBounds] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate a spawn object request against defined bounds.

    Checks that all numeric values fall within the constraints specified
    by SpawnBounds, and that the dimensions array length matches the
    object type.

    Args:
        data: Dictionary with keys: object_type, dimensions, position,
              orientation, color, mass.
        bounds: SpawnBounds instance to validate against. Defaults to
                SPAWN_BOUNDS module constant.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    if bounds is None:
        bounds = SPAWN_BOUNDS

    # Validate object_type.
    object_type = data.get("object_type")
    if object_type not in _VALID_OBJECT_TYPES:
        return (
            False,
            f"Invalid object_type '{object_type}'. "
            f"Valid types: {sorted(_VALID_OBJECT_TYPES)}",
        )

    # Validate dimensions array length matches object type.
    dimensions = data.get("dimensions", [])
    expected_len = _DIMENSION_LENGTHS[object_type]
    if len(dimensions) != expected_len:
        return (
            False,
            f"object_type '{object_type}' requires {expected_len} dimension(s), "
            f"got {len(dimensions)}",
        )

    # Validate each dimension value: must be in (0.0, 2.0].
    for i, dim in enumerate(dimensions):
        if not isinstance(dim, (int, float)):
            return (False, f"dimensions[{i}] must be a number")
        if dim <= bounds.min_dimension:
            return (
                False,
                f"dimensions[{i}] = {dim} must be greater than {bounds.min_dimension}",
            )
        if dim > bounds.max_dimension:
            return (
                False,
                f"dimensions[{i}] = {dim} exceeds maximum {bounds.max_dimension}",
            )

    # Validate position: [x, y, z] each in [-10.0, 10.0].
    position = data.get("position", [])
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return (False, "position must be an array of 3 numbers [x, y, z]")
    for i, coord in enumerate(position):
        if not isinstance(coord, (int, float)):
            return (False, f"position[{i}] must be a number")
        if coord < bounds.min_position or coord > bounds.max_position:
            return (
                False,
                f"position[{i}] = {coord} out of bounds "
                f"[{bounds.min_position}, {bounds.max_position}]",
            )

    # Validate orientation: [roll, pitch, yaw] each in [-π, π].
    orientation = data.get("orientation", [])
    if not isinstance(orientation, (list, tuple)) or len(orientation) != 3:
        return (False, "orientation must be an array of 3 numbers [roll, pitch, yaw]")
    for i, angle in enumerate(orientation):
        if not isinstance(angle, (int, float)):
            return (False, f"orientation[{i}] must be a number")
        if angle < bounds.min_orientation or angle > bounds.max_orientation:
            return (
                False,
                f"orientation[{i}] = {angle} out of bounds "
                f"[{bounds.min_orientation}, {bounds.max_orientation}]",
            )

    # Validate color: [r, g, b, a] each in [0.0, 1.0].
    color = data.get("color", [])
    if not isinstance(color, (list, tuple)) or len(color) != 4:
        return (False, "color must be an array of 4 numbers [r, g, b, a]")
    for i, c in enumerate(color):
        if not isinstance(c, (int, float)):
            return (False, f"color[{i}] must be a number")
        if c < bounds.min_color or c > bounds.max_color:
            return (
                False,
                f"color[{i}] = {c} out of bounds "
                f"[{bounds.min_color}, {bounds.max_color}]",
            )

    # Validate mass: must be in (0.0, 50.0].
    mass = data.get("mass")
    if not isinstance(mass, (int, float)):
        return (False, "mass must be a number")
    if mass <= bounds.min_mass:
        return (False, f"mass = {mass} must be greater than {bounds.min_mass}")
    if mass > bounds.max_mass:
        return (False, f"mass = {mass} exceeds maximum {bounds.max_mass}")

    return (True, None)


# ─── Workspace Bounds Validation ─────────────────────────────────────────────


def validate_workspace_position(
    position: List[float],
    bounds: Optional[WorkspaceBounds] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate a Cartesian goal position against workspace bounds.

    Checks that the target position [x, y, z] falls within the
    reachable workspace of the SO-100 arm.

    Args:
        position: [x, y, z] target position in meters.
        bounds: WorkspaceBounds instance to validate against. Defaults to
                WORKSPACE_BOUNDS module constant.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_message).
    """
    if bounds is None:
        bounds = WORKSPACE_BOUNDS

    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return (False, "position must be an array of 3 numbers [x, y, z]")

    x, y, z = position

    if not isinstance(x, (int, float)):
        return (False, "position x must be a number")
    if not isinstance(y, (int, float)):
        return (False, "position y must be a number")
    if not isinstance(z, (int, float)):
        return (False, "position z must be a number")

    if x < bounds.x_min or x > bounds.x_max:
        return (
            False,
            f"position x = {x} out of workspace bounds "
            f"[{bounds.x_min}, {bounds.x_max}]",
        )
    if y < bounds.y_min or y > bounds.y_max:
        return (
            False,
            f"position y = {y} out of workspace bounds "
            f"[{bounds.y_min}, {bounds.y_max}]",
        )
    if z < bounds.z_min or z > bounds.z_max:
        return (
            False,
            f"position z = {z} out of workspace bounds "
            f"[{bounds.z_min}, {bounds.z_max}]",
        )

    return (True, None)


# ─── Command Deserialization ─────────────────────────────────────────────────


def deserialize_command(json_str: str) -> Union[Dict[str, Any], Dict[str, str]]:
    """Deserialize and validate a JSON command from a WebSocket client.

    Parses the JSON string, validates it conforms to a recognized message
    schema (joint_command, gripper_command, or trajectory_goal), and
    validates field values including joint names and position limits.

    Args:
        json_str: Raw JSON string received from a WebSocket client.

    Returns:
        On success: A parsed command dictionary with the validated message
            content, including a "type" field.
        On validation failure: An error dictionary with the structure:
            {"type": "error", "code": "<ERROR_CODE>", "message": "<description>"}

    Error codes:
        - PARSE_ERROR: The input is not valid JSON.
        - VALIDATION_ERROR: The JSON is valid but does not conform to any
            recognized message schema (missing fields, wrong types, invalid
            joint names, position out of range, etc.).
    """
    # Step 1: Parse JSON.
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        return _error_response("PARSE_ERROR", f"Invalid JSON: {e}")

    # Step 2: Validate top-level structure.
    if not isinstance(data, dict):
        return _error_response(
            "VALIDATION_ERROR", "Message must be a JSON object"
        )

    # Step 3: Check message type field exists and is recognized.
    msg_type = data.get("type")
    if msg_type is None:
        return _error_response(
            "VALIDATION_ERROR", "Missing required field 'type'"
        )
    if msg_type not in _VALID_CLIENT_MESSAGE_TYPES:
        return _error_response(
            "VALIDATION_ERROR",
            f"Unknown message type '{msg_type}'. "
            f"Valid types: {sorted(_VALID_CLIENT_MESSAGE_TYPES)}",
        )

    # Step 4: Dispatch to type-specific validation.
    if msg_type == "joint_command":
        return _validate_joint_command(data)
    elif msg_type == "gripper_command":
        return _validate_gripper_command(data)
    elif msg_type == "trajectory_goal":
        return _validate_trajectory_goal(data)
    elif msg_type == "camera_stream_control":
        return _validate_camera_stream_control(data)
    elif msg_type == "spawn_object":
        return _validate_spawn_object(data)
    elif msg_type == "delete_object":
        return _validate_delete_object(data)
    elif msg_type == "cartesian_goal":
        return _validate_cartesian_goal(data)
    elif msg_type == "episode_control":
        return _validate_episode_control(data)
    elif msg_type == "teleop_velocity":
        return _validate_teleop_velocity(data)
    elif msg_type == "teleop_mode":
        return _validate_teleop_mode(data)
    elif msg_type == "select_robot":
        return _validate_select_robot(data)

    # Should not reach here due to the type check above.
    return _error_response("VALIDATION_ERROR", f"Unhandled message type '{msg_type}'")


def _validate_joint_command(data: Dict[str, Any]) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a joint_command message.

    Expected schema:
    {
        "type": "joint_command",
        "joints": [{"name": str, "position": number}, ...]
    }
    """
    joints = data.get("joints")
    if joints is None:
        return _error_response(
            "VALIDATION_ERROR", "joint_command: missing required field 'joints'"
        )
    if not isinstance(joints, list):
        return _error_response(
            "VALIDATION_ERROR", "joint_command: 'joints' must be an array"
        )
    if len(joints) == 0:
        return _error_response(
            "VALIDATION_ERROR", "joint_command: 'joints' array must not be empty"
        )

    validated_joints: List[Dict[str, Any]] = []
    for i, joint_entry in enumerate(joints):
        if not isinstance(joint_entry, dict):
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: joints[{i}] must be an object",
            )

        name = joint_entry.get("name")
        if name is None:
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: joints[{i}] missing required field 'name'",
            )
        if not isinstance(name, str):
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: joints[{i}].name must be a string",
            )
        if name not in ARM_JOINT_NAMES:
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: unrecognized joint name '{name}'. "
                f"Valid arm joints: {ARM_JOINT_NAMES}",
            )

        position = joint_entry.get("position")
        if position is None:
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: joints[{i}] missing required field 'position'",
            )
        if not isinstance(position, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                f"joint_command: joints[{i}].position must be a number",
            )

        # Validate position against joint limits.
        is_valid, error_msg = validate_joint_command(name, float(position))
        if not is_valid:
            return _error_response("VALIDATION_ERROR", error_msg)

        validated_joints.append({"name": name, "position": float(position)})

    return {"type": "joint_command", "joints": validated_joints}


def _validate_gripper_command(data: Dict[str, Any]) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a gripper_command message.

    Expected schema:
    {
        "type": "gripper_command",
        "position": number
    }
    """
    position = data.get("position")
    if position is None:
        return _error_response(
            "VALIDATION_ERROR",
            "gripper_command: missing required field 'position'",
        )
    if not isinstance(position, (int, float)):
        return _error_response(
            "VALIDATION_ERROR",
            "gripper_command: 'position' must be a number",
        )

    is_valid, error_msg = validate_gripper_command(float(position))
    if not is_valid:
        return _error_response("VALIDATION_ERROR", error_msg)

    return {"type": "gripper_command", "position": float(position)}


def _validate_trajectory_goal(data: Dict[str, Any]) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a trajectory_goal message.

    Expected schema:
    {
        "type": "trajectory_goal",
        "waypoints": [
            {
                "positions": {"joint_name": number, ...},
                "time_from_start": number
            },
            ...
        ]
    }
    """
    waypoints = data.get("waypoints")
    if waypoints is None:
        return _error_response(
            "VALIDATION_ERROR",
            "trajectory_goal: missing required field 'waypoints'",
        )
    if not isinstance(waypoints, list):
        return _error_response(
            "VALIDATION_ERROR",
            "trajectory_goal: 'waypoints' must be an array",
        )
    if len(waypoints) == 0:
        return _error_response(
            "VALIDATION_ERROR",
            "trajectory_goal: 'waypoints' array must not be empty",
        )

    validated_waypoints: List[Dict[str, Any]] = []
    for i, wp in enumerate(waypoints):
        if not isinstance(wp, dict):
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}] must be an object",
            )

        # Validate positions field.
        positions = wp.get("positions")
        if positions is None:
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}] missing required field 'positions'",
            )
        if not isinstance(positions, dict):
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}].positions must be an object",
            )

        # Validate each joint in the positions dict.
        validated_positions: Dict[str, float] = {}
        for joint_name, pos_value in positions.items():
            if joint_name not in ARM_JOINT_NAMES:
                return _error_response(
                    "VALIDATION_ERROR",
                    f"trajectory_goal: waypoints[{i}] unrecognized joint name "
                    f"'{joint_name}'. Valid arm joints: {ARM_JOINT_NAMES}",
                )
            if not isinstance(pos_value, (int, float)):
                return _error_response(
                    "VALIDATION_ERROR",
                    f"trajectory_goal: waypoints[{i}].positions['{joint_name}'] "
                    f"must be a number",
                )
            is_valid, error_msg = validate_joint_command(joint_name, float(pos_value))
            if not is_valid:
                return _error_response("VALIDATION_ERROR", error_msg)
            validated_positions[joint_name] = float(pos_value)

        # Validate time_from_start field.
        time_from_start = wp.get("time_from_start")
        if time_from_start is None:
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}] missing required field "
                f"'time_from_start'",
            )
        if not isinstance(time_from_start, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}].time_from_start must be a number",
            )
        if time_from_start <= 0:
            return _error_response(
                "VALIDATION_ERROR",
                f"trajectory_goal: waypoints[{i}].time_from_start must be positive",
            )

        validated_waypoints.append({
            "positions": validated_positions,
            "time_from_start": float(time_from_start),
        })

    return {"type": "trajectory_goal", "waypoints": validated_waypoints}


def _error_response(code: str, message: str) -> Dict[str, str]:
    """Build a structured error response dictionary.

    Args:
        code: Error code (e.g., "PARSE_ERROR", "VALIDATION_ERROR").
        message: Human-readable error description.

    Returns:
        A dictionary with "type", "code", and "message" keys.
    """
    return {"type": "error", "code": code, "message": message}


# ─── New Message Type Validators ─────────────────────────────────────────────


def _validate_camera_stream_control(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a camera_stream_control message.

    Expected schema:
    {
        "type": "camera_stream_control",
        "enabled": boolean
    }
    """
    enabled = data.get("enabled")
    if enabled is None:
        return _error_response(
            "VALIDATION_ERROR",
            "camera_stream_control: missing required field 'enabled'",
        )
    if not isinstance(enabled, bool):
        return _error_response(
            "VALIDATION_ERROR",
            "camera_stream_control: 'enabled' must be a boolean",
        )
    return {"type": "camera_stream_control", "enabled": enabled}


def _validate_spawn_object(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a spawn_object message.

    Expected schema:
    {
        "type": "spawn_object",
        "object_type": "box" | "sphere" | "cylinder",
        "dimensions": number[],
        "position": [number, number, number],
        "orientation": [number, number, number],
        "color": [number, number, number, number],
        "mass": number
    }
    """
    # Validate using the shared spawn request validation.
    is_valid, error_msg = validate_spawn_request(data)
    if not is_valid:
        return _error_response("VALIDATION_ERROR", f"spawn_object: {error_msg}")

    return {
        "type": "spawn_object",
        "object_type": data["object_type"],
        "dimensions": [float(d) for d in data["dimensions"]],
        "position": [float(p) for p in data["position"]],
        "orientation": [float(o) for o in data["orientation"]],
        "color": [float(c) for c in data["color"]],
        "mass": float(data["mass"]),
    }


def _validate_delete_object(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a delete_object message.

    Expected schema:
    {
        "type": "delete_object",
        "object_id": string
    }
    """
    object_id = data.get("object_id")
    if object_id is None:
        return _error_response(
            "VALIDATION_ERROR",
            "delete_object: missing required field 'object_id'",
        )
    if not isinstance(object_id, str):
        return _error_response(
            "VALIDATION_ERROR",
            "delete_object: 'object_id' must be a string",
        )
    if len(object_id) == 0:
        return _error_response(
            "VALIDATION_ERROR",
            "delete_object: 'object_id' must not be empty",
        )
    return {"type": "delete_object", "object_id": object_id}


def _validate_cartesian_goal(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a cartesian_goal message.

    Expected schema:
    {
        "type": "cartesian_goal",
        "position": [number, number, number],
        "orientation"?: [number, number, number],
        "time_from_start"?: number
    }
    """
    # Validate position (required).
    position = data.get("position")
    if position is None:
        return _error_response(
            "VALIDATION_ERROR",
            "cartesian_goal: missing required field 'position'",
        )
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        return _error_response(
            "VALIDATION_ERROR",
            "cartesian_goal: 'position' must be an array of 3 numbers [x, y, z]",
        )
    for i, coord in enumerate(position):
        if not isinstance(coord, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                f"cartesian_goal: position[{i}] must be a number",
            )

    # Validate against workspace bounds.
    pos_list = [float(p) for p in position]
    is_valid, error_msg = validate_workspace_position(pos_list)
    if not is_valid:
        return _error_response("VALIDATION_ERROR", f"cartesian_goal: {error_msg}")

    # Validate orientation (optional, defaults to [0.0, 0.0, 0.0]).
    orientation = data.get("orientation")
    if orientation is not None:
        if not isinstance(orientation, (list, tuple)) or len(orientation) != 3:
            return _error_response(
                "VALIDATION_ERROR",
                "cartesian_goal: 'orientation' must be an array of 3 numbers "
                "[roll, pitch, yaw]",
            )
        for i, angle in enumerate(orientation):
            if not isinstance(angle, (int, float)):
                return _error_response(
                    "VALIDATION_ERROR",
                    f"cartesian_goal: orientation[{i}] must be a number",
                )
            if float(angle) < -math.pi or float(angle) > math.pi:
                return _error_response(
                    "VALIDATION_ERROR",
                    f"cartesian_goal: orientation[{i}] = {angle} out of bounds "
                    f"[-π, π]",
                )
        orient_list = [float(o) for o in orientation]
    else:
        orient_list = [0.0, 0.0, 0.0]

    # Validate time_from_start (optional, defaults to 2.0).
    time_from_start = data.get("time_from_start")
    if time_from_start is not None:
        if not isinstance(time_from_start, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                "cartesian_goal: 'time_from_start' must be a number",
            )
        if float(time_from_start) < 0.5 or float(time_from_start) > 10.0:
            return _error_response(
                "VALIDATION_ERROR",
                f"cartesian_goal: 'time_from_start' = {time_from_start} "
                f"out of range [0.5, 10.0]",
            )
        tfs = float(time_from_start)
    else:
        tfs = 2.0

    return {
        "type": "cartesian_goal",
        "position": pos_list,
        "orientation": orient_list,
        "time_from_start": tfs,
    }


def _validate_episode_control(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate an episode_control message.

    Expected schema:
    {
        "type": "episode_control",
        "command": "start_recording" | "stop_recording" | "discard_recording"
                 | "list_episodes" | "replay_episode" | "stop_replay",
        "episode_id"?: string  (required for replay_episode)
    }
    """
    command = data.get("command")
    if command is None:
        return _error_response(
            "VALIDATION_ERROR",
            "episode_control: missing required field 'command'",
        )
    if not isinstance(command, str):
        return _error_response(
            "VALIDATION_ERROR",
            "episode_control: 'command' must be a string",
        )
    if command not in _VALID_EPISODE_COMMANDS:
        return _error_response(
            "VALIDATION_ERROR",
            f"episode_control: unknown command '{command}'. "
            f"Valid commands: {sorted(_VALID_EPISODE_COMMANDS)}",
        )

    # episode_id is required for replay_episode.
    episode_id = data.get("episode_id")
    if command == "replay_episode":
        if episode_id is None:
            return _error_response(
                "VALIDATION_ERROR",
                "episode_control: 'episode_id' is required for 'replay_episode' command",
            )
        if not isinstance(episode_id, str):
            return _error_response(
                "VALIDATION_ERROR",
                "episode_control: 'episode_id' must be a string",
            )

    result: Dict[str, Any] = {"type": "episode_control", "command": command}
    if episode_id is not None and isinstance(episode_id, str):
        result["episode_id"] = episode_id
    return result


def _validate_teleop_velocity(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a teleop_velocity message.

    Expected schema:
    {
        "type": "teleop_velocity",
        "linear": [number, number, number],
        "angular": [number, number, number],
        "gripper"?: number  (-1 to 1)
    }
    """
    # Validate linear velocity (required).
    linear = data.get("linear")
    if linear is None:
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_velocity: missing required field 'linear'",
        )
    if not isinstance(linear, (list, tuple)) or len(linear) != 3:
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_velocity: 'linear' must be an array of 3 numbers [vx, vy, vz]",
        )
    for i, v in enumerate(linear):
        if not isinstance(v, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                f"teleop_velocity: linear[{i}] must be a number",
            )

    # Validate angular velocity (required).
    angular = data.get("angular")
    if angular is None:
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_velocity: missing required field 'angular'",
        )
    if not isinstance(angular, (list, tuple)) or len(angular) != 3:
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_velocity: 'angular' must be an array of 3 numbers [wx, wy, wz]",
        )
    for i, w in enumerate(angular):
        if not isinstance(w, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                f"teleop_velocity: angular[{i}] must be a number",
            )

    # Validate gripper (optional, range -1 to 1).
    gripper = data.get("gripper")
    result: Dict[str, Any] = {
        "type": "teleop_velocity",
        "linear": [float(v) for v in linear],
        "angular": [float(w) for w in angular],
    }
    if gripper is not None:
        if not isinstance(gripper, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                "teleop_velocity: 'gripper' must be a number",
            )
        if float(gripper) < -1.0 or float(gripper) > 1.0:
            return _error_response(
                "VALIDATION_ERROR",
                f"teleop_velocity: 'gripper' = {gripper} out of range [-1, 1]",
            )
        result["gripper"] = float(gripper)

    return result


def _validate_teleop_mode(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a teleop_mode message.

    Expected schema:
    {
        "type": "teleop_mode",
        "enabled": boolean,
        "velocity_scale"?: number (0.01 to 0.2)
    }
    """
    enabled = data.get("enabled")
    if enabled is None:
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_mode: missing required field 'enabled'",
        )
    if not isinstance(enabled, bool):
        return _error_response(
            "VALIDATION_ERROR",
            "teleop_mode: 'enabled' must be a boolean",
        )

    result: Dict[str, Any] = {"type": "teleop_mode", "enabled": enabled}

    velocity_scale = data.get("velocity_scale")
    if velocity_scale is not None:
        if not isinstance(velocity_scale, (int, float)):
            return _error_response(
                "VALIDATION_ERROR",
                "teleop_mode: 'velocity_scale' must be a number",
            )
        if float(velocity_scale) < 0.01 or float(velocity_scale) > 0.2:
            return _error_response(
                "VALIDATION_ERROR",
                f"teleop_mode: 'velocity_scale' = {velocity_scale} "
                f"out of range [0.01, 0.2]",
            )
        result["velocity_scale"] = float(velocity_scale)

    return result


def _validate_select_robot(
    data: Dict[str, Any],
) -> Union[Dict[str, Any], Dict[str, str]]:
    """Validate a select_robot message.

    Expected schema:
    {
        "type": "select_robot",
        "robot_id": string
    }
    """
    robot_id = data.get("robot_id")
    if robot_id is None:
        return _error_response(
            "VALIDATION_ERROR",
            "select_robot: missing required field 'robot_id'",
        )
    if not isinstance(robot_id, str):
        return _error_response(
            "VALIDATION_ERROR",
            "select_robot: 'robot_id' must be a string",
        )
    if len(robot_id) == 0:
        return _error_response(
            "VALIDATION_ERROR",
            "select_robot: 'robot_id' must not be empty",
        )
    return {"type": "select_robot", "robot_id": robot_id}
