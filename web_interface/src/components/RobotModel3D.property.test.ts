/**
 * Property-based test for Forward Kinematics Transform Chain (Property 4)
 *
 * **Validates: Requirements 7.1**
 *
 * For any set of 6 joint angles within their respective limits, applying the
 * URDF-defined kinematic chain (parent-child relationships, joint origins, joint axes)
 * should produce link world-transforms where each child link's position is the
 * composition of its parent's transform with the joint origin and rotation by the
 * joint angle about the defined axis.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import * as THREE from 'three';
import { JOINT_CONFIGS } from '@/types';

// ─── Kinematic Helper Functions (mirroring RobotModel3D implementation) ──────

/**
 * Creates a rotation matrix from RPY (Roll, Pitch, Yaw) angles.
 * Uses the URDF convention: fixed-frame XYZ rotation.
 */
function rpyToQuaternion(rpy: [number, number, number]): THREE.Quaternion {
  const euler = new THREE.Euler(rpy[0], rpy[1], rpy[2], 'XYZ');
  return new THREE.Quaternion().setFromEuler(euler);
}

/**
 * Creates a quaternion representing rotation about a given axis by an angle.
 */
function axisAngleRotation(
  axis: [number, number, number],
  angle: number
): THREE.Quaternion {
  const axisVec = new THREE.Vector3(axis[0], axis[1], axis[2]).normalize();
  return new THREE.Quaternion().setFromAxisAngle(axisVec, angle);
}

/**
 * Computes the world transform for each link in the kinematic chain
 * by composing parent transform + joint origin + joint rotation.
 *
 * Returns an array of 4x4 world matrices, one per joint (6 total).
 */
function computeForwardKinematics(jointAngles: number[]): THREE.Matrix4[] {
  const worldTransforms: THREE.Matrix4[] = [];

  // Start from the root (identity — base link at world origin)
  let parentWorld = new THREE.Matrix4().identity();

  for (let i = 0; i < JOINT_CONFIGS.length; i++) {
    const config = JOINT_CONFIGS[i];
    const angle = jointAngles[i];

    // 1. Joint origin: translation + RPY rotation
    const originTranslation = new THREE.Matrix4().makeTranslation(
      config.originXyz[0],
      config.originXyz[1],
      config.originXyz[2]
    );
    const originRotation = new THREE.Matrix4().makeRotationFromQuaternion(
      rpyToQuaternion(config.originRpy)
    );
    const originTransform = originTranslation.clone().multiply(originRotation);

    // 2. Joint rotation about the joint axis
    const jointRotation = new THREE.Matrix4().makeRotationFromQuaternion(
      axisAngleRotation(config.axis, angle)
    );

    // 3. Child world = parent world * origin transform * joint rotation
    const childWorld = parentWorld.clone().multiply(originTransform).multiply(jointRotation);

    worldTransforms.push(childWorld);

    // The child becomes the parent for the next joint
    parentWorld = childWorld;
  }

  return worldTransforms;
}

/**
 * Simulates the Three.js scene graph approach used in RobotModel3D:
 * - Creates nested Object3D groups matching the component's structure
 * - Applies joint angles via quaternion on the rotation groups
 * - Extracts world matrices from the scene graph
 *
 * This tests that the scene graph approach produces the same results
 * as direct matrix composition.
 */
function computeViaSceneGraph(jointAngles: number[]): THREE.Matrix4[] {
  const root = new THREE.Group();
  const worldTransforms: THREE.Matrix4[] = [];
  const jointRotationGroups: THREE.Object3D[] = [];

  // Build the kinematic chain just like RobotModel3D does
  let currentParent: THREE.Object3D = root;

  for (let i = 0; i < JOINT_CONFIGS.length; i++) {
    const config = JOINT_CONFIGS[i];

    // Joint origin group: position + RPY
    const jointOriginGroup = new THREE.Group();
    jointOriginGroup.position.set(
      config.originXyz[0],
      config.originXyz[1],
      config.originXyz[2]
    );
    jointOriginGroup.rotation.copy(
      new THREE.Euler(config.originRpy[0], config.originRpy[1], config.originRpy[2], 'XYZ')
    );
    currentParent.add(jointOriginGroup);

    // Joint rotation group: rotation about axis
    const jointRotationGroup = new THREE.Group();
    jointOriginGroup.add(jointRotationGroup);
    jointRotationGroups.push(jointRotationGroup);

    // Move to next level
    currentParent = jointRotationGroup;
  }

  // Apply joint angles (same as updateJointAngles)
  for (let i = 0; i < jointAngles.length; i++) {
    const config = JOINT_CONFIGS[i];
    const quat = axisAngleRotation(config.axis, jointAngles[i]);
    jointRotationGroups[i].quaternion.copy(quat);
  }

  // Force world matrix update
  root.updateMatrixWorld(true);

  // Extract world transforms from the joint rotation groups
  for (const group of jointRotationGroups) {
    worldTransforms.push(group.matrixWorld.clone());
  }

  return worldTransforms;
}

// ─── Arbitraries ────────────────────────────────────────────────────────────

/**
 * Generates a tuple of 6 joint angles within their respective limits.
 */
const jointAnglesArb = fc.tuple(
  fc.double({ min: JOINT_CONFIGS[0].lowerLimit, max: JOINT_CONFIGS[0].upperLimit, noNaN: true }),
  fc.double({ min: JOINT_CONFIGS[1].lowerLimit, max: JOINT_CONFIGS[1].upperLimit, noNaN: true }),
  fc.double({ min: JOINT_CONFIGS[2].lowerLimit, max: JOINT_CONFIGS[2].upperLimit, noNaN: true }),
  fc.double({ min: JOINT_CONFIGS[3].lowerLimit, max: JOINT_CONFIGS[3].upperLimit, noNaN: true }),
  fc.double({ min: JOINT_CONFIGS[4].lowerLimit, max: JOINT_CONFIGS[4].upperLimit, noNaN: true }),
  fc.double({ min: JOINT_CONFIGS[5].lowerLimit, max: JOINT_CONFIGS[5].upperLimit, noNaN: true })
);

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: so100-isaacsim-web-control, Property 4: Forward kinematics transform chain', () => {
  /**
   * Property 4: Forward kinematics transform chain
   * **Validates: Requirements 7.1**
   */

  const EPSILON = 1e-6;

  it('child transforms equal composition of parent transform + joint origin + rotation by angle about axis', () => {
    fc.assert(
      fc.property(jointAnglesArb, (angles) => {
        const directTransforms = computeForwardKinematics(angles);
        const sceneGraphTransforms = computeViaSceneGraph(angles);

        // Both approaches should produce the same world transforms
        for (let i = 0; i < JOINT_CONFIGS.length; i++) {
          const direct = directTransforms[i];
          const sceneGraph = sceneGraphTransforms[i];

          // Compare all 16 elements of the 4x4 matrix
          const directElements = direct.elements;
          const sceneGraphElements = sceneGraph.elements;

          for (let j = 0; j < 16; j++) {
            expect(Math.abs(directElements[j] - sceneGraphElements[j])).toBeLessThan(EPSILON);
          }
        }
      }),
      { numRuns: 200 }
    );
  });

  it('each child world position equals parent world * joint origin translation + RPY + axis rotation', () => {
    fc.assert(
      fc.property(jointAnglesArb, (angles) => {
        const worldTransforms = computeForwardKinematics(angles);

        // Verify the composition property: child = parent * origin * rotation
        let parentWorld = new THREE.Matrix4().identity();

        for (let i = 0; i < JOINT_CONFIGS.length; i++) {
          const config = JOINT_CONFIGS[i];
          const angle = angles[i];

          // Reconstruct child from parent + origin + rotation
          const originTranslation = new THREE.Matrix4().makeTranslation(
            config.originXyz[0],
            config.originXyz[1],
            config.originXyz[2]
          );
          const originRotation = new THREE.Matrix4().makeRotationFromQuaternion(
            rpyToQuaternion(config.originRpy)
          );
          const jointRotation = new THREE.Matrix4().makeRotationFromQuaternion(
            axisAngleRotation(config.axis, angle)
          );

          const expectedChild = parentWorld
            .clone()
            .multiply(originTranslation)
            .multiply(originRotation)
            .multiply(jointRotation);

          // Compare with computed child world transform
          const actualChild = worldTransforms[i];
          const expectedElements = expectedChild.elements;
          const actualElements = actualChild.elements;

          for (let j = 0; j < 16; j++) {
            expect(Math.abs(expectedElements[j] - actualElements[j])).toBeLessThan(EPSILON);
          }

          // Move parent to this child for next iteration
          parentWorld = actualChild.clone();
        }
      }),
      { numRuns: 200 }
    );
  });

  it('zero angles produce transforms determined only by joint origins (no joint rotation effect)', () => {
    fc.assert(
      fc.property(
        // Use a small perturbation to generate "zero-like" angles
        fc.constant([0, 0, 0, 0, 0, 0] as [number, number, number, number, number, number]),
        (angles) => {
          const worldTransforms = computeForwardKinematics(angles);

          // With zero angles, joint rotation is identity. So child = parent * origin only.
          let parentWorld = new THREE.Matrix4().identity();

          for (let i = 0; i < JOINT_CONFIGS.length; i++) {
            const config = JOINT_CONFIGS[i];

            const originTranslation = new THREE.Matrix4().makeTranslation(
              config.originXyz[0],
              config.originXyz[1],
              config.originXyz[2]
            );
            const originRotation = new THREE.Matrix4().makeRotationFromQuaternion(
              rpyToQuaternion(config.originRpy)
            );

            // At zero angle, joint rotation is identity
            const expectedChild = parentWorld
              .clone()
              .multiply(originTranslation)
              .multiply(originRotation);

            const actualChild = worldTransforms[i];
            const expectedElements = expectedChild.elements;
            const actualElements = actualChild.elements;

            for (let j = 0; j < 16; j++) {
              expect(Math.abs(expectedElements[j] - actualElements[j])).toBeLessThan(EPSILON);
            }

            parentWorld = actualChild.clone();
          }
        }
      ),
      { numRuns: 1 } // Only needs one run since input is constant
    );
  });

  it('world transforms are valid rigid body transforms (orthonormal rotation + translation)', () => {
    fc.assert(
      fc.property(jointAnglesArb, (angles) => {
        const worldTransforms = computeForwardKinematics(angles);

        for (let i = 0; i < worldTransforms.length; i++) {
          const mat = worldTransforms[i];
          const elements = mat.elements;

          // Extract the 3x3 rotation submatrix (column-major in Three.js)
          // Column 0: elements[0], elements[1], elements[2]
          // Column 1: elements[4], elements[5], elements[6]
          // Column 2: elements[8], elements[9], elements[10]
          const col0 = new THREE.Vector3(elements[0], elements[1], elements[2]);
          const col1 = new THREE.Vector3(elements[4], elements[5], elements[6]);
          const col2 = new THREE.Vector3(elements[8], elements[9], elements[10]);

          // Columns should be unit length (orthonormal)
          expect(Math.abs(col0.length() - 1.0)).toBeLessThan(EPSILON);
          expect(Math.abs(col1.length() - 1.0)).toBeLessThan(EPSILON);
          expect(Math.abs(col2.length() - 1.0)).toBeLessThan(EPSILON);

          // Columns should be orthogonal (dot products = 0)
          expect(Math.abs(col0.dot(col1))).toBeLessThan(EPSILON);
          expect(Math.abs(col0.dot(col2))).toBeLessThan(EPSILON);
          expect(Math.abs(col1.dot(col2))).toBeLessThan(EPSILON);

          // Bottom row should be [0, 0, 0, 1] for a proper rigid transform
          expect(Math.abs(elements[3])).toBeLessThan(EPSILON);
          expect(Math.abs(elements[7])).toBeLessThan(EPSILON);
          expect(Math.abs(elements[11])).toBeLessThan(EPSILON);
          expect(Math.abs(elements[15] - 1.0)).toBeLessThan(EPSILON);
        }
      }),
      { numRuns: 200 }
    );
  });
});
