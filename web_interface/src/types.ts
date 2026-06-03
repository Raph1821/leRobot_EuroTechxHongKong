/**
 * Shared type definitions for the SO-100 Web Control Interface.
 * Based on the WebSocket message protocol defined in the design document.
 */

/** Joint state received from server */
export interface JointStateMessage {
  type: 'joint_state';
  timestamp: number;
  joints: {
    names: string[];
    positions: number[];
    velocities: number[];
    efforts: number[];
  };
}

/** Joint command sent to server */
export interface JointCommandMessage {
  type: 'joint_command';
  joints: Array<{ name: string; position: number }>;
}

/** Gripper command sent to server */
export interface GripperCommandMessage {
  type: 'gripper_command';
  position: number;
}

/** Trajectory goal sent to server */
export interface TrajectoryGoalMessage {
  type: 'trajectory_goal';
  waypoints: Array<{
    positions: Record<string, number>;
    time_from_start: number;
  }>;
}

/** Error response from server */
export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

/** Trajectory execution status from server */
export interface TrajectoryStatusMessage {
  type: 'trajectory_status';
  status: 'executing' | 'succeeded' | 'aborted' | 'preempted';
  message: string;
}

/** Simulation status from server */
export interface SimStatusMessage {
  type: 'sim_status';
  state: 'running' | 'paused' | 'disconnected';
}

// ─── Camera Streaming ───────────────────────────────────────────────────────

/** Server → Client: Camera frame */
export interface CameraFrameMessage {
  type: 'camera_frame';
  timestamp: number;
  width: number;
  height: number;
  encoding: 'jpeg';
  quality: number; // 10-100
  data: string; // base64-encoded JPEG
}

/** Client → Server: Camera stream control */
export interface CameraStreamControlMessage {
  type: 'camera_stream_control';
  enabled: boolean;
}

// ─── Object Spawning ────────────────────────────────────────────────────────

/** Client → Server: Spawn object request */
export interface SpawnObjectMessage {
  type: 'spawn_object';
  object_type: 'box' | 'sphere' | 'cylinder';
  dimensions: number[]; // [l,w,h] | [r] | [r,h]
  position: [number, number, number];
  orientation: [number, number, number];
  color: [number, number, number, number];
  mass: number;
}

/** Server → Client: Spawn confirmation */
export interface SpawnConfirmMessage {
  type: 'spawn_confirm';
  object_id: string;
  object_type: 'box' | 'sphere' | 'cylinder';
  dimensions: number[];
  position: [number, number, number];
  orientation: [number, number, number];
  color: [number, number, number, number];
  mass: number;
}

/** Client → Server: Delete object request */
export interface DeleteObjectMessage {
  type: 'delete_object';
  object_id: string;
}

/** Server → Client: Delete confirmation */
export interface DeleteConfirmMessage {
  type: 'delete_confirm';
  object_id: string;
}

// ─── Cartesian Control ──────────────────────────────────────────────────────

/** Client → Server: Cartesian goal */
export interface CartesianGoalMessage {
  type: 'cartesian_goal';
  position: [number, number, number]; // [x, y, z] meters
  orientation?: [number, number, number]; // [roll, pitch, yaw] radians (optional)
  time_from_start?: number; // seconds (default 2.0)
}

/** Server → Client: End-effector pose update */
export interface EndEffectorPoseMessage {
  type: 'end_effector_pose';
  position: [number, number, number]; // [x, y, z] meters
  orientation: [number, number, number]; // [roll, pitch, yaw] radians
}

// ─── Episode Recording ──────────────────────────────────────────────────────

/** Client → Server: Episode control command */
export interface EpisodeControlMessage {
  type: 'episode_control';
  command:
    | 'start_recording'
    | 'stop_recording'
    | 'discard_recording'
    | 'list_episodes'
    | 'replay_episode'
    | 'stop_replay';
  episode_id?: string; // required for replay_episode
}

/** Server → Client: Episode list */
export interface EpisodeListMessage {
  type: 'episode_list';
  episodes: EpisodeRecord[];
}

/** Server → Client: Recording status */
export interface RecordingStatusMessage {
  type: 'recording_status';
  state: 'idle' | 'recording' | 'replaying';
  elapsed_seconds?: number;
  total_seconds?: number; // for replay progress
  episode_id?: string;
}

/** A single episode record */
export interface EpisodeRecord {
  id: string; // directory name, e.g., "episode_000042"
  name: string; // display name
  timestamp: number; // creation time (epoch ms)
  duration_seconds: number;
}

// ─── Teleoperation ──────────────────────────────────────────────────────────

/** Client → Server: Teleoperation velocity command */
export interface TeleopVelocityMessage {
  type: 'teleop_velocity';
  linear: [number, number, number]; // [vx, vy, vz] m/s
  angular: [number, number, number]; // [wx, wy, wz] rad/s
  gripper?: number; // gripper velocity (-1 to 1)
}

/** Client → Server: Teleoperation mode control */
export interface TeleopModeMessage {
  type: 'teleop_mode';
  enabled: boolean;
  velocity_scale?: number; // 0.01 to 0.2
}

// ─── Multi-Robot ────────────────────────────────────────────────────────────

/** Client → Server: Select active robot */
export interface SelectRobotMessage {
  type: 'select_robot';
  robot_id: string; // namespace string, e.g., "/robot1"
}

/** Server → Client: Robot namespace list */
export interface RobotListMessage {
  type: 'robot_list';
  robots: Array<{
    robot_id: string;
    status: 'online' | 'offline';
  }>;
}

/** Server → Client: Namespaced joint state */
export interface NamespacedJointStateMessage {
  type: 'joint_state';
  robot_id: string; // namespace identifier
  timestamp: number;
  joints: {
    names: string[];
    positions: number[];
    velocities: number[];
    efforts: number[];
  };
}

/** Server → Client: Robot status change */
export interface RobotStatusChangeMessage {
  type: 'robot_status_change';
  robot_id: string;
  status: 'online' | 'offline';
}

// ─── Workspace Bounds ───────────────────────────────────────────────────────

/** Reachable workspace of the SO-100 arm in base_link frame */
export const WORKSPACE_BOUNDS = {
  x_min: -0.3,
  x_max: 0.3,
  y_min: -0.3,
  y_max: 0.3,
  z_min: 0.0,
  z_max: 0.5,
} as const;

// ─── Union Types ────────────────────────────────────────────────────────────

/** Union of all server-to-client message types */
export type ServerMessage =
  | JointStateMessage
  | ErrorMessage
  | TrajectoryStatusMessage
  | SimStatusMessage
  | CameraFrameMessage
  | SpawnConfirmMessage
  | DeleteConfirmMessage
  | EndEffectorPoseMessage
  | EpisodeListMessage
  | RecordingStatusMessage
  | RobotListMessage
  | NamespacedJointStateMessage
  | RobotStatusChangeMessage;

/** Union of all client-to-server message types */
export type ClientMessage =
  | JointCommandMessage
  | GripperCommandMessage
  | TrajectoryGoalMessage
  | CameraStreamControlMessage
  | SpawnObjectMessage
  | DeleteObjectMessage
  | CartesianGoalMessage
  | EpisodeControlMessage
  | TeleopVelocityMessage
  | TeleopModeMessage
  | SelectRobotMessage;

/** Saved pose stored in browser session */
export interface SavedPose {
  name: string; // 1-64 characters
  positions: Record<string, number>; // joint name → angle in radians
  savedAt: number; // timestamp
}

/** Configuration for pose sequence playback */
export interface PoseSequenceConfig {
  intervalSeconds: number; // 0.5 to 30.0, default 2.0
}

/** Connection state machine states */
export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

/** Joint configuration matching the URDF */
export interface JointConfig {
  name: string;
  lowerLimit: number;
  upperLimit: number;
  axis: [number, number, number];
  originXyz: [number, number, number];
  originRpy: [number, number, number];
}

/** All joint configurations for the SO-100 5-DOF arm */
export const JOINT_CONFIGS: JointConfig[] = [
  {
    name: 'Shoulder_Rotation',
    lowerLimit: -1.96,
    upperLimit: 1.96,
    axis: [0, -1, 0],
    originXyz: [0, -0.0452, 0.0165],
    originRpy: [1.5708, 0, 0],
  },
  {
    name: 'Shoulder_Pitch',
    lowerLimit: -1.745,
    upperLimit: 1.745,
    axis: [1, 0, 0],
    originXyz: [0, 0.1025, 0.0306],
    originRpy: [0, 0, 0],
  },
  {
    name: 'Elbow',
    lowerLimit: -1.5,
    upperLimit: 1.5,
    axis: [1, 0, 0],
    originXyz: [0, 0.11257, 0.028],
    originRpy: [0, 0, 0],
  },
  {
    name: 'Wrist_Pitch',
    lowerLimit: -1.658,
    upperLimit: 1.658,
    axis: [1, 0, 0],
    originXyz: [0, 0.0052, 0.1349],
    originRpy: [-1.57079, 0, 0],
  },
  {
    name: 'Wrist_Roll',
    lowerLimit: -2.75,
    upperLimit: 2.75,
    axis: [0, 1, 0],
    originXyz: [0, -0.0601, 0],
    originRpy: [0, 1.57079, 0],
  },
  {
    name: 'Gripper',
    lowerLimit: -0.1792,
    upperLimit: 1.5708,
    axis: [0, 0, 1],
    originXyz: [-0.0202, -0.0244, 0],
    originRpy: [3.1416, 0, 3.1416],
  },
];

/** Joint names for the 5 arm joints (excluding gripper) */
export const ARM_JOINT_NAMES = [
  'Shoulder_Rotation',
  'Shoulder_Pitch',
  'Elbow',
  'Wrist_Pitch',
  'Wrist_Roll',
] as const;

/** All joint names including gripper */
export const ALL_JOINT_NAMES = [
  'Shoulder_Rotation',
  'Shoulder_Pitch',
  'Elbow',
  'Wrist_Pitch',
  'Wrist_Roll',
  'Gripper',
] as const;

/** STL mesh file names corresponding to robot links */
export const MESH_FILES = [
  'Base.STL',
  'Shoulder_Rotation_Pitch.STL',
  'Lower_Arm.STL',
  'Upper_Arm.STL',
  'Wrist_Pitch_Roll.STL',
  'Fixed_Gripper.STL',
  'Moving_Jaw.STL',
] as const;
