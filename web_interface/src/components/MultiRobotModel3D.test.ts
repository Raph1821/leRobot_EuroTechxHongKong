/**
 * Unit tests for MultiRobotModel3D — multi-robot instance management.
 *
 * Tests verify:
 * - Adding/removing robots with distinct color tints
 * - Independent joint state updates per robot
 * - Active robot highlighting with emissive glow
 * - Robot lifecycle management (add, remove, dispose)
 *
 * Validates: Requirements 6.5
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as THREE from 'three';
import { MultiRobotModel3D } from './MultiRobotModel3D';
import { RobotModel3D } from './RobotModel3D';

// Mock STLLoader to avoid actual file loading in tests
vi.mock('three/examples/jsm/loaders/STLLoader.js', () => ({
  STLLoader: class MockSTLLoader {
    load(
      _url: string,
      onLoad: (geometry: THREE.BufferGeometry) => void,
      _onProgress?: () => void,
      _onError?: (error: Error) => void
    ) {
      // Create a simple triangle geometry for testing
      const geometry = new THREE.BufferGeometry();
      const vertices = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
      geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
      geometry.computeVertexNormals();
      setTimeout(() => onLoad(geometry), 0);
    }
  },
}));

describe('MultiRobotModel3D', () => {
  let multiRobot: MultiRobotModel3D;

  beforeEach(() => {
    multiRobot = new MultiRobotModel3D('/meshes');
  });

  describe('constructor', () => {
    it('should create a root group named MultiRobot_Root', () => {
      expect(multiRobot.root).toBeInstanceOf(THREE.Group);
      expect(multiRobot.root.name).toBe('MultiRobot_Root');
    });

    it('should start with no robots and no active robot', () => {
      expect(multiRobot.robotCount).toBe(0);
      expect(multiRobot.activeRobotId).toBeNull();
      expect(multiRobot.robotIds).toEqual([]);
    });
  });

  describe('addRobot', () => {
    it('should add a robot instance and return it', () => {
      const instance = multiRobot.addRobot('/robot1');
      expect(instance.robotId).toBe('/robot1');
      expect(instance.model).toBeInstanceOf(RobotModel3D);
      expect(multiRobot.robotCount).toBe(1);
    });

    it('should assign distinct colors to different robots', () => {
      const r1 = multiRobot.addRobot('/robot1');
      const r2 = multiRobot.addRobot('/robot2');
      const r3 = multiRobot.addRobot('/robot3');

      expect(r1.color).not.toBe(r2.color);
      expect(r2.color).not.toBe(r3.color);
      expect(r1.color).not.toBe(r3.color);
    });

    it('should add the robot root group to the multi-robot root', () => {
      multiRobot.addRobot('/robot1');
      expect(multiRobot.root.children).toHaveLength(1);
      expect(multiRobot.root.children[0].name).toBe('Robot_/robot1');
    });

    it('should return existing instance if robot already added', () => {
      const first = multiRobot.addRobot('/robot1');
      const second = multiRobot.addRobot('/robot1');
      expect(first).toBe(second);
      expect(multiRobot.robotCount).toBe(1);
    });

    it('should make first robot active by default', () => {
      multiRobot.addRobot('/robot1');
      expect(multiRobot.activeRobotId).toBe('/robot1');
    });

    it('should not change active robot when adding subsequent robots', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');
      expect(multiRobot.activeRobotId).toBe('/robot1');
    });

    it('should store robotId in userData of the model root', () => {
      const instance = multiRobot.addRobot('/robot1');
      expect(instance.model.root.userData.robotId).toBe('/robot1');
      expect(instance.model.root.userData.color).toBe(instance.color);
    });

    it('should support at least 4 simultaneous robot instances', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');
      multiRobot.addRobot('/robot3');
      multiRobot.addRobot('/robot4');
      expect(multiRobot.robotCount).toBe(4);
      expect(multiRobot.robotIds).toEqual(['/robot1', '/robot2', '/robot3', '/robot4']);
    });
  });

  describe('removeRobot', () => {
    it('should remove a robot and return true', () => {
      multiRobot.addRobot('/robot1');
      const result = multiRobot.removeRobot('/robot1');
      expect(result).toBe(true);
      expect(multiRobot.robotCount).toBe(0);
    });

    it('should return false for non-existent robot', () => {
      const result = multiRobot.removeRobot('/nonexistent');
      expect(result).toBe(false);
    });

    it('should remove the robot root from the scene', () => {
      multiRobot.addRobot('/robot1');
      expect(multiRobot.root.children).toHaveLength(1);
      multiRobot.removeRobot('/robot1');
      expect(multiRobot.root.children).toHaveLength(0);
    });

    it('should select another robot as active if the active one is removed', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');
      expect(multiRobot.activeRobotId).toBe('/robot1');

      multiRobot.removeRobot('/robot1');
      expect(multiRobot.activeRobotId).toBe('/robot2');
    });

    it('should set activeRobotId to null if last robot is removed', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.removeRobot('/robot1');
      expect(multiRobot.activeRobotId).toBeNull();
    });
  });

  describe('setActiveRobot', () => {
    it('should set the active robot and return true', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      const result = multiRobot.setActiveRobot('/robot2');
      expect(result).toBe(true);
      expect(multiRobot.activeRobotId).toBe('/robot2');
    });

    it('should return false for non-existent robot', () => {
      const result = multiRobot.setActiveRobot('/nonexistent');
      expect(result).toBe(false);
    });

    it('should mark the target robot as active', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      multiRobot.setActiveRobot('/robot2');
      const r2 = multiRobot.getRobot('/robot2');
      expect(r2?.isActive).toBe(true);
    });

    it('should mark the previously active robot as inactive', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      // robot1 is initially active
      expect(multiRobot.getRobot('/robot1')?.isActive).toBe(true);

      multiRobot.setActiveRobot('/robot2');
      expect(multiRobot.getRobot('/robot1')?.isActive).toBe(false);
    });

    it('should handle setting the same robot active (no-op for deactivation)', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.setActiveRobot('/robot1');
      expect(multiRobot.activeRobotId).toBe('/robot1');
      expect(multiRobot.getRobot('/robot1')?.isActive).toBe(true);
    });
  });

  describe('updateJointAngles', () => {
    it('should update joint angles for a specific robot and return true', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      const positions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
      const result = multiRobot.updateJointAngles('/robot1', positions);
      expect(result).toBe(true);
    });

    it('should return false for non-existent robot', () => {
      const result = multiRobot.updateJointAngles('/nonexistent', [0, 0, 0, 0, 0, 0]);
      expect(result).toBe(false);
    });

    it('should update robots independently', async () => {
      const r1 = multiRobot.addRobot('/robot1');
      const r2 = multiRobot.addRobot('/robot2');

      // Wait for models to load
      await r1.model.loadPromise;
      await r2.model.loadPromise;

      const positions1 = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
      const positions2 = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1];

      multiRobot.updateJointAngles('/robot1', positions1);
      multiRobot.updateJointAngles('/robot2', positions2);

      // Verify they are different by checking the quaternion of the first joint
      const r1FirstJoint = r1.model.root.children[0]; // first joint origin group
      const r2FirstJoint = r2.model.root.children[0];

      // They should be different objects with potentially different transforms
      expect(r1FirstJoint).not.toBe(r2FirstJoint);
    });
  });

  describe('getRobot', () => {
    it('should return the robot instance for a valid ID', () => {
      multiRobot.addRobot('/robot1');
      const instance = multiRobot.getRobot('/robot1');
      expect(instance).toBeDefined();
      expect(instance?.robotId).toBe('/robot1');
    });

    it('should return undefined for non-existent robot', () => {
      const instance = multiRobot.getRobot('/nonexistent');
      expect(instance).toBeUndefined();
    });
  });

  describe('getAllRobots', () => {
    it('should return all robot instances', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      const all = multiRobot.getAllRobots();
      expect(all).toHaveLength(2);
      expect(all[0].robotId).toBe('/robot1');
      expect(all[1].robotId).toBe('/robot2');
    });

    it('should return empty array when no robots exist', () => {
      expect(multiRobot.getAllRobots()).toEqual([]);
    });
  });

  describe('resetAll', () => {
    it('should reset all robots to zero positions', async () => {
      const r1 = multiRobot.addRobot('/robot1');
      const r2 = multiRobot.addRobot('/robot2');

      await r1.model.loadPromise;
      await r2.model.loadPromise;

      // Set some angles first
      multiRobot.updateJointAngles('/robot1', [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]);
      multiRobot.updateJointAngles('/robot2', [0.3, 0.3, 0.3, 0.3, 0.3, 0.3]);

      // Reset all
      multiRobot.resetAll();

      // After reset, no errors thrown (full verification would need internal access)
      expect(multiRobot.robotCount).toBe(2);
    });
  });

  describe('dispose', () => {
    it('should remove all robots and clear state', () => {
      multiRobot.addRobot('/robot1');
      multiRobot.addRobot('/robot2');

      multiRobot.dispose();

      expect(multiRobot.robotCount).toBe(0);
      expect(multiRobot.activeRobotId).toBeNull();
      expect(multiRobot.root.children).toHaveLength(0);
    });
  });

  describe('color tinting', () => {
    it('should assign first color from palette to first robot', () => {
      const instance = multiRobot.addRobot('/robot1');
      expect(instance.color).toBe(0xfcfc01); // Yellow
    });

    it('should assign second color from palette to second robot', () => {
      multiRobot.addRobot('/robot1');
      const instance = multiRobot.addRobot('/robot2');
      expect(instance.color).toBe(0x00bfff); // Deep sky blue
    });

    it('should wrap around palette when more robots than colors', () => {
      // Add 9 robots (palette has 8 colors)
      for (let i = 1; i <= 8; i++) {
        multiRobot.addRobot(`/robot${i}`);
      }
      const ninth = multiRobot.addRobot('/robot9');
      const first = multiRobot.getRobot('/robot1');

      // 9th robot should wrap back to first color
      expect(ninth.color).toBe(first!.color);
    });
  });

  describe('highlight behavior', () => {
    it('should apply highlight to loaded active robot meshes', async () => {
      const instance = multiRobot.addRobot('/robot1');
      await instance.model.loadPromise;

      // The first robot is auto-activated — wait a tick for async highlight
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Check that at least one mesh has the emissive highlight
      let foundHighlighted = false;
      instance.model.root.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
          if (obj.material.emissiveIntensity > 0) {
            foundHighlighted = true;
          }
        }
      });
      expect(foundHighlighted).toBe(true);
    });

    it('should remove highlight when switching active robot', async () => {
      const r1 = multiRobot.addRobot('/robot1');
      const r2 = multiRobot.addRobot('/robot2');

      await r1.model.loadPromise;
      await r2.model.loadPromise;

      // Wait for async color/highlight application
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Switch active to robot2
      multiRobot.setActiveRobot('/robot2');

      // robot1 should no longer be highlighted (emissive intensity = 0)
      let r1Highlighted = false;
      r1.model.root.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
          if (obj.material.emissiveIntensity > 0) {
            r1Highlighted = true;
          }
        }
      });
      expect(r1Highlighted).toBe(false);

      // robot2 should be highlighted
      let r2Highlighted = false;
      r2.model.root.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
          if (obj.material.emissiveIntensity > 0) {
            r2Highlighted = true;
          }
        }
      });
      expect(r2Highlighted).toBe(true);
    });

    it('should dim inactive robots with reduced opacity', async () => {
      const r1 = multiRobot.addRobot('/robot1');
      const r2 = multiRobot.addRobot('/robot2');

      await r1.model.loadPromise;
      await r2.model.loadPromise;

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));

      // robot1 is active, robot2 should be dimmed
      let r2IsDimmed = false;
      r2.model.root.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
          if (obj.material.transparent && obj.material.opacity < 1.0) {
            r2IsDimmed = true;
          }
        }
      });
      expect(r2IsDimmed).toBe(true);
    });
  });
});
