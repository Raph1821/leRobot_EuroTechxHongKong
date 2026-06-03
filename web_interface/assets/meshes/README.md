# SO-100 Robot Arm STL Meshes

This directory contains STL mesh files for the SO-100 5-DOF robot arm,
copied from the `so_arm_100_description` package for serving via the web interface.

## Files

- `Base.STL` — Base link
- `Shoulder_Rotation_Pitch.STL` — Shoulder rotation/pitch link
- `Lower_Arm.STL` — Lower arm link
- `Upper_Arm.STL` — Upper arm link
- `Wrist_Pitch_Roll.STL` — Wrist pitch/roll link
- `Fixed_Gripper.STL` — Fixed gripper jaw
- `Moving_Jaw.STL` — Moving gripper jaw

## Source

These files are sourced from:
`so_arm_100_description/models/so_arm_100_5dof/meshes/`

To update, run from the workspace root:
```bash
cp so_arm_100_description/models/so_arm_100_5dof/meshes/*.STL web_interface/assets/meshes/
```
