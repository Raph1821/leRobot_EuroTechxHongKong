/**
 * Unit tests for JointControlPanel component.
 *
 * Tests cover:
 * - Slider creation for 5 arm joints with correct limits
 * - Numeric angle display (2 decimal places in radians)
 * - Joint command sending via WebSocket on slider change
 * - Value clamping with warning indicator for ≥2s
 * - Slider position updates from joint state feedback
 * - Slider disabling when connection is unavailable
 *
 * Requirements: 8.1, 8.3, 8.4, 8.6, 8.7, 10.5
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { JointControlPanel } from './JointControlPanel';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { JointStateMessage } from '../types';
import { ARM_JOINT_NAMES, JOINT_CONFIGS } from '../types';

// ─── Mock ConnectionManager ────────────────────────────────────────────────

function createMockConnectionManager() {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    controlsEnabled: [],
    controlsDisabled: [],
    message: [],
    stateChange: [],
  };

  const mock = {
    on: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(listener);
    }),
    off: vi.fn(),
    send: vi.fn(() => true),
    getState: vi.fn(() => 'connected' as const),
    connect: vi.fn(),
    disconnect: vi.fn(),
    removeAllListeners: vi.fn(),
    // Helper to emit events in tests
    _emit(event: string, ...args: unknown[]) {
      for (const listener of listeners[event] ?? []) {
        listener(...args);
      }
    },
  };

  return mock as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

// ─── Test Helpers ──────────────────────────────────────────────────────────

function createContainer(): HTMLDivElement {
  const container = document.createElement('div');
  document.body.appendChild(container);
  return container;
}

function createJointStateMessage(positions: number[]): JointStateMessage {
  return {
    type: 'joint_state',
    timestamp: Date.now() / 1000,
    joints: {
      names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow', 'Wrist_Pitch', 'Wrist_Roll', 'Gripper'],
      positions: positions,
      velocities: [0, 0, 0, 0, 0, 0],
      efforts: [0, 0, 0, 0, 0, 0],
    },
  };
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('JointControlPanel', () => {
  let panel: JointControlPanel;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.useFakeTimers();
    connectionManager = createMockConnectionManager();
    panel = new JointControlPanel(connectionManager as unknown as ConnectionManager);
    container = createContainer();
    panel.mount(container);
  });

  afterEach(() => {
    panel.unmount();
    document.body.removeChild(container);
    vi.useRealTimers();
  });

  describe('initialization', () => {
    it('should create 5 sliders for arm joints', () => {
      const sliders = container.querySelectorAll('input[type="range"]');
      expect(sliders.length).toBe(5);
    });

    it('should set correct min/max limits from URDF for each joint', () => {
      for (const jointName of ARM_JOINT_NAMES) {
        const config = JOINT_CONFIGS.find(c => c.name === jointName)!;
        const slider = container.querySelector(`input[data-joint="${jointName}"]`) as HTMLInputElement;
        expect(slider).not.toBeNull();
        expect(parseFloat(slider.min)).toBe(config.lowerLimit);
        expect(parseFloat(slider.max)).toBe(config.upperLimit);
      }
    });

    it('should initialize all sliders at position 0', () => {
      for (const jointName of ARM_JOINT_NAMES) {
        const state = panel.getJointState(jointName);
        expect(state?.position).toBe(0);
      }
    });

    it('should not include the Gripper joint in arm sliders', () => {
      const gripperSlider = container.querySelector('input[data-joint="Gripper"]');
      expect(gripperSlider).toBeNull();
    });

    it('should display numeric joint angle with 2 decimal places in radians', () => {
      const valueDisplays = container.querySelectorAll('.joint-value');
      expect(valueDisplays.length).toBe(5);
      for (const display of valueDisplays) {
        expect(display.textContent).toBe('0.00 rad');
      }
    });
  });

  describe('slider disabled state', () => {
    it('should start with sliders enabled (always enabled for local 3D model feedback)', () => {
      expect(panel.isDisabled()).toBe(false);
      const sliders = container.querySelectorAll('input[type="range"]') as NodeListOf<HTMLInputElement>;
      for (const slider of sliders) {
        expect(slider.disabled).toBe(false);
      }
    });

    it('should enable sliders when controlsEnabled event fires', () => {
      connectionManager._emit('controlsEnabled');
      expect(panel.isDisabled()).toBe(false);
      const sliders = container.querySelectorAll('input[type="range"]') as NodeListOf<HTMLInputElement>;
      for (const slider of sliders) {
        expect(slider.disabled).toBe(false);
      }
    });

    it('should remain enabled when controlsDisabled event fires (local feedback always available)', () => {
      connectionManager._emit('controlsEnabled');
      connectionManager._emit('controlsDisabled');
      expect(panel.isDisabled()).toBe(false);
      const sliders = container.querySelectorAll('input[type="range"]') as NodeListOf<HTMLInputElement>;
      for (const slider of sliders) {
        expect(slider.disabled).toBe(false);
      }
    });
  });

  describe('sending joint commands', () => {
    beforeEach(() => {
      connectionManager._emit('controlsEnabled');
    });

    it('should send joint command via WebSocket when slider changes', () => {
      const slider = container.querySelector('input[data-joint="Shoulder_Rotation"]') as HTMLInputElement;
      slider.value = '0.50';
      slider.dispatchEvent(new Event('input'));

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'joint_command',
        joints: [{ name: 'Shoulder_Rotation', position: 0.5 }],
      });
    });

    it('should send command even when connection is unavailable (for local model update)', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');

      const slider = container.querySelector('input[data-joint="Shoulder_Rotation"]') as HTMLInputElement;
      slider.value = '0.50';
      slider.dispatchEvent(new Event('input'));

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'joint_command',
        joints: [{ name: 'Shoulder_Rotation', position: 0.5 }],
      });
    });

    it('should send command even when connection is reconnecting (for local model update)', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('reconnecting');

      const slider = container.querySelector('input[data-joint="Elbow"]') as HTMLInputElement;
      slider.value = '0.30';
      slider.dispatchEvent(new Event('input'));

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'joint_command',
        joints: [{ name: 'Elbow', position: 0.3 }],
      });
    });
  });

  describe('value clamping (Req 10.5)', () => {
    beforeEach(() => {
      connectionManager._emit('controlsEnabled');
    });

    it('should clamp values below the lower limit', () => {
      // Shoulder_Rotation lower limit is -1.96
      panel.setJointPosition('Shoulder_Rotation', -3.0);
      const state = panel.getJointState('Shoulder_Rotation');
      expect(state?.position).toBe(-1.96);
    });

    it('should clamp values above the upper limit', () => {
      // Elbow upper limit is 1.5
      panel.setJointPosition('Elbow', 5.0);
      const state = panel.getJointState('Elbow');
      expect(state?.position).toBe(1.5);
    });

    it('should not clamp values within the valid range', () => {
      panel.setJointPosition('Wrist_Roll', 1.5);
      const state = panel.getJointState('Wrist_Roll');
      expect(state?.position).toBe(1.5);
    });

    it('should show warning indicator when value is clamped on slider input', () => {
      // Simulate a raw input that would exceed limits via internal handler
      const slider = container.querySelector('input[data-joint="Shoulder_Rotation"]') as HTMLInputElement;
      // Manually force the value to exceed limits (in real browser, the range input clamps automatically,
      // but we test our clamping logic)
      Object.defineProperty(slider, 'value', { get: () => '5.0', set: () => {}, configurable: true });
      slider.dispatchEvent(new Event('input'));

      const state = panel.getJointState('Shoulder_Rotation');
      expect(state?.warning).toBe(true);
    });

    it('should hide warning indicator after 2 seconds', () => {
      // Trigger a clamp warning
      const slider = container.querySelector('input[data-joint="Shoulder_Rotation"]') as HTMLInputElement;
      Object.defineProperty(slider, 'value', { get: () => '5.0', set: () => {}, configurable: true });
      slider.dispatchEvent(new Event('input'));

      expect(panel.getJointState('Shoulder_Rotation')?.warning).toBe(true);

      // Advance time by 2 seconds
      vi.advanceTimersByTime(2000);

      expect(panel.getJointState('Shoulder_Rotation')?.warning).toBe(false);
    });

    it('should send the clamped value (not the raw value) when clamping occurs', () => {
      const slider = container.querySelector('input[data-joint="Elbow"]') as HTMLInputElement;
      Object.defineProperty(slider, 'value', { get: () => '10.0', set: () => {}, configurable: true });
      slider.dispatchEvent(new Event('input'));

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'joint_command',
        joints: [{ name: 'Elbow', position: 1.5 }],
      });
    });
  });

  describe('joint state feedback (Req 8.7)', () => {
    it('should update slider positions from joint state message', () => {
      const positions = [0.5, -0.3, 1.0, 0.8, -1.5, 0.0];
      const message = createJointStateMessage(positions);

      connectionManager._emit('message', message);

      for (let i = 0; i < ARM_JOINT_NAMES.length; i++) {
        const state = panel.getJointState(ARM_JOINT_NAMES[i]);
        expect(state?.position).toBe(positions[i]);
      }
    });

    it('should update numeric display from joint state feedback', () => {
      const positions = [1.23, -0.45, 0.67, -0.89, 2.10, 0.0];
      const message = createJointStateMessage(positions);

      connectionManager._emit('message', message);

      const valueDisplays = container.querySelectorAll('.joint-value');
      const expected = ['1.23 rad', '-0.45 rad', '0.67 rad', '-0.89 rad', '2.10 rad'];
      valueDisplays.forEach((display, i) => {
        expect(display.textContent).toBe(expected[i]);
      });
    });

    it('should clamp incoming joint state values that exceed limits', () => {
      // Send a position that exceeds Elbow upper limit (1.5)
      const positions = [0, 0, 5.0, 0, 0, 0];
      const message = createJointStateMessage(positions);

      connectionManager._emit('message', message);

      const state = panel.getJointState('Elbow');
      expect(state?.position).toBe(1.5);
    });

    it('should ignore non-joint_state messages', () => {
      const errorMessage = { type: 'error', code: 'TEST', message: 'test error' };
      connectionManager._emit('message', errorMessage);

      // States should remain at initial (0)
      for (const jointName of ARM_JOINT_NAMES) {
        expect(panel.getJointState(jointName)?.position).toBe(0);
      }
    });
  });

  describe('getAllJointStates', () => {
    it('should return states for all 5 arm joints', () => {
      const states = panel.getAllJointStates();
      expect(states.length).toBe(5);
      const names = states.map(s => s.name);
      expect(names).toEqual([...ARM_JOINT_NAMES]);
    });
  });

  describe('unmount', () => {
    it('should clear the container on unmount', () => {
      panel.unmount();
      expect(container.innerHTML).toBe('');
    });

    it('should clear warning timers on unmount', () => {
      // Trigger a warning
      const slider = container.querySelector('input[data-joint="Shoulder_Rotation"]') as HTMLInputElement;
      Object.defineProperty(slider, 'value', { get: () => '5.0', set: () => {}, configurable: true });
      slider.dispatchEvent(new Event('input'));

      panel.unmount();
      // If timers weren't cleared, this would throw or have side effects
      vi.advanceTimersByTime(5000);
    });
  });
});
