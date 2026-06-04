// SO-101 revolute joints, base → tip. Limits in radians, straight from
// so101_new_calib.urdf (new calibration: zero = middle of range).
export type JointDef = {
  name: string; // must match the URDF <joint name=...>
  label: string;
  lower: number;
  upper: number;
};

export const JOINTS: JointDef[] = [
  { name: "shoulder_pan", label: "Shoulder Pan", lower: -1.91986, upper: 1.91986 },
  { name: "shoulder_lift", label: "Shoulder Lift", lower: -1.74533, upper: 1.74533 },
  { name: "elbow_flex", label: "Elbow Flex", lower: -1.69, upper: 1.69 },
  { name: "wrist_flex", label: "Wrist Flex", lower: -1.65806, upper: 1.65806 },
  { name: "wrist_roll", label: "Wrist Roll", lower: -2.74385, upper: 2.84121 },
  { name: "gripper", label: "Gripper", lower: -0.174533, upper: 1.74533 },
];

export type JointValues = Record<string, number>;

export const HOME_POSE: JointValues = Object.fromEntries(
  JOINTS.map((j) => [j.name, 0]),
);

export const URDF_URL = "/so101/so101.urdf";

export const radToDeg = (r: number) => (r * 180) / Math.PI;
