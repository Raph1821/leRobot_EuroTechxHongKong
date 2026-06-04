/**
 * MultiRobotModel3D — Manages multiple RobotModel3D instances for multi-robot support.
 *
 * Renders all configured robots simultaneously in the 3D scene, each with:
 * - A distinct color tint for visual differentiation
 * - Independent joint state updates
 * - A highlight indicator on the active (selected) robot
 *
 * Validates: Requirements 6.5
 */

import * as THREE from 'three';
import { RobotModel3D } from './RobotModel3D';

/**
 * Predefined color tints for distinguishing multiple robots.
 * Each color is applied as a hue shift on the robot meshes.
 */
const ROBOT_COLOR_PALETTE: number[] = [
  0xfcfc01, // Yellow (default/first robot)
  0x00bfff, // Deep sky blue
  0xff6347, // Tomato red
  0x32cd32, // Lime green
  0xff69b4, // Hot pink
  0xffa500, // Orange
  0x9370db, // Medium purple
  0x00ced1, // Dark turquoise
];

/**
 * Configuration for the active robot highlight effect.
 */
const HIGHLIGHT_CONFIG = {
  /** Emissive color for the active robot highlight */
  emissiveColor: 0xffffff,
  /** Emissive intensity for the active robot */
  emissiveIntensity: 0.3,
  /** Opacity for inactive (non-active) robots */
  inactiveOpacity: 0.6,
  /** Opacity for the active robot */
  activeOpacity: 1.0,
} as const;

/**
 * Represents a single robot instance managed by MultiRobotModel3D.
 */
export interface RobotInstance {
  /** The robot's namespace identifier (e.g., "/robot1") */
  robotId: string;
  /** The underlying RobotModel3D instance */
  model: RobotModel3D;
  /** The color tint applied to this robot */
  color: number;
  /** Whether this robot is currently the active (highlighted) one */
  isActive: boolean;
}

/**
 * MultiRobotModel3D manages multiple simultaneous robot instances in a single
 * 3D scene. Each robot is visually distinct via color tinting, and the active
 * robot is highlighted with an emissive glow effect.
 */
export class MultiRobotModel3D {
  /** The root Three.js group containing all robot instances */
  public readonly root: THREE.Group;

  /** Map of robot_id → RobotInstance */
  private robots: Map<string, RobotInstance> = new Map();

  /** The currently active robot ID (highlighted) */
  private _activeRobotId: string | null = null;

  /** Base path for mesh files */
  private readonly meshBasePath: string;

  constructor(meshBasePath = '/meshes') {
    this.root = new THREE.Group();
    this.root.name = 'MultiRobot_Root';
    this.meshBasePath = meshBasePath;
  }

  /** The currently active robot ID, or null if none is active */
  get activeRobotId(): string | null {
    return this._activeRobotId;
  }

  /** Returns the list of all robot IDs currently managed */
  get robotIds(): string[] {
    return Array.from(this.robots.keys());
  }

  /** Returns the number of robot instances currently managed */
  get robotCount(): number {
    return this.robots.size;
  }

  /**
   * Adds a new robot instance identified by the given robot_id (namespace).
   * The robot is assigned a distinct color from the palette based on its index.
   *
   * @param robotId The namespace identifier for the robot (e.g., "/robot1")
   * @returns The RobotInstance that was created, or the existing one if already present
   */
  addRobot(robotId: string): RobotInstance {
    // If robot already exists, return it
    const existing = this.robots.get(robotId);
    if (existing) {
      return existing;
    }

    // Create a new RobotModel3D instance
    const model = new RobotModel3D(this.meshBasePath);

    // Assign a color from the palette based on the number of robots already added
    const colorIndex = this.robots.size % ROBOT_COLOR_PALETTE.length;
    const color = ROBOT_COLOR_PALETTE[colorIndex];

    // Apply the color tint to the model once it's loaded
    model.loadPromise.then(() => {
      this.applyColorTint(model, color);
      // If this robot is active, apply the highlight
      const instance = this.robots.get(robotId);
      if (instance?.isActive) {
        this.applyHighlight(model, true);
      } else {
        this.applyHighlight(model, false);
      }
    });

    // Create the instance record
    const instance: RobotInstance = {
      robotId,
      model,
      color,
      isActive: false,
    };

    // Add a label to the robot's root group for identification
    model.root.name = `Robot_${robotId}`;
    model.root.userData = { robotId, color };

    // Add to the scene
    this.root.add(model.root);
    this.robots.set(robotId, instance);

    // If this is the first robot and no active robot is set, make it active
    if (this.robots.size === 1 && this._activeRobotId === null) {
      this.setActiveRobot(robotId);
    }

    return instance;
  }

  /**
   * Removes a robot instance by its robot_id.
   *
   * @param robotId The namespace identifier of the robot to remove
   * @returns true if the robot was removed, false if it wasn't found
   */
  removeRobot(robotId: string): boolean {
    const instance = this.robots.get(robotId);
    if (!instance) {
      return false;
    }

    // Remove from scene
    this.root.remove(instance.model.root);

    // Dispose of the model's resources
    instance.model.dispose();

    // Remove from map
    this.robots.delete(robotId);

    // If the removed robot was active, clear active or select another
    if (this._activeRobotId === robotId) {
      const remaining = Array.from(this.robots.keys());
      if (remaining.length > 0) {
        this.setActiveRobot(remaining[0]);
      } else {
        this._activeRobotId = null;
      }
    }

    return true;
  }

  /**
   * Sets the active (highlighted) robot. The active robot gets an emissive
   * highlight effect, while other robots are slightly dimmed.
   *
   * @param robotId The namespace identifier of the robot to make active
   * @returns true if the robot was found and activated, false otherwise
   */
  setActiveRobot(robotId: string): boolean {
    const targetInstance = this.robots.get(robotId);
    if (!targetInstance) {
      return false;
    }

    // Deactivate the previously active robot
    if (this._activeRobotId !== null && this._activeRobotId !== robotId) {
      const prevInstance = this.robots.get(this._activeRobotId);
      if (prevInstance) {
        prevInstance.isActive = false;
        if (prevInstance.model.loaded) {
          this.applyHighlight(prevInstance.model, false);
        }
      }
    }

    // Activate the target robot
    targetInstance.isActive = true;
    this._activeRobotId = robotId;

    if (targetInstance.model.loaded) {
      this.applyHighlight(targetInstance.model, true);
    }

    // Dim all other robots
    for (const [id, instance] of this.robots) {
      if (id !== robotId && instance.model.loaded) {
        this.applyHighlight(instance.model, false);
      }
    }

    return true;
  }

  /**
   * Updates the joint angles for a specific robot instance.
   *
   * @param robotId The namespace identifier of the robot
   * @param positions Array of joint angles in radians
   * @returns true if the robot was found and updated, false otherwise
   */
  updateJointAngles(robotId: string, positions: number[]): boolean {
    const instance = this.robots.get(robotId);
    if (!instance) {
      return false;
    }

    instance.model.updateJointAngles(positions);
    return true;
  }

  /**
   * Gets the RobotInstance for a given robot_id.
   *
   * @param robotId The namespace identifier
   * @returns The RobotInstance or undefined if not found
   */
  getRobot(robotId: string): RobotInstance | undefined {
    return this.robots.get(robotId);
  }

  /**
   * Returns all robot instances as an array.
   */
  getAllRobots(): RobotInstance[] {
    return Array.from(this.robots.values());
  }

  /**
   * Resets all robots to their zero joint positions.
   */
  resetAll(): void {
    for (const instance of this.robots.values()) {
      instance.model.resetToZero();
    }
  }

  /**
   * Disposes of all robot instances and cleans up resources.
   */
  dispose(): void {
    for (const instance of this.robots.values()) {
      this.root.remove(instance.model.root);
      instance.model.dispose();
    }
    this.robots.clear();
    this._activeRobotId = null;
  }

  /**
   * Applies a color tint to all meshes of a robot model.
   */
  private applyColorTint(model: RobotModel3D, color: number): void {
    model.root.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
        obj.material.color.setHex(color);
      }
    });
  }

  /**
   * Applies or removes the highlight effect on a robot model.
   * Active robots get an emissive glow; inactive robots are dimmed.
   */
  private applyHighlight(model: RobotModel3D, isActive: boolean): void {
    model.root.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
        if (isActive) {
          obj.material.emissive.setHex(HIGHLIGHT_CONFIG.emissiveColor);
          obj.material.emissiveIntensity = HIGHLIGHT_CONFIG.emissiveIntensity;
          obj.material.opacity = HIGHLIGHT_CONFIG.activeOpacity;
          obj.material.transparent = false;
        } else {
          obj.material.emissive.setHex(0x000000);
          obj.material.emissiveIntensity = 0;
          obj.material.opacity = HIGHLIGHT_CONFIG.inactiveOpacity;
          obj.material.transparent = true;
        }
      }
    });
  }
}
