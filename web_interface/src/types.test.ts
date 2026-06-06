import { describe, it, expect } from 'vitest';
import { JOINT_CONFIGS, ALL_JOINT_NAMES, MESH_FILES } from './types';

describe('types', () => {
  it('should define 6 joint configurations', () => {
    expect(JOINT_CONFIGS).toHaveLength(6);
  });

  it('should define all expected joint names', () => {
    expect(ALL_JOINT_NAMES).toEqual([
      'Shoulder_Rotation',
      'Shoulder_Pitch',
      'Elbow',
      'Wrist_Pitch',
      'Wrist_Roll',
      'Gripper',
    ]);
  });

  it('should define 7 mesh files', () => {
    expect(MESH_FILES).toHaveLength(7);
    expect(MESH_FILES).toContain('Base.STL');
    expect(MESH_FILES).toContain('Moving_Jaw.STL');
  });

  it('should have valid joint limit ranges (lower < upper)', () => {
    for (const joint of JOINT_CONFIGS) {
      expect(joint.lowerLimit).toBeLessThan(joint.upperLimit);
    }
  });
});
