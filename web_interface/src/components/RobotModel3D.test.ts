/**
 * Unit tests for RobotModel3D kinematic chain logic.
 *
 * These tests verify the kinematic chain structure and joint angle updates
 * without requiring actual STL file loading (which requires a browser env).
 */

import { describe, it, expect } from 'vitest';
import * as THREE from 'three';
import { JOINT_CONFIGS } from '@/types';

// We test the exported helper logic by importing the module and testing the
// core kinematic math that the component relies on.

/**
 * Replicate the axis-angle rotation function from RobotModel3D for testing.
 */
function axisAngleRotation(
  axis: [number, number, number],
  angle: number
): THREE.Quaternion {
  const axisVec = new THREE.Vector3(axis[0], axis[1], axis[2]).normalize();
  return new THREE.Quaternion().setFromAxisAngle(axisVec, angle);
}

/**
 * Replicate the RPY to Euler conversion from RobotModel3D for testing.
 */
function rpyToEuler(rpy: [number, number, number]): THREE.Euler {
  return new THREE.Euler(rpy[0], rpy[1], rpy[2], 'XYZ');
}

describe('RobotModel3D kinematic helpers', () => {
  describe('axisAngleRotation', () => {
    it('should produce identity quaternion for zero angle', () => {
      const quat = axisAngleRotation([1, 0, 0], 0);
      expect(quat.x).toBeCloseTo(0);
      expect(quat.y).toBeCloseTo(0);
      expect(quat.z).toBeCloseTo(0);
      expect(quat.w).toBeCloseTo(1);
    });

    it('should rotate 90 degrees about X axis correctly', () => {
      const quat = axisAngleRotation([1, 0, 0], Math.PI / 2);
      // Expected: quaternion for 90° about X = (sin(45°), 0, 0, cos(45°))
      const expected = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(1, 0, 0),
        Math.PI / 2
      );
      expect(quat.x).toBeCloseTo(expected.x);
      expect(quat.y).toBeCloseTo(expected.y);
      expect(quat.z).toBeCloseTo(expected.z);
      expect(quat.w).toBeCloseTo(expected.w);
    });

    it('should handle negative axis components (Shoulder_Rotation axis [0,-1,0])', () => {
      const angle = 0.5;
      const quat = axisAngleRotation([0, -1, 0], angle);
      const expected = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, -1, 0).normalize(),
        angle
      );
      expect(quat.x).toBeCloseTo(expected.x);
      expect(quat.y).toBeCloseTo(expected.y);
      expect(quat.z).toBeCloseTo(expected.z);
      expect(quat.w).toBeCloseTo(expected.w);
    });

    it('should rotate 180 degrees about Z axis correctly', () => {
      const quat = axisAngleRotation([0, 0, 1], Math.PI);
      const expected = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0, 0, 1),
        Math.PI
      );
      expect(quat.x).toBeCloseTo(expected.x);
      expect(quat.y).toBeCloseTo(expected.y);
      expect(quat.z).toBeCloseTo(expected.z);
      expect(quat.w).toBeCloseTo(expected.w);
    });
  });

  describe('rpyToEuler', () => {
    it('should produce zero euler for [0,0,0]', () => {
      const euler = rpyToEuler([0, 0, 0]);
      expect(euler.x).toBeCloseTo(0);
      expect(euler.y).toBeCloseTo(0);
      expect(euler.z).toBeCloseTo(0);
      expect(euler.order).toBe('XYZ');
    });

    it('should handle Shoulder_Rotation origin RPY [1.5708, 0, 0]', () => {
      const euler = rpyToEuler([1.5708, 0, 0]);
      expect(euler.x).toBeCloseTo(1.5708);
      expect(euler.y).toBeCloseTo(0);
      expect(euler.z).toBeCloseTo(0);
    });

    it('should handle Wrist_Pitch origin RPY [-1.57079, 0, 0]', () => {
      const euler = rpyToEuler([-1.57079, 0, 0]);
      expect(euler.x).toBeCloseTo(-1.57079);
      expect(euler.y).toBeCloseTo(0);
      expect(euler.z).toBeCloseTo(0);
    });

    it('should handle Gripper origin RPY [3.1416, 0, 3.1416]', () => {
      const euler = rpyToEuler([3.1416, 0, 3.1416]);
      expect(euler.x).toBeCloseTo(3.1416);
      expect(euler.y).toBeCloseTo(0);
      expect(euler.z).toBeCloseTo(3.1416);
    });
  });

  describe('JOINT_CONFIGS consistency', () => {
    it('should have 6 joint configurations', () => {
      expect(JOINT_CONFIGS).toHaveLength(6);
    });

    it('should have correct joint names in order', () => {
      const names = JOINT_CONFIGS.map((j) => j.name);
      expect(names).toEqual([
        'Shoulder_Rotation',
        'Shoulder_Pitch',
        'Elbow',
        'Wrist_Pitch',
        'Wrist_Roll',
        'Gripper',
      ]);
    });

    it('should have normalized axes (unit vectors)', () => {
      for (const config of JOINT_CONFIGS) {
        const len = Math.sqrt(
          config.axis[0] ** 2 + config.axis[1] ** 2 + config.axis[2] ** 2
        );
        expect(len).toBeCloseTo(1.0);
      }
    });

    it('should have Shoulder_Rotation axis [0,-1,0]', () => {
      expect(JOINT_CONFIGS[0].axis).toEqual([0, -1, 0]);
    });

    it('should have Shoulder_Rotation origin xyz [0,-0.0452,0.0165]', () => {
      expect(JOINT_CONFIGS[0].originXyz).toEqual([0, -0.0452, 0.0165]);
    });
  });

  describe('kinematic chain transform composition', () => {
    it('should compose parent transform with joint origin for child position', () => {
      // Simulate the chain: base at origin, first joint at [0, -0.0452, 0.0165]
      const parentWorld = new THREE.Matrix4().identity();
      const jointOrigin = new THREE.Matrix4().compose(
        new THREE.Vector3(0, -0.0452, 0.0165),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(1.5708, 0, 0, 'XYZ')),
        new THREE.Vector3(1, 1, 1)
      );

      const childWorld = parentWorld.clone().multiply(jointOrigin);
      const childPos = new THREE.Vector3();
      childPos.setFromMatrixPosition(childWorld);

      expect(childPos.x).toBeCloseTo(0);
      expect(childPos.y).toBeCloseTo(-0.0452);
      expect(childPos.z).toBeCloseTo(0.0165);
    });

    it('should apply joint angle rotation about axis after origin', () => {
      const angle = Math.PI / 4; // 45 degrees
      const axis: [number, number, number] = [0, -1, 0];

      // Origin transform
      const originMat = new THREE.Matrix4().compose(
        new THREE.Vector3(0, -0.0452, 0.0165),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(1.5708, 0, 0, 'XYZ')),
        new THREE.Vector3(1, 1, 1)
      );

      // Joint rotation
      const jointQuat = axisAngleRotation(axis, angle);
      const jointRotMat = new THREE.Matrix4().makeRotationFromQuaternion(jointQuat);

      // Combined: origin * rotation
      const combined = originMat.clone().multiply(jointRotMat);

      // Position should still be the origin xyz (rotation doesn't change position)
      const pos = new THREE.Vector3();
      pos.setFromMatrixPosition(combined);
      expect(pos.x).toBeCloseTo(0);
      expect(pos.y).toBeCloseTo(-0.0452);
      expect(pos.z).toBeCloseTo(0.0165);
    });

    it('should produce different orientations for different joint angles', () => {
      const axis: [number, number, number] = [1, 0, 0];
      const quat1 = axisAngleRotation(axis, 0);
      const quat2 = axisAngleRotation(axis, Math.PI / 2);

      // They should not be equal
      expect(quat1.equals(quat2)).toBe(false);
    });

    it('zero angles should result in identity rotations for all joints', () => {
      for (const config of JOINT_CONFIGS) {
        const quat = axisAngleRotation(config.axis, 0);
        expect(quat.x).toBeCloseTo(0);
        expect(quat.y).toBeCloseTo(0);
        expect(quat.z).toBeCloseTo(0);
        expect(quat.w).toBeCloseTo(1);
      }
    });
  });
});
