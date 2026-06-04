/**
 * Unit tests for PoseManager component.
 *
 * Tests: save, list, delete, select poses; name validation; capacity limit;
 * session storage persistence; select-to-command sends trajectory_goal;
 * play sequence; trajectory status handling; progress indicator; error notifications.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { PoseManager, validatePoseName, validatePoseCapacity, buildTrajectoryGoal } from './PoseManager';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { JointStateMessage } from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

function createMockConnectionManager(): ConnectionManager {
  const listeners: Record<string, Function[]> = {};
  return {
    on: vi.fn((event: string, listener: Function) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(listener);
    }),
    off: vi.fn(),
    send: vi.fn(() => true),
    getState: vi.fn(() => 'connected' as const),
    removeAllListeners: vi.fn(),
    // Helper for tests to emit messages
    _emit: (event: string, ...args: unknown[]) => {
      for (const listener of listeners[event] || []) {
        listener(...args);
      }
    },
  } as unknown as ConnectionManager & { _emit: Function };
}

// ─── Mock sessionStorage ────────────────────────────────────────────────────

function createMockSessionStorage(): Storage {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
  };
}

// ─── Helper ─────────────────────────────────────────────────────────────────

function createJointStateMessage(positions: number[] = [0, 0, 0, 0, 0, 0]): JointStateMessage {
  return {
    type: 'joint_state',
    timestamp: Date.now(),
    joints: {
      names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow', 'Wrist_Pitch', 'Wrist_Roll', 'Gripper'],
      positions,
      velocities: [0, 0, 0, 0, 0, 0],
      efforts: [0, 0, 0, 0, 0, 0],
    },
  };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('validatePoseName', () => {
  it('accepts a name of 1 character', () => {
    expect(validatePoseName('A')).toBeNull();
  });

  it('accepts a name of 64 characters', () => {
    expect(validatePoseName('a'.repeat(64))).toBeNull();
  });

  it('rejects an empty name', () => {
    expect(validatePoseName('')).not.toBeNull();
  });

  it('rejects a name longer than 64 characters', () => {
    expect(validatePoseName('a'.repeat(65))).not.toBeNull();
  });
});

describe('validatePoseCapacity', () => {
  it('allows saving when count is below 50', () => {
    expect(validatePoseCapacity(0)).toBeNull();
    expect(validatePoseCapacity(49)).toBeNull();
  });

  it('rejects saving when count is 50', () => {
    expect(validatePoseCapacity(50)).not.toBeNull();
  });

  it('rejects saving when count exceeds 50', () => {
    expect(validatePoseCapacity(51)).not.toBeNull();
  });
});

describe('PoseManager', () => {
  let connectionManager: ConnectionManager & { _emit: Function };
  let poseManager: PoseManager;
  let mockStorage: Storage;

  beforeEach(() => {
    // Setup mock sessionStorage
    mockStorage = createMockSessionStorage();
    Object.defineProperty(globalThis, 'sessionStorage', { value: mockStorage, writable: true });

    connectionManager = createMockConnectionManager() as ConnectionManager & { _emit: Function };
    poseManager = new PoseManager(connectionManager);
  });

  describe('savePose', () => {
    it('saves a pose with valid name and joint positions', () => {
      // Simulate receiving a joint state
      const jointState = createJointStateMessage([0.5, -0.3, 1.0, 0.2, -1.0, 0.0]);
      poseManager.updateFromJointState(jointState);

      const error = poseManager.savePose('Home');
      expect(error).toBeNull();
      expect(poseManager.getPoseCount()).toBe(1);

      const poses = poseManager.getPoses();
      expect(poses[0].name).toBe('Home');
      expect(poses[0].positions['Shoulder_Rotation']).toBe(0.5);
      expect(poses[0].positions['Shoulder_Pitch']).toBe(-0.3);
      expect(poses[0].positions['Elbow']).toBe(1.0);
      expect(poses[0].positions['Wrist_Pitch']).toBe(0.2);
      expect(poses[0].positions['Wrist_Roll']).toBe(-1.0);
      // Gripper should NOT be included (only arm joints)
      expect(poses[0].positions['Gripper']).toBeUndefined();
    });

    it('rejects empty name', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      const error = poseManager.savePose('');
      expect(error).not.toBeNull();
      expect(poseManager.getPoseCount()).toBe(0);
    });

    it('rejects name longer than 64 characters', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      const error = poseManager.savePose('x'.repeat(65));
      expect(error).not.toBeNull();
      expect(poseManager.getPoseCount()).toBe(0);
    });

    it('rejects when no joint state is available', () => {
      const error = poseManager.savePose('Test');
      expect(error).not.toBeNull();
      expect(poseManager.getPoseCount()).toBe(0);
    });

    it('rejects when at max capacity (50 poses)', () => {
      poseManager.updateFromJointState(createJointStateMessage());

      // Save 50 poses
      for (let i = 0; i < 50; i++) {
        const err = poseManager.savePose(`Pose ${i}`);
        expect(err).toBeNull();
      }

      // 51st should fail
      const error = poseManager.savePose('One Too Many');
      expect(error).not.toBeNull();
      expect(poseManager.getPoseCount()).toBe(50);
    });

    it('stores poses to session storage', () => {
      poseManager.updateFromJointState(createJointStateMessage([1.0, 0, 0, 0, 0, 0]));
      poseManager.savePose('Stored');

      expect(mockStorage.setItem).toHaveBeenCalledWith(
        'so100_saved_poses',
        expect.any(String)
      );
    });
  });

  describe('deletePose', () => {
    it('removes pose at given index', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('First');
      poseManager.savePose('Second');
      poseManager.savePose('Third');

      poseManager.deletePose(1);

      expect(poseManager.getPoseCount()).toBe(2);
      const poses = poseManager.getPoses();
      expect(poses[0].name).toBe('First');
      expect(poses[1].name).toBe('Third');
    });

    it('does nothing for out-of-range index', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('Only');

      poseManager.deletePose(-1);
      poseManager.deletePose(5);
      expect(poseManager.getPoseCount()).toBe(1);
    });
  });

  describe('selectPose', () => {
    it('sends a trajectory_goal message for the selected pose', () => {
      poseManager.updateFromJointState(
        createJointStateMessage([0.5, -0.3, 1.0, 0.2, -1.0, 0.0])
      );
      poseManager.savePose('Target');

      const result = poseManager.selectPose(0);
      expect(result).toBe(true);

      expect(connectionManager.send).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'trajectory_goal',
          waypoints: [
            expect.objectContaining({
              positions: expect.objectContaining({
                Shoulder_Rotation: 0.5,
                Shoulder_Pitch: -0.3,
                Elbow: 1.0,
                Wrist_Pitch: 0.2,
                Wrist_Roll: -1.0,
              }),
              time_from_start: 2.0,
            }),
          ],
        })
      );
    });

    it('returns false when not connected', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');

      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('Test');

      const result = poseManager.selectPose(0);
      expect(result).toBe(false);
    });

    it('returns false for out-of-range index', () => {
      const result = poseManager.selectPose(99);
      expect(result).toBe(false);
    });

    it('uses configured duration for time_from_start', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('Timed');
      poseManager.setDuration(5.0);

      poseManager.selectPose(0);

      expect(connectionManager.send).toHaveBeenCalledWith(
        expect.objectContaining({
          waypoints: [
            expect.objectContaining({
              time_from_start: 5.0,
            }),
          ],
        })
      );
    });
  });

  describe('setDuration', () => {
    it('clamps duration to minimum 0.5', () => {
      poseManager.setDuration(0.1);
      expect(poseManager.getDuration()).toBe(0.5);
    });

    it('clamps duration to maximum 30.0', () => {
      poseManager.setDuration(50);
      expect(poseManager.getDuration()).toBe(30.0);
    });

    it('accepts valid durations within range', () => {
      poseManager.setDuration(10.0);
      expect(poseManager.getDuration()).toBe(10.0);
    });
  });

  describe('updateFromJointState', () => {
    it('tracks the latest arm joint positions', () => {
      const msg = createJointStateMessage([1.5, -0.5, 0.8, 0.3, -2.0, 1.0]);
      poseManager.updateFromJointState(msg);

      poseManager.savePose('Captured');
      const poses = poseManager.getPoses();
      expect(poses[0].positions['Shoulder_Rotation']).toBe(1.5);
      expect(poses[0].positions['Elbow']).toBe(0.8);
    });

    it('responds to message events from ConnectionManager', () => {
      const msg = createJointStateMessage([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);
      connectionManager._emit('message', msg);

      poseManager.savePose('FromEvent');
      const poses = poseManager.getPoses();
      expect(poses[0].positions['Shoulder_Rotation']).toBe(0.1);
    });
  });

  describe('session storage persistence', () => {
    it('loads poses from session storage on construction', () => {
      const storedPoses = [
        {
          name: 'Stored Pose',
          positions: { Shoulder_Rotation: 0.5, Shoulder_Pitch: 0, Elbow: 0, Wrist_Pitch: 0, Wrist_Roll: 0 },
          savedAt: 1000,
        },
      ];
      (mockStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(JSON.stringify(storedPoses));

      const mgr = new PoseManager(connectionManager);
      expect(mgr.getPoseCount()).toBe(1);
      expect(mgr.getPoses()[0].name).toBe('Stored Pose');
    });

    it('handles corrupted storage data gracefully', () => {
      (mockStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue('not valid json!!!');

      const mgr = new PoseManager(connectionManager);
      expect(mgr.getPoseCount()).toBe(0);
    });

    it('filters out invalid pose entries from storage', () => {
      const storedPoses = [
        { name: 'Valid', positions: { Shoulder_Rotation: 0 }, savedAt: 1000 },
        { name: '', positions: {}, savedAt: 2000 }, // invalid: empty name
        { positions: {}, savedAt: 3000 }, // invalid: no name
      ];
      (mockStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(JSON.stringify(storedPoses));

      const mgr = new PoseManager(connectionManager);
      expect(mgr.getPoseCount()).toBe(1);
      expect(mgr.getPoses()[0].name).toBe('Valid');
    });
  });

  describe('buildTrajectoryGoal', () => {
    it('constructs a trajectory goal with correct waypoint count', () => {
      const poses = [
        { name: 'A', positions: { Shoulder_Rotation: 0.5, Shoulder_Pitch: 0, Elbow: 0, Wrist_Pitch: 0, Wrist_Roll: 0 }, savedAt: 1000 },
        { name: 'B', positions: { Shoulder_Rotation: 1.0, Shoulder_Pitch: 0.5, Elbow: 0.3, Wrist_Pitch: 0, Wrist_Roll: 0 }, savedAt: 2000 },
        { name: 'C', positions: { Shoulder_Rotation: -0.5, Shoulder_Pitch: -0.3, Elbow: -0.1, Wrist_Pitch: 0.2, Wrist_Roll: 0.1 }, savedAt: 3000 },
      ];

      const goal = buildTrajectoryGoal(poses, 2.0);

      expect(goal.type).toBe('trajectory_goal');
      expect(goal.waypoints).toHaveLength(3);
    });

    it('sets time_from_start as (index + 1) × interval', () => {
      const poses = [
        { name: 'A', positions: { Shoulder_Rotation: 0 }, savedAt: 1000 },
        { name: 'B', positions: { Shoulder_Rotation: 1 }, savedAt: 2000 },
        { name: 'C', positions: { Shoulder_Rotation: -1 }, savedAt: 3000 },
      ];

      const goal = buildTrajectoryGoal(poses, 3.0);

      expect(goal.waypoints[0].time_from_start).toBe(3.0);
      expect(goal.waypoints[1].time_from_start).toBe(6.0);
      expect(goal.waypoints[2].time_from_start).toBe(9.0);
    });

    it('preserves pose joint positions in waypoints', () => {
      const poses = [
        { name: 'A', positions: { Shoulder_Rotation: 0.5, Shoulder_Pitch: -0.3 }, savedAt: 1000 },
      ];

      const goal = buildTrajectoryGoal(poses, 2.0);

      expect(goal.waypoints[0].positions).toEqual({ Shoulder_Rotation: 0.5, Shoulder_Pitch: -0.3 });
    });

    it('clamps interval to minimum 0.5', () => {
      const poses = [
        { name: 'A', positions: { Shoulder_Rotation: 0 }, savedAt: 1000 },
        { name: 'B', positions: { Shoulder_Rotation: 1 }, savedAt: 2000 },
      ];

      const goal = buildTrajectoryGoal(poses, 0.1);

      expect(goal.waypoints[0].time_from_start).toBe(0.5);
      expect(goal.waypoints[1].time_from_start).toBe(1.0);
    });

    it('clamps interval to maximum 30.0', () => {
      const poses = [
        { name: 'A', positions: { Shoulder_Rotation: 0 }, savedAt: 1000 },
        { name: 'B', positions: { Shoulder_Rotation: 1 }, savedAt: 2000 },
      ];

      const goal = buildTrajectoryGoal(poses, 50.0);

      expect(goal.waypoints[0].time_from_start).toBe(30.0);
      expect(goal.waypoints[1].time_from_start).toBe(60.0);
    });
  });

  describe('playSequence', () => {
    it('sends a trajectory goal with all poses as waypoints', () => {
      poseManager.updateFromJointState(createJointStateMessage([0.5, 0.3, 0.1, 0.2, -0.5, 0]));
      poseManager.savePose('Pose1');
      poseManager.updateFromJointState(createJointStateMessage([1.0, -0.3, 0.5, 0.4, 1.0, 0]));
      poseManager.savePose('Pose2');

      const result = poseManager.playSequence(3.0);

      expect(result).toBe(true);
      expect(connectionManager.send).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'trajectory_goal',
          waypoints: expect.arrayContaining([
            expect.objectContaining({ time_from_start: 3.0 }),
            expect.objectContaining({ time_from_start: 6.0 }),
          ]),
        })
      );
    });

    it('returns false when fewer than 2 poses saved', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('OnlyOne');

      const result = poseManager.playSequence();

      expect(result).toBe(false);
      expect(connectionManager.send).not.toHaveBeenCalled();
    });

    it('returns false when no poses saved', () => {
      const result = poseManager.playSequence();
      expect(result).toBe(false);
    });

    it('returns false when already playing', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');

      // First play succeeds
      poseManager.playSequence();
      // Second play while in progress fails
      const result = poseManager.playSequence();
      expect(result).toBe(false);
    });

    it('returns false when disconnected', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');

      const result = poseManager.playSequence();
      expect(result).toBe(false);
    });

    it('uses configured duration when no interval specified', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.setDuration(5.0);

      poseManager.playSequence();

      expect(connectionManager.send).toHaveBeenCalledWith(
        expect.objectContaining({
          waypoints: expect.arrayContaining([
            expect.objectContaining({ time_from_start: 5.0 }),
            expect.objectContaining({ time_from_start: 10.0 }),
          ]),
        })
      );
    });

    it('sets isPlaying to true after sending', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');

      poseManager.playSequence();

      expect(poseManager.isPlaying()).toBe(true);
    });
  });

  describe('canPlaySequence', () => {
    it('returns false with fewer than 2 poses', () => {
      expect(poseManager.canPlaySequence()).toBe(false);

      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('One');
      expect(poseManager.canPlaySequence()).toBe(false);
    });

    it('returns true with 2 or more poses', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      expect(poseManager.canPlaySequence()).toBe(true);
    });

    it('returns false while playing', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      expect(poseManager.canPlaySequence()).toBe(false);
    });
  });

  describe('handleTrajectoryStatus', () => {
    beforeEach(() => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();
    });

    it('keeps isPlaying true on "executing" status', () => {
      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'executing',
        message: 'Trajectory in progress',
      });

      expect(poseManager.isPlaying()).toBe(true);
    });

    it('sets isPlaying to false on "succeeded" status', () => {
      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'Trajectory completed',
      });

      expect(poseManager.isPlaying()).toBe(false);
    });

    it('sets isPlaying to false and stores error on "aborted" status', () => {
      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Joint limit exceeded',
      });

      expect(poseManager.isPlaying()).toBe(false);
      expect(poseManager.getLastTrajectoryError()).toContain('aborted');
      expect(poseManager.getLastTrajectoryError()).toContain('Joint limit exceeded');
    });

    it('sets isPlaying to false and stores error on "preempted" status', () => {
      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'preempted',
        message: 'New goal received',
      });

      expect(poseManager.isPlaying()).toBe(false);
      expect(poseManager.getLastTrajectoryError()).toContain('preempted');
      expect(poseManager.getLastTrajectoryError()).toContain('New goal received');
    });

    it('responds to trajectory_status messages via ConnectionManager events', () => {
      // Reset state for a clean test
      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'done',
      });
      expect(poseManager.isPlaying()).toBe(false);

      // Start a new sequence
      poseManager.playSequence();
      expect(poseManager.isPlaying()).toBe(true);

      // Emit trajectory status via connection manager message event
      connectionManager._emit('message', {
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'All done',
      });

      expect(poseManager.isPlaying()).toBe(false);
    });
  });

  describe('error notifications', () => {
    it('has no error initially', () => {
      expect(poseManager.getLastTrajectoryError()).toBeNull();
    });

    it('stores error on trajectory failure', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Robot fault',
      });

      expect(poseManager.getLastTrajectoryError()).not.toBeNull();
    });

    it('clears error on dismissError()', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Error occurred',
      });

      poseManager.dismissError();
      expect(poseManager.getLastTrajectoryError()).toBeNull();
    });

    it('clears error when a new trajectory command is issued (selectPose)', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Error occurred',
      });

      // Issuing a new selectPose should clear the error
      poseManager.selectPose(0);
      expect(poseManager.getLastTrajectoryError()).toBeNull();
    });

    it('clears error when a new playSequence command is issued', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      poseManager.handleTrajectoryStatus({
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Error occurred',
      });

      // Play sequence again should clear the error
      poseManager.playSequence();
      expect(poseManager.getLastTrajectoryError()).toBeNull();
    });
  });

  describe('selectPose during playback', () => {
    it('returns false when playing', () => {
      poseManager.updateFromJointState(createJointStateMessage());
      poseManager.savePose('A');
      poseManager.savePose('B');
      poseManager.playSequence();

      const result = poseManager.selectPose(0);
      expect(result).toBe(false);
    });
  });
});
