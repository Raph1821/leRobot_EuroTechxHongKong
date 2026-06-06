/**
 * Unit tests for TeleopPanel component.
 *
 * Tests cover:
 * - Teleop mode toggle (must be explicitly activated) (Req 5.4)
 * - Velocity scale slider (range 0.01 to 0.2, default 0.05) (Req 5.6)
 * - Active input device indicator (keyboard/gamepad) (Req 5.5)
 * - Key/button mapping overlay (Req 5.5)
 * - Unreachable motion indicator on IK failure (Req 5.9)
 * - Deactivate teleop + show warning on WebSocket loss (Req 5.8)
 *
 * Validates: Requirements 5.4, 5.5, 5.6, 5.8, 5.9
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  TeleopPanel,
  VELOCITY_SCALE_MIN,
  VELOCITY_SCALE_MAX,
  VELOCITY_SCALE_DEFAULT,
  KEYBOARD_MAPPING,
  GAMEPAD_MAPPING,
} from './TeleopPanel';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { ServerMessage } from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

function createMockConnectionManager() {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    stateChange: [],
    message: [],
    controlsEnabled: [],
    controlsDisabled: [],
  };

  const mock = {
    getState: vi.fn(() => 'connected' as const),
    on: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      listeners[event]?.push(listener);
    }),
    off: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      const list = listeners[event];
      if (list) {
        const idx = list.indexOf(listener);
        if (idx !== -1) list.splice(idx, 1);
      }
    }),
    send: vi.fn(() => true),
    connect: vi.fn(),
    disconnect: vi.fn(),
    removeAllListeners: vi.fn(),
    _emit(event: string, ...args: unknown[]) {
      for (const listener of listeners[event] ?? []) {
        listener(...args);
      }
    },
  };

  return mock as unknown as ConnectionManager & {
    _emit: (event: string, ...args: unknown[]) => void;
    send: ReturnType<typeof vi.fn>;
  };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('TeleopPanel', () => {
  let container: HTMLElement;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let panel: TeleopPanel;

  beforeEach(() => {
    container = document.createElement('div');
    connectionManager = createMockConnectionManager();
    panel = new TeleopPanel({ connectionManager });
    panel.mount(container);
  });

  describe('mount and unmount', () => {
    it('renders the teleop panel into the container', () => {
      const root = container.querySelector('.teleop-panel');
      expect(root).not.toBeNull();
      expect(root?.getAttribute('role')).toBe('region');
      expect(root?.getAttribute('aria-label')).toBe('Teleoperation Controls');
    });

    it('cleans up on unmount', () => {
      panel.unmount();
      expect(container.querySelector('.teleop-panel')).toBeNull();
    });

    it('stops responding to events after unmount', () => {
      panel.unmount();
      // Should not throw
      connectionManager._emit('stateChange', 'disconnected');
      expect(panel.isEnabled()).toBe(false);
    });
  });

  describe('teleop mode toggle (Req 5.4)', () => {
    it('starts with teleop mode disabled', () => {
      expect(panel.isEnabled()).toBe(false);
    });

    it('toggle button shows "Activate Teleop" when disabled', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      expect(btn.textContent).toBe('Activate Teleop');
      expect(btn.getAttribute('aria-pressed')).toBe('false');
    });

    it('enables teleop on toggle click', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click();

      expect(panel.isEnabled()).toBe(true);
      expect(btn.textContent).toBe('Deactivate Teleop');
      expect(btn.getAttribute('aria-pressed')).toBe('true');
    });

    it('disables teleop on second toggle click', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable
      btn.click(); // disable

      expect(panel.isEnabled()).toBe(false);
      expect(btn.textContent).toBe('Activate Teleop');
      expect(btn.getAttribute('aria-pressed')).toBe('false');
    });

    it('sends teleop_mode message on toggle', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click();

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'teleop_mode',
        enabled: true,
        velocity_scale: VELOCITY_SCALE_DEFAULT,
      });
    });
  });

  describe('velocity scale slider (Req 5.6)', () => {
    it('starts with default velocity scale of 0.05', () => {
      expect(panel.getVelocityScale()).toBe(VELOCITY_SCALE_DEFAULT);
    });

    it('slider has correct range attributes', () => {
      const slider = container.querySelector('.teleop-panel__velocity-slider') as HTMLInputElement;
      expect(slider.min).toBe(String(VELOCITY_SCALE_MIN));
      expect(slider.max).toBe(String(VELOCITY_SCALE_MAX));
      expect(slider.value).toBe(String(VELOCITY_SCALE_DEFAULT));
    });

    it('updates velocity scale on slider input', () => {
      const slider = container.querySelector('.teleop-panel__velocity-slider') as HTMLInputElement;
      slider.value = '0.1';
      slider.dispatchEvent(new Event('input'));

      expect(panel.getVelocityScale()).toBe(0.1);
    });

    it('displays velocity value with units', () => {
      const display = container.querySelector('.teleop-panel__velocity-value');
      expect(display?.textContent).toBe('0.05 m/s');
    });

    it('sends teleop_mode message with updated scale', () => {
      const slider = container.querySelector('.teleop-panel__velocity-slider') as HTMLInputElement;
      slider.value = '0.15';
      slider.dispatchEvent(new Event('input'));

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'teleop_mode',
        enabled: false,
        velocity_scale: 0.15,
      });
    });

    it('clamps velocity scale to min/max bounds', () => {
      const slider = container.querySelector('.teleop-panel__velocity-slider') as HTMLInputElement;

      // Below min
      slider.value = '0.001';
      slider.dispatchEvent(new Event('input'));
      expect(panel.getVelocityScale()).toBe(VELOCITY_SCALE_MIN);

      // Above max
      slider.value = '0.5';
      slider.dispatchEvent(new Event('input'));
      expect(panel.getVelocityScale()).toBe(VELOCITY_SCALE_MAX);
    });
  });

  describe('active input device indicator (Req 5.5)', () => {
    it('shows no active device initially', () => {
      expect(panel.getActiveDevice()).toBe('none');
      const indicator = container.querySelector('.teleop-panel__device-indicator');
      expect(indicator?.textContent).toContain('No active input device');
    });

    it('updates to keyboard when setActiveDevice called', () => {
      panel.setActiveDevice('keyboard');
      expect(panel.getActiveDevice()).toBe('keyboard');

      const indicator = container.querySelector('.teleop-panel__device-indicator');
      expect(indicator?.textContent).toContain('Keyboard active');
    });

    it('updates to gamepad when setActiveDevice called', () => {
      panel.setActiveDevice('gamepad');
      expect(panel.getActiveDevice()).toBe('gamepad');

      const indicator = container.querySelector('.teleop-panel__device-indicator');
      expect(indicator?.textContent).toContain('Gamepad active');
    });
  });

  describe('key/button mapping overlay (Req 5.5)', () => {
    it('renders keyboard mapping section', () => {
      const overlay = container.querySelector('.teleop-panel__mapping-overlay');
      expect(overlay).not.toBeNull();

      const sections = overlay?.querySelectorAll('.teleop-panel__mapping-section');
      expect(sections?.length).toBe(2); // keyboard + gamepad

      const kbTitle = sections?.[0]?.querySelector('h4');
      expect(kbTitle?.textContent).toBe('Keyboard');
    });

    it('renders gamepad mapping section', () => {
      const overlay = container.querySelector('.teleop-panel__mapping-overlay');
      const sections = overlay?.querySelectorAll('.teleop-panel__mapping-section');

      const gpTitle = sections?.[1]?.querySelector('h4');
      expect(gpTitle?.textContent).toBe('Gamepad');
    });

    it('includes all keyboard mappings', () => {
      const overlay = container.querySelector('.teleop-panel__mapping-overlay');
      const dtElements = overlay?.querySelectorAll('.teleop-panel__mapping-section:first-child dt');

      expect(dtElements?.length).toBe(KEYBOARD_MAPPING.length);
    });

    it('includes all gamepad mappings', () => {
      const overlay = container.querySelector('.teleop-panel__mapping-overlay');
      const dtElements = overlay?.querySelectorAll('.teleop-panel__mapping-section:last-child dt');

      expect(dtElements?.length).toBe(GAMEPAD_MAPPING.length);
    });
  });

  describe('unreachable motion indicator (Req 5.9)', () => {
    it('is hidden initially', () => {
      expect(panel.isUnreachableVisible()).toBe(false);
      const indicator = container.querySelector('.teleop-panel__unreachable');
      expect(indicator?.getAttribute('aria-hidden')).toBe('true');
    });

    it('shows on IK_NO_SOLUTION error when teleop is active', () => {
      // Enable teleop first
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click();

      const errorMsg: ServerMessage = {
        type: 'error',
        code: 'IK_NO_SOLUTION',
        message: 'Target pose is unreachable',
      };
      connectionManager._emit('message', errorMsg);

      expect(panel.isUnreachableVisible()).toBe(true);
      const indicator = container.querySelector('.teleop-panel__unreachable');
      expect(indicator?.classList.contains('teleop-panel__unreachable--visible')).toBe(true);
    });

    it('does not show on IK error when teleop is inactive', () => {
      const errorMsg: ServerMessage = {
        type: 'error',
        code: 'IK_NO_SOLUTION',
        message: 'Target pose is unreachable',
      };
      connectionManager._emit('message', errorMsg);

      expect(panel.isUnreachableVisible()).toBe(false);
    });

    it('can be manually hidden', () => {
      panel.showUnreachableIndicator();
      expect(panel.isUnreachableVisible()).toBe(true);

      panel.hideUnreachableIndicator();
      expect(panel.isUnreachableVisible()).toBe(false);
    });

    it('is hidden when teleop is deactivated', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable
      panel.showUnreachableIndicator();

      btn.click(); // disable
      expect(panel.isUnreachableVisible()).toBe(false);
    });
  });

  describe('WebSocket loss handling (Req 5.8)', () => {
    it('deactivates teleop on connection loss', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable
      expect(panel.isEnabled()).toBe(true);

      connectionManager._emit('stateChange', 'disconnected');

      expect(panel.isEnabled()).toBe(false);
    });

    it('deactivates teleop on reconnecting state', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable

      connectionManager._emit('stateChange', 'reconnecting');

      expect(panel.isEnabled()).toBe(false);
    });

    it('shows connection lost warning on disconnect', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable

      connectionManager._emit('stateChange', 'disconnected');

      expect(panel.isConnectionLostWarningVisible()).toBe(true);
      const warning = container.querySelector('.teleop-panel__warning');
      expect(warning?.classList.contains('teleop-panel__warning--visible')).toBe(true);
      expect(warning?.getAttribute('aria-hidden')).toBe('false');
    });

    it('hides connection lost warning on reconnect', () => {
      const btn = container.querySelector('.teleop-panel__toggle') as HTMLButtonElement;
      btn.click(); // enable
      connectionManager._emit('stateChange', 'disconnected');

      connectionManager._emit('stateChange', 'connected');

      expect(panel.isConnectionLostWarningVisible()).toBe(false);
      const warning = container.querySelector('.teleop-panel__warning');
      expect(warning?.classList.contains('teleop-panel__warning--visible')).toBe(false);
    });

    it('does not show warning if teleop was not active', () => {
      connectionManager._emit('stateChange', 'disconnected');

      expect(panel.isConnectionLostWarningVisible()).toBe(false);
    });
  });
});
