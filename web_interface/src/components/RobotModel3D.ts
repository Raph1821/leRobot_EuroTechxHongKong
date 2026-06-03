/**
 * RobotModel3D — Three.js kinematic chain with STL meshes for the SO-100 arm.
 *
 * Loads all 7 STL meshes using STLLoader and builds a kinematic chain matching
 * the URDF parent-child relationships. Applies joint origins and rotation axes
 * from the URDF and provides updateJointAngles() to update all link transforms.
 *
 * Renders at zero-position (all angles = 0) before the first joint state is received.
 *
 * Validates: Requirements 7.1, 7.2, 7.6
 */

import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { JOINT_CONFIGS } from '@/types';

/**
 * Configuration for a single link in the kinematic chain.
 * Each link has a mesh, a parent joint defining its origin/axis, and a child group.
 */
interface LinkConfig {
  meshFile: string;
  jointIndex: number | null; // null for the base link (no controlling joint)
}

/**
 * The kinematic chain structure:
 * base_link (world) → Base (fixed) → Shoulder_Rotation_Pitch → Upper_Arm →
 * Lower_Arm → Wrist_Pitch_Roll → Fixed_Gripper → Moving_Jaw
 *
 * Each joint group contains:
 * 1. A translation to the joint origin (xyz)
 * 2. A rotation for the joint RPY (fixed frame rotation)
 * 3. A rotation about the joint axis (the variable joint angle)
 * 4. The child link mesh + child joint groups
 */

/** Link definitions in kinematic chain order, mapping meshes to joints */
const LINK_CHAIN: LinkConfig[] = [
  { meshFile: 'Base.STL', jointIndex: null },                // Base link (no parent joint)
  { meshFile: 'Shoulder_Rotation_Pitch.STL', jointIndex: 0 }, // Shoulder_Rotation
  { meshFile: 'Upper_Arm.STL', jointIndex: 1 },              // Shoulder_Pitch (note: URDF names this link "Upper_Arm" but connects via Shoulder_Pitch joint)
  { meshFile: 'Lower_Arm.STL', jointIndex: 2 },              // Elbow
  { meshFile: 'Wrist_Pitch_Roll.STL', jointIndex: 3 },       // Wrist_Pitch
  { meshFile: 'Fixed_Gripper.STL', jointIndex: 4 },          // Wrist_Roll
  { meshFile: 'Moving_Jaw.STL', jointIndex: 5 },             // Gripper
];

/** Default material for robot links */
const ROBOT_MATERIAL = new THREE.MeshPhongMaterial({
  color: 0xfcfc01, // bright yellow matching URDF
  specular: 0x444444,
  shininess: 30,
});

/**
 * Creates a rotation matrix from RPY (Roll, Pitch, Yaw) angles.
 * Uses the URDF convention: fixed-frame XYZ rotation (equivalent to ZYX Euler).
 */
function rpyToEuler(rpy: [number, number, number]): THREE.Euler {
  // URDF RPY is fixed-frame rotation: first roll about X, then pitch about Y, then yaw about Z
  return new THREE.Euler(rpy[0], rpy[1], rpy[2], 'XYZ');
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

export class RobotModel3D {
  /** The root Three.js group containing the entire robot */
  public readonly root: THREE.Group;

  /** Joint rotation objects — one per joint for angle updates */
  private jointRotationGroups: THREE.Object3D[] = [];

  /** Whether meshes have been loaded */
  private _loaded = false;

  /** Promise that resolves when all meshes are loaded */
  public readonly loadPromise: Promise<void>;

  constructor(meshBasePath = '/meshes') {
    this.root = new THREE.Group();
    this.root.name = 'SO100_Robot';
    this.loadPromise = this.buildKinematicChain(meshBasePath);
  }

  /** Whether all meshes have finished loading */
  get loaded(): boolean {
    return this._loaded;
  }

  /**
   * Builds the kinematic chain by creating nested Three.js groups
   * that represent joint origins, orientations, and variable rotations.
   *
   * Structure for each joint:
   *   parentGroup
   *     └─ jointOriginGroup (position = joint origin xyz, rotation = joint origin rpy)
   *          └─ jointRotationGroup (rotation = variable joint angle about axis)
   *               └─ linkMesh
   *               └─ next jointOriginGroup...
   */
  private async buildKinematicChain(meshBasePath: string): Promise<void> {
    const loader = new STLLoader();
    const meshPromises: Promise<THREE.BufferGeometry>[] = [];

    // Load all meshes in parallel
    for (const link of LINK_CHAIN) {
      const url = `${meshBasePath}/${link.meshFile}`;
      meshPromises.push(this.loadSTL(loader, url));
    }

    const geometries = await Promise.all(meshPromises);

    // Build the chain starting from the base
    let currentParent: THREE.Object3D = this.root;

    for (let i = 0; i < LINK_CHAIN.length; i++) {
      const link = LINK_CHAIN[i];
      const geometry = geometries[i];

      if (link.jointIndex === null) {
        // Base link — attached directly to root with no joint transform
        const mesh = new THREE.Mesh(geometry, ROBOT_MATERIAL.clone());
        mesh.name = `mesh_${link.meshFile}`;
        currentParent.add(mesh);
        // The base is also the parent for the next joint
        // currentParent stays as this.root
      } else {
        // Create joint transform hierarchy
        const jointConfig = JOINT_CONFIGS[link.jointIndex];

        // 1. Joint origin group: translates to joint origin and applies RPY
        const jointOriginGroup = new THREE.Group();
        jointOriginGroup.name = `joint_origin_${jointConfig.name}`;
        jointOriginGroup.position.set(
          jointConfig.originXyz[0],
          jointConfig.originXyz[1],
          jointConfig.originXyz[2]
        );
        jointOriginGroup.rotation.copy(rpyToEuler(jointConfig.originRpy));
        currentParent.add(jointOriginGroup);

        // 2. Joint rotation group: rotates about the joint axis (variable angle)
        const jointRotationGroup = new THREE.Group();
        jointRotationGroup.name = `joint_rotation_${jointConfig.name}`;
        jointOriginGroup.add(jointRotationGroup);

        // Store reference for angle updates
        this.jointRotationGroups.push(jointRotationGroup);

        // 3. Add the link mesh to the joint rotation group
        const mesh = new THREE.Mesh(geometry, ROBOT_MATERIAL.clone());
        mesh.name = `mesh_${link.meshFile}`;
        jointRotationGroup.add(mesh);

        // The rotation group becomes the parent for the next joint in the chain
        currentParent = jointRotationGroup;
      }
    }

    this._loaded = true;
  }

  /**
   * Loads an STL file and returns its geometry.
   */
  private loadSTL(loader: STLLoader, url: string): Promise<THREE.BufferGeometry> {
    return new Promise((resolve, reject) => {
      loader.load(
        url,
        (geometry) => {
          geometry.computeVertexNormals();
          resolve(geometry);
        },
        undefined,
        (error) => {
          reject(new Error(`Failed to load STL: ${url} — ${error}`));
        }
      );
    });
  }

  /**
   * Updates all joint angles in the kinematic chain.
   *
   * @param positions Array of 6 joint angles in radians, in order:
   *   [Shoulder_Rotation, Shoulder_Pitch, Elbow, Wrist_Pitch, Wrist_Roll, Gripper]
   *
   * Each joint rotation is applied about its defined axis from JOINT_CONFIGS.
   */
  updateJointAngles(positions: number[]): void {
    if (!this._loaded) return;

    const count = Math.min(positions.length, this.jointRotationGroups.length);
    for (let i = 0; i < count; i++) {
      const jointConfig = JOINT_CONFIGS[i];
      const angle = positions[i];
      const group = this.jointRotationGroups[i];

      // Apply rotation about the joint axis
      const quat = axisAngleRotation(jointConfig.axis, angle);
      group.quaternion.copy(quat);
    }
  }

  /**
   * Resets all joints to zero position.
   */
  resetToZero(): void {
    for (const group of this.jointRotationGroups) {
      group.quaternion.identity();
    }
  }

  /**
   * Disposes of all geometries and materials to free GPU memory.
   */
  dispose(): void {
    this.root.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        if (obj.material instanceof THREE.Material) {
          obj.material.dispose();
        }
      }
    });
  }
}
