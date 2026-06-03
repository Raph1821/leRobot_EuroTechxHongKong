/**
 * Unit tests for GripperControl component.
 *
 * Validates: Requirements 8.2
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GripperControl, GRIPPER_MIN, GRIPPER_MAX } from './GripperControl';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { JointStateMessage } from '../types';

// ─── Mock ConnectionManager ────────────────────────────────────────────────

function createMockConnectionManager(): ConnectionManager {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    controlsEnabled: [],
    controlsDisabled: [],
    message: [],
    stateChange: [],
  };

  return {
    send: vi.fn().mockReturnValue(true),
    getState: vi.fn().mockReturnValue('connected'),
    on: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(listener);
    }),
    off: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      if (listeners[event]) {
        const idx = listeners[event].indexOf(listener);
        if (idx !== -1) listeners[event].splice(idx, 1);
      }
    }),
    removeAllListeners: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    // Helper for tests to emit events
    _emit: (event: string, ...args: unknown[]) => {
      (listeners[event] || []).forEach((fn) => fn(...args));
    },
  } as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

function createJointStateMessage(gripperPosition: number): JointStateMessage {
  return {
    type: 'joint_state',
    timestamp: Date.now() / 1000,
    joints: {
      names: ['Shoulder_Rotation', 'Shoulder_Pitch', 'Elbow', 'Wrist_Pitch', 'Wrist_Roll', 'Gripper'],
      positions: [0, 0, 0, 0, 0, gripperPosition],
      velocities: [0, 0, 0, 0, 0, 0],
      efforts: [0, 0, 0, 0, 0, 0],
    },
  };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('GripperControl', () => {
  let mockCM: ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
  let container: HTMLElement;

  beforeEach(() => {
    // Create a simple DOM container
    container = document.createElement('div');
    mockCM = createMockConnectionManager() as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
  });

  describe('initialization', () => {
    it('should create the component with correct structure', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });

      const root = control.getElement();
      expect(root).toBeDefined();
      expect(root.className).toBe('gripper-control');

      // Should have a slider
      const slider = root.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider).not.toBeNull();
      expect(slider.min).toBe(String(GRIPPER_MIN));
      expect(slider.max).toBe(String(GRIPPER_MAX));

      control.dispose();
    });

    it('should initialize with position 0', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      expect(control.getPosition()).toBe(0);
      control.dispose();
    });

    it('should start with controls disabled', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      expect(control.isEnabled()).toBe(false);

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider.disabled).toBe(true);

      control.dispose();
    });

    it('should have Open and Close buttons', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      const root = control.getElement();

      const openBtn = root.querySelector('.gripper-control__btn--open') as HTMLButtonElement;
      const closeBtn = root.querySelector('.gripper-control__btn--close') as HTMLButtonElement;

      expect(openBtn).not.toBeNull();
      expect(openBtn.textContent).toBe('Open');
      expect(closeBtn).not.toBeNull();
      expect(closeBtn.textContent).toBe('Close');

      control.dispose();
    });

    it('should display value with 2 decimal places', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      const valueEl = control.getElement().querySelector('.gripper-control__value');
      expect(valueEl?.textContent).toBe('0.00 rad');
      control.dispose();
    });
  });

  describe('slider interaction', () => {
    it('should send gripper_command when slider changes', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      slider.value = '0.75';
      slider.dispatchEvent(new Event('input'));

      expect(mockCM.send).toHaveBeenCalledWith({
        type: 'gripper_command',
        position: 0.75,
      });

      control.dispose();
    });

    it('should clamp position to GRIPPER_MIN', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      slider.value = String(GRIPPER_MIN - 1);
      slider.dispatchEvent(new Event('input'));

      expect(control.getPosition()).toBe(GRIPPER_MIN);

      control.dispose();
    });

    it('should clamp position to GRIPPER_MAX', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      slider.value = String(GRIPPER_MAX + 1);
      slider.dispatchEvent(new Event('input'));

      expect(control.getPosition()).toBe(GRIPPER_MAX);

      control.dispose();
    });

    it('should not send commands when disabled', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      // Controls start disabled

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      slider.value = '0.5';
      slider.dispatchEvent(new Event('input'));

      expect(mockCM.send).not.toHaveBeenCalled();

      control.dispose();
    });
  });

  describe('buttons', () => {
    it('should send GRIPPER_MAX on Open click', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      const openBtn = control.getElement().querySelector('.gripper-control__btn--open') as HTMLButtonElement;
      openBtn.click();

      expect(mockCM.send).toHaveBeenCalledWith({
        type: 'gripper_command',
        position: GRIPPER_MAX,
      });
      expect(control.getPosition()).toBe(GRIPPER_MAX);

      control.dispose();
    });

    it('should send GRIPPER_MIN on Close click', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      const closeBtn = control.getElement().querySelector('.gripper-control__btn--close') as HTMLButtonElement;
      closeBtn.click();

      expect(mockCM.send).toHaveBeenCalledWith({
        type: 'gripper_command',
        position: GRIPPER_MIN,
      });
      expect(control.getPosition()).toBe(GRIPPER_MIN);

      control.dispose();
    });

    it('should not send commands from buttons when disabled', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      // Controls start disabled

      const openBtn = control.getElement().querySelector('.gripper-control__btn--open') as HTMLButtonElement;
      openBtn.click();

      expect(mockCM.send).not.toHaveBeenCalled();

      control.dispose();
    });
  });

  describe('joint state feedback', () => {
    it('should update position from joint state message', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });

      const msg = createJointStateMessage(1.23);
      control.updateFromJointState(msg);

      expect(control.getPosition()).toBe(1.23);

      const valueEl = control.getElement().querySelector('.gripper-control__value');
      expect(valueEl?.textContent).toBe('1.23 rad');

      control.dispose();
    });

    it('should update slider value from joint state', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });

      const msg = createJointStateMessage(0.5);
      control.updateFromJointState(msg);

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider.value).toBe('0.5');

      control.dispose();
    });

    it('should ignore joint state without Gripper', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });

      const msg: JointStateMessage = {
        type: 'joint_state',
        timestamp: Date.now() / 1000,
        joints: {
          names: ['Shoulder_Rotation', 'Shoulder_Pitch'],
          positions: [0.5, 0.3],
          velocities: [0, 0],
          efforts: [0, 0],
        },
      };
      control.updateFromJointState(msg);

      // Position should remain unchanged
      expect(control.getPosition()).toBe(0);

      control.dispose();
    });

    it('should respond to joint_state messages from ConnectionManager', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });

      const msg = createJointStateMessage(0.88);
      mockCM._emit('message', msg);

      expect(control.getPosition()).toBe(0.88);

      control.dispose();
    });
  });

  describe('enable/disable', () => {
    it('should enable controls on controlsEnabled event', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      expect(control.isEnabled()).toBe(false);

      mockCM._emit('controlsEnabled');

      expect(control.isEnabled()).toBe(true);

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider.disabled).toBe(false);

      control.dispose();
    });

    it('should disable controls on controlsDisabled event', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();

      mockCM._emit('controlsDisabled');

      expect(control.isEnabled()).toBe(false);

      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider.disabled).toBe(true);

      control.dispose();
    });

    it('should disable all buttons when connection lost', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.enable();
      mockCM._emit('controlsDisabled');

      const openBtn = control.getElement().querySelector('.gripper-control__btn--open') as HTMLButtonElement;
      const closeBtn = control.getElement().querySelector('.gripper-control__btn--close') as HTMLButtonElement;

      expect(openBtn.disabled).toBe(true);
      expect(closeBtn.disabled).toBe(true);

      control.dispose();
    });
  });

  describe('accessibility', () => {
    it('should have proper ARIA attributes on slider', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      const slider = control.getElement().querySelector('input[type="range"]') as HTMLInputElement;

      expect(slider.getAttribute('aria-label')).toBe('Gripper position');
      expect(slider.getAttribute('aria-valuemin')).toBe(String(GRIPPER_MIN));
      expect(slider.getAttribute('aria-valuemax')).toBe(String(GRIPPER_MAX));

      control.dispose();
    });

    it('should have role group on root element', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      const root = control.getElement();
      expect(root.getAttribute('role')).toBe('group');
      expect(root.getAttribute('aria-label')).toBe('Gripper Control');
      control.dispose();
    });
  });

  describe('dispose', () => {
    it('should clean up event listeners on dispose', () => {
      const control = new GripperControl({ connectionManager: mockCM, container });
      control.dispose();

      // After dispose, ConnectionManager events should not trigger updates
      expect(mockCM.off).toHaveBeenCalled();
    });
  });
});
