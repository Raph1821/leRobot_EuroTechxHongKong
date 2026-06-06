/**
 * Unit tests for RobotViewer — wiring ConnectionManager to RobotModel3D.
 *
 * Validates: Requirements 7.2, 7.7
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RobotViewer } from './RobotViewer';
import type { ServerMessage, JointStateMessage, ConnectionState } from '../types';

// ─── Mocks ──────────────────────────────────────────────────────────────────

/** Minimal mock of ConnectionManager with event emitter behavior */
function createMockConnectionManager() {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    message: [],
    stateChange: [],
    controlsEnabled: [],
    controlsDisabled: [],
  };

  return {
    on: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(listener);
    }),
    off: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      const list = listeners[event] ?? [];
      const index = list.indexOf(listener);
      if (index !== -1) list.splice(index, 1);
    }),
    getState: vi.fn(() => 'disconnected' as ConnectionState),
    // Test helper: emit events
    _emit(event: string, ...args: unknown[]) {
      for (const listener of listeners[event] ?? []) {
        listener(...args);
      }
    },
  };
}

/** Minimal mock of RobotModel3D */
function createMockRobotModel() {
  return {
    updateJointAngles: vi.fn(),
    resetToZero: vi.fn(),
    root: {},
    loaded: true,
    loadPromise: Promise.resolve(),
    dispose: vi.fn(),
  };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('RobotViewer', () => {
  let mockCM: ReturnType<typeof createMockConnectionManager>;
  let mockModel: ReturnType<typeof createMockRobotModel>;
  let viewer: RobotViewer;

  beforeEach(() => {
    mockCM = createMockConnectionManager();
    mockModel = createMockRobotModel();
    viewer = new RobotViewer(mockCM as any, mockModel as any);
  });

  describe('joint state message handling', () => {
    it('should update model joint angles on valid joint_state message', () => {
      const positions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
      const message: JointStateMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow', 'Wrist_Pitch', 'Wrist_Roll', 'Gripper'],
          positions,
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(mockModel.updateJointAngles).toHaveBeenCalledWith(positions);
    });

    it('should ignore joint_state messages with fewer than 6 positions', () => {
      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow'],
          positions: [0.1, 0.2, 0.3],
          velocities: [0, 0, 0],
          efforts: [0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(mockModel.updateJointAngles).not.toHaveBeenCalled();
    });

    it('should ignore joint_state messages with more than 6 positions', () => {
      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
          positions: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
          velocities: [0, 0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(mockModel.updateJointAngles).not.toHaveBeenCalled();
    });

    it('should ignore joint_state messages with NaN positions', () => {
      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b', 'c', 'd', 'e', 'f'],
          positions: [0.1, NaN, 0.3, 0.4, 0.5, 0.6],
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(mockModel.updateJointAngles).not.toHaveBeenCalled();
    });

    it('should ignore joint_state messages with Infinity positions', () => {
      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b', 'c', 'd', 'e', 'f'],
          positions: [0.1, 0.2, Infinity, 0.4, 0.5, 0.6],
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(mockModel.updateJointAngles).not.toHaveBeenCalled();
    });

    it('should ignore non-joint_state messages', () => {
      const errorMessage: ServerMessage = {
        type: 'error',
        code: 'VALIDATION_ERROR',
        message: 'some error',
      };

      mockCM._emit('message', errorMessage);

      expect(mockModel.updateJointAngles).not.toHaveBeenCalled();
    });

    it('should store last valid positions', () => {
      const positions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
      const message: JointStateMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow', 'Wrist_Pitch', 'Wrist_Roll', 'Gripper'],
          positions,
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };

      mockCM._emit('message', message);

      expect(viewer.lastPositions).toEqual(positions);
    });

    it('should retain last valid pose when invalid message is received', () => {
      // First, send a valid message
      const validPositions = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
      const validMessage: JointStateMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b', 'c', 'd', 'e', 'f'],
          positions: validPositions,
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };
      mockCM._emit('message', validMessage);

      // Then send an invalid message (wrong number of positions)
      const invalidMessage: ServerMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b'],
          positions: [0.1, 0.2],
          velocities: [0, 0],
          efforts: [0, 0],
        },
      };
      mockCM._emit('message', invalidMessage);

      // Last valid positions should still be the first valid message
      expect(viewer.lastPositions).toEqual(validPositions);
      // Model should have only been called once (with valid message)
      expect(mockModel.updateJointAngles).toHaveBeenCalledTimes(1);
    });
  });

  describe('connection status tracking', () => {
    it('should start with disconnected status when CM is disconnected', () => {
      expect(viewer.connectionStatus).toBe('disconnected');
    });

    it('should report connected when state transitions to connected', () => {
      mockCM._emit('stateChange', 'connected');
      expect(viewer.connectionStatus).toBe('connected');
    });

    it('should report reconnecting when state transitions to reconnecting', () => {
      mockCM._emit('stateChange', 'reconnecting');
      expect(viewer.connectionStatus).toBe('reconnecting');
    });

    it('should report reconnecting when state is connecting', () => {
      mockCM._emit('stateChange', 'connecting');
      expect(viewer.connectionStatus).toBe('reconnecting');
    });

    it('should report disconnected when state transitions to disconnected', () => {
      mockCM._emit('stateChange', 'connected');
      mockCM._emit('stateChange', 'disconnected');
      expect(viewer.connectionStatus).toBe('disconnected');
    });

    it('should emit status change events to registered listeners', () => {
      const listener = vi.fn();
      viewer.onStatusChange(listener);

      mockCM._emit('stateChange', 'connected');

      expect(listener).toHaveBeenCalledWith('connected');
    });

    it('should not emit if status does not change', () => {
      const listener = vi.fn();
      viewer.onStatusChange(listener);

      // Already disconnected, emitting disconnected should not trigger listener
      mockCM._emit('stateChange', 'disconnected');

      expect(listener).not.toHaveBeenCalled();
    });

    it('should allow removing status change listeners', () => {
      const listener = vi.fn();
      viewer.onStatusChange(listener);
      viewer.offStatusChange(listener);

      mockCM._emit('stateChange', 'connected');

      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('connection loss — retain last valid pose', () => {
    it('should not reset model when connection is lost', () => {
      // Send valid state
      const positions = [0.5, -0.3, 0.1, 0.2, -0.1, 1.0];
      const message: JointStateMessage = {
        type: 'joint_state',
        timestamp: Date.now(),
        joints: {
          names: ['a', 'b', 'c', 'd', 'e', 'f'],
          positions,
          velocities: [0, 0, 0, 0, 0, 0],
          efforts: [0, 0, 0, 0, 0, 0],
        },
      };
      mockCM._emit('message', message);

      // Lose connection
      mockCM._emit('stateChange', 'reconnecting');

      // Model should not have been reset — updateJointAngles called only once
      expect(mockModel.updateJointAngles).toHaveBeenCalledTimes(1);
      expect(mockModel.resetToZero).not.toHaveBeenCalled();
      // Last valid positions still intact
      expect(viewer.lastPositions).toEqual(positions);
    });
  });

  describe('dispose', () => {
    it('should unsubscribe from ConnectionManager events', () => {
      viewer.dispose();

      expect(mockCM.off).toHaveBeenCalledWith('message', expect.any(Function));
      expect(mockCM.off).toHaveBeenCalledWith('stateChange', expect.any(Function));
    });

    it('should clear status listeners on dispose', () => {
      const listener = vi.fn();
      viewer.onStatusChange(listener);

      viewer.dispose();

      // Even if state changes after dispose, listener shouldn't be called
      // (because we've unsubscribed from CM, but also cleared our own listeners)
      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('initial state', () => {
    it('should start with null lastPositions before any message', () => {
      expect(viewer.lastPositions).toBeNull();
    });

    it('should initialize status from current CM state', () => {
      // Create a new viewer where CM is already connected
      const connectedCM = createMockConnectionManager();
      connectedCM.getState.mockReturnValue('connected');
      const model = createMockRobotModel();

      const connectedViewer = new RobotViewer(connectedCM as any, model as any);
      expect(connectedViewer.connectionStatus).toBe('connected');
    });
  });
});
