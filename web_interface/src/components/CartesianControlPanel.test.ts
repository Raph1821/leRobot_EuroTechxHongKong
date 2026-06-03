/**
 * Unit tests for CartesianControlPanel component.
 *
 * Validates: Requirements 3.4, 3.5, 3.6, 3.8, 3.9
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CartesianControlPanel } from './CartesianControlPanel';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { EndEffectorPoseMessage } from '../types';
import type { SceneSetup } from './SceneSetup';
import type { TargetMarker } from './CartesianControlPanel';

// ─── Mock ConnectionManager ────────────────────────────────────────────────

function createMockConnectionManager(): ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void } {
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
    _emit: (event: string, ...args: unknown[]) => {
      (listeners[event] || []).forEach((fn) => fn(...args));
    },
  } as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

function createMockSceneSetup(): SceneSetup & { added: unknown[]; removed: unknown[] } {
  const added: unknown[] = [];
  const removed: unknown[] = [];
  return {
    add: vi.fn((obj: unknown) => { added.push(obj); }),
    remove: vi.fn((obj: unknown) => { removed.push(obj); }),
    added,
    removed,
  } as unknown as SceneSetup & { added: unknown[]; removed: unknown[] };
}

function createMockMarkerFactory(): { factory: () => TargetMarker; markers: TargetMarker[] } {
  const markers: TargetMarker[] = [];
  const factory = () => {
    const marker: TargetMarker = {
      setPosition: vi.fn(),
      getObject3D: vi.fn().mockReturnValue({}),
      dispose: vi.fn(),
    };
    markers.push(marker);
    return marker;
  };
  return { factory, markers };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('CartesianControlPanel', () => {
  let mockCM: ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
  let container: HTMLElement;

  beforeEach(() => {
    container = document.createElement('div');
    mockCM = createMockConnectionManager();
  });

  describe('initialization and mounting', () => {
    it('should mount with correct structure', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      expect(container.classList.contains('cartesian-control-panel')).toBe(true);
      expect(container.querySelector('h3')?.textContent).toBe('Cartesian Control');

      panel.unmount();
    });

    it('should create position inputs constrained to [-0.5, 0.5]', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      // First 3 are position (x, y, z)
      const posInputs = [inputs[0], inputs[1], inputs[2]];

      for (const input of posInputs) {
        expect(input.min).toBe('-0.5');
        expect(input.max).toBe('0.5');
        expect(input.step).toBe('0.001');
      }

      panel.unmount();
    });

    it('should create orientation inputs constrained to [-3.14, 3.14]', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      // Last 3 are orientation (roll, pitch, yaw)
      const oriInputs = [inputs[3], inputs[4], inputs[5]];

      for (const input of oriInputs) {
        expect(input.min).toBe('-3.14');
        expect(input.max).toBe('3.14');
        expect(input.step).toBe('0.01');
      }

      panel.unmount();
    });

    it('should have a "Move To" button', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      expect(button).not.toBeNull();
      expect(button.textContent).toBe('Move To');

      panel.unmount();
    });

    it('should have an error display area initially hidden', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const errorDisplay = container.querySelector('.cartesian-error-display') as HTMLElement;
      expect(errorDisplay).not.toBeNull();
      expect(errorDisplay.style.display).toBe('none');

      panel.unmount();
    });
  });

  describe('Move To button', () => {
    it('should send cartesian_goal message with position and orientation on click', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      // Set input values
      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      inputs[0].value = '0.1';  // x
      inputs[1].value = '0.2';  // y
      inputs[2].value = '0.3';  // z
      inputs[3].value = '0.5';  // roll
      inputs[4].value = '-0.5'; // pitch
      inputs[5].value = '1.0';  // yaw

      inputs[0].dispatchEvent(new Event('input'));

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      expect(mockCM.send).toHaveBeenCalledWith({
        type: 'cartesian_goal',
        position: [0.1, 0.2, 0.3],
        orientation: [0.5, -0.5, 1.0],
      });

      panel.unmount();
    });

    it('should not send when disabled', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);
      panel.setDisabled(true);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      expect(mockCM.send).not.toHaveBeenCalled();

      panel.unmount();
    });

    it('should not send while motion is in progress', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      // First click starts motion
      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();
      expect(mockCM.send).toHaveBeenCalledTimes(1);

      // Second click should be blocked
      button.click();
      expect(mockCM.send).toHaveBeenCalledTimes(1);

      panel.unmount();
    });

    it('should clamp position values to [-0.5, 0.5]', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      inputs[0].value = '0.9';  // exceeds max
      inputs[1].value = '-0.8'; // below min
      inputs[2].value = '0.3';  // valid

      inputs[0].dispatchEvent(new Event('input'));

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      expect(mockCM.send).toHaveBeenCalledWith({
        type: 'cartesian_goal',
        position: [0.5, -0.5, 0.3],
        orientation: [0, 0, 0],
      });

      panel.unmount();
    });
  });

  describe('FK display', () => {
    it('should display current position with 3 decimal places', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const poseMsg: EndEffectorPoseMessage = {
        type: 'end_effector_pose',
        position: [0.12345, -0.06789, 0.45012],
        orientation: [1.234, -0.567, 2.89],
      };

      mockCM._emit('message', poseMsg);

      const posDisplay = container.querySelector('.cartesian-current-position') as HTMLElement;
      expect(posDisplay.textContent).toBe('Position: x=0.123, y=-0.068, z=0.450 m');

      panel.unmount();
    });

    it('should display current orientation with 2 decimal places', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const poseMsg: EndEffectorPoseMessage = {
        type: 'end_effector_pose',
        position: [0.1, 0.2, 0.3],
        orientation: [1.2345, -0.5678, 2.8912],
      };

      mockCM._emit('message', poseMsg);

      const oriDisplay = container.querySelector('.cartesian-current-orientation') as HTMLElement;
      expect(oriDisplay.textContent).toBe('Orientation: roll=1.23, pitch=-0.57, yaw=2.89 rad');

      panel.unmount();
    });

    it('should update FK display when end_effector_pose message received', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const poseMsg: EndEffectorPoseMessage = {
        type: 'end_effector_pose',
        position: [0.1, 0.2, 0.3],
        orientation: [0.5, 0.6, 0.7],
      };

      mockCM._emit('message', poseMsg);

      const state = panel.getState();
      expect(state.currentPosition).toEqual([0.1, 0.2, 0.3]);
      expect(state.currentOrientation).toEqual([0.5, 0.6, 0.7]);

      panel.unmount();
    });
  });

  describe('error notifications', () => {
    it('should show error on IK_NO_SOLUTION', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      // Start a motion
      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      // Receive IK error
      mockCM._emit('message', {
        type: 'error',
        code: 'IK_NO_SOLUTION',
        message: 'Target pose is unreachable',
      });

      const errorDisplay = container.querySelector('.cartesian-error-display') as HTMLElement;
      expect(errorDisplay.style.display).toBe('block');
      expect(errorDisplay.textContent).toBe('Target pose is unreachable');

      panel.unmount();
    });

    it('should show error on IK_TIMEOUT', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      // Start a motion
      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      mockCM._emit('message', {
        type: 'error',
        code: 'IK_TIMEOUT',
        message: 'IK solver timed out after 5 seconds',
      });

      const errorDisplay = container.querySelector('.cartesian-error-display') as HTMLElement;
      expect(errorDisplay.style.display).toBe('block');
      expect(errorDisplay.textContent).toBe('IK solver timed out after 5 seconds');

      panel.unmount();
    });

    it('should clear motion-in-progress on IK error', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();
      expect(panel.isMotionInProgress()).toBe(true);

      mockCM._emit('message', {
        type: 'error',
        code: 'IK_NO_SOLUTION',
        message: 'Unreachable',
      });

      expect(panel.isMotionInProgress()).toBe(false);

      panel.unmount();
    });

    it('should not show error for non-IK error codes', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      mockCM._emit('message', {
        type: 'error',
        code: 'SOME_OTHER_ERROR',
        message: 'Something else failed',
      });

      const errorDisplay = container.querySelector('.cartesian-error-display') as HTMLElement;
      expect(errorDisplay.style.display).toBe('none');

      panel.unmount();
    });
  });

  describe('trajectory status handling', () => {
    it('should clear motion-in-progress on trajectory succeeded', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();
      expect(panel.isMotionInProgress()).toBe(true);

      mockCM._emit('message', {
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'Goal reached',
      });

      expect(panel.isMotionInProgress()).toBe(false);

      panel.unmount();
    });

    it('should clear motion-in-progress on trajectory aborted', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      mockCM._emit('message', {
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Motion aborted',
      });

      expect(panel.isMotionInProgress()).toBe(false);

      panel.unmount();
    });
  });

  describe('target marker', () => {
    it('should add marker when Move To is clicked', () => {
      const mockScene = createMockSceneSetup();
      const { factory, markers } = createMockMarkerFactory();
      const panel = new CartesianControlPanel(mockCM, mockScene, factory);
      panel.mount(container);

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      inputs[0].value = '0.1';
      inputs[1].value = '0.2';
      inputs[2].value = '0.3';
      inputs[0].dispatchEvent(new Event('input'));

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      expect(markers).toHaveLength(1);
      expect(markers[0].setPosition).toHaveBeenCalledWith(0.1, 0.2, 0.3);
      expect(mockScene.add).toHaveBeenCalled();

      panel.unmount();
    });

    it('should remove marker on motion complete', () => {
      const mockScene = createMockSceneSetup();
      const { factory, markers } = createMockMarkerFactory();
      const panel = new CartesianControlPanel(mockCM, mockScene, factory);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      expect(markers).toHaveLength(1);

      mockCM._emit('message', {
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'Done',
      });

      expect(markers[0].dispose).toHaveBeenCalled();
      expect(mockScene.remove).toHaveBeenCalled();

      panel.unmount();
    });

    it('should remove marker on IK failure', () => {
      const mockScene = createMockSceneSetup();
      const { factory, markers } = createMockMarkerFactory();
      const panel = new CartesianControlPanel(mockCM, mockScene, factory);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      mockCM._emit('message', {
        type: 'error',
        code: 'IK_NO_SOLUTION',
        message: 'Unreachable',
      });

      expect(markers[0].dispose).toHaveBeenCalled();
      expect(mockScene.remove).toHaveBeenCalled();

      panel.unmount();
    });
  });

  describe('disabled state', () => {
    it('should disable inputs on controlsDisabled event', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      mockCM._emit('controlsDisabled');

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      for (const input of inputs) {
        expect(input.disabled).toBe(true);
      }

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      expect(button.disabled).toBe(true);

      panel.unmount();
    });

    it('should re-enable inputs on controlsEnabled event', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      mockCM._emit('controlsDisabled');
      mockCM._emit('controlsEnabled');

      const inputs = container.querySelectorAll<HTMLInputElement>('.cartesian-input');
      for (const input of inputs) {
        expect(input.disabled).toBe(false);
      }

      panel.unmount();
    });

    it('should support programmatic setDisabled', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      panel.setDisabled(true);
      expect(panel.getState().disabled).toBe(true);

      panel.setDisabled(false);
      expect(panel.getState().disabled).toBe(false);

      panel.unmount();
    });
  });

  describe('unmount and cleanup', () => {
    it('should clear container on unmount', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);

      expect(container.children.length).toBeGreaterThan(0);

      panel.unmount();

      expect(container.children.length).toBe(0);
      expect(container.classList.contains('cartesian-control-panel')).toBe(false);
    });

    it('should unregister event listeners on unmount', () => {
      const panel = new CartesianControlPanel(mockCM);
      panel.mount(container);
      panel.unmount();

      expect(mockCM.off).toHaveBeenCalled();
    });

    it('should remove marker on unmount', () => {
      const mockScene = createMockSceneSetup();
      const { factory, markers } = createMockMarkerFactory();
      const panel = new CartesianControlPanel(mockCM, mockScene, factory);
      panel.mount(container);

      const button = container.querySelector('.cartesian-move-button') as HTMLButtonElement;
      button.click();

      panel.unmount();

      expect(markers[0].dispose).toHaveBeenCalled();

      panel.unmount();
    });
  });
});
