// SO-101 revolute joints, base → tip.
// `name`   = URDF joint name (drives the local 3D model)
// `bridge` = joint name expected by the ROS2 web_bridge (ws://…:9090)
// Limits (radians) aligned with the bridge's validator so commands aren't rejected.
export type JointDef = {
  name: string;
  bridge: string;
  label: string;
  lower: number;
  upper: number;
};

export const JOINTS: JointDef[] = [
  { name: "shoulder_pan", bridge: "Shoulder_Rotation", label: "Shoulder Pan", lower: -1.96, upper: 1.96 },
  { name: "shoulder_lift", bridge: "Shoulder_Pitch", label: "Shoulder Lift", lower: -1.745, upper: 1.745 },
  { name: "elbow_flex", bridge: "Elbow", label: "Elbow Flex", lower: -1.5, upper: 1.5 },
  { name: "wrist_flex", bridge: "Wrist_Pitch", label: "Wrist Flex", lower: -1.658, upper: 1.658 },
  { name: "wrist_roll", bridge: "Wrist_Roll", label: "Wrist Roll", lower: -2.75, upper: 2.75 },
  { name: "gripper", bridge: "Gripper", label: "Gripper", lower: -0.1792, upper: 1.5708 },
];

export type JointValues = Record<string, number>;

export const HOME_POSE: JointValues = Object.fromEntries(
  JOINTS.map((j) => [j.name, 0]),
);

// name ↔ bridge lookup maps
export const URDF_TO_BRIDGE: Record<string, string> = Object.fromEntries(
  JOINTS.map((j) => [j.name, j.bridge]),
);
export const BRIDGE_TO_URDF: Record<string, string> = Object.fromEntries(
  JOINTS.map((j) => [j.bridge, j.name]),
);

export const URDF_URL = "/so101/so101.urdf";

export const radToDeg = (r: number) => (r * 180) / Math.PI;
