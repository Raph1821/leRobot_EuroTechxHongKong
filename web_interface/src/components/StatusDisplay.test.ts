/**
 * Unit tests for StatusDisplay component.
 *
 * Tests cover:
 * - Connection indicator displays correct state and color
 * - Simulation status updates from sim_status messages within 1s
 * - Error notifications for trajectory failures and validation errors
 * - Notification dismissal and clearing
 *
 * Validates: Requirements 10.1, 10.6, 9.5
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StatusDisplay } from './StatusDisplay';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { ConnectionState, ServerMessage } from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

function createMockConnectionManager(initialState: ConnectionState = 'disconnected') {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    stateChange: [],
    message: [],
    controlsEnabled: [],
    controlsDisabled: [],
  };

  const mock = {
    getState: vi.fn(() => initialState),
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

  return mock as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('StatusDisplay', () => {
  let container: HTMLElement;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let statusDisplay: StatusDisplay;

  beforeEach(() => {
    container = document.createElement('div');
    connectionManager = createMockConnectionManager('disconnected');
    statusDisplay = new StatusDisplay(connectionManager);
    statusDisplay.mount(container);
  });

  describe('connection indicator', () => {
    it('displays red indicator when disconnected', () => {
      expect(statusDisplay.getConnectionState()).toBe('disconnected');
      expect(statusDisplay.getIndicatorColor()).toBe('red');

      const indicator = container.querySelector('.status-display__indicator');
      expect(indicator?.classList.contains('status-display__indicator--red')).toBe(true);
    });

    it('displays green indicator when connected', () => {
      connectionManager._emit('stateChange', 'connected');

      expect(statusDisplay.getConnectionState()).toBe('connected');
      expect(statusDisplay.getIndicatorColor()).toBe('green');

      const indicator = container.querySelector('.status-display__indicator');
      expect(indicator?.classList.contains('status-display__indicator--green')).toBe(true);
    });

    it('displays yellow indicator when reconnecting', () => {
      connectionManager._emit('stateChange', 'reconnecting');

      expect(statusDisplay.getConnectionState()).toBe('reconnecting');
      expect(statusDisplay.getIndicatorColor()).toBe('yellow');

      const indicator = container.querySelector('.status-display__indicator');
      expect(indicator?.classList.contains('status-display__indicator--yellow')).toBe(true);
    });

    it('displays yellow indicator when connecting', () => {
      connectionManager._emit('stateChange', 'connecting');

      expect(statusDisplay.getConnectionState()).toBe('connecting');
      expect(statusDisplay.getIndicatorColor()).toBe('yellow');
    });

    it('updates label text on state change', () => {
      connectionManager._emit('stateChange', 'connected');
      const label = container.querySelector('.status-display__connection-label');
      expect(label?.textContent).toBe('Connected');

      connectionManager._emit('stateChange', 'reconnecting');
      expect(label?.textContent).toBe('Reconnecting');

      connectionManager._emit('stateChange', 'disconnected');
      expect(label?.textContent).toBe('Disconnected');
    });
  });

  describe('simulation status', () => {
    it('shows unknown state initially', () => {
      expect(statusDisplay.getSimulationState()).toBe('unknown');
    });

    it('updates to running on sim_status message', () => {
      const message: ServerMessage = { type: 'sim_status', state: 'running' };
      connectionManager._emit('message', message);

      expect(statusDisplay.getSimulationState()).toBe('running');
      const simState = container.querySelector('.status-display__sim-state');
      expect(simState?.textContent).toBe('Running');
    });

    it('updates to paused on sim_status message', () => {
      const message: ServerMessage = { type: 'sim_status', state: 'paused' };
      connectionManager._emit('message', message);

      expect(statusDisplay.getSimulationState()).toBe('paused');
      const simState = container.querySelector('.status-display__sim-state');
      expect(simState?.textContent).toBe('Paused');
    });

    it('updates to disconnected on sim_status message', () => {
      const message: ServerMessage = { type: 'sim_status', state: 'disconnected' };
      connectionManager._emit('message', message);

      expect(statusDisplay.getSimulationState()).toBe('disconnected');
      const simState = container.querySelector('.status-display__sim-state');
      expect(simState?.textContent).toBe('Disconnected');
    });

    it('does not change sim state on non-sim messages', () => {
      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: 123,
        joints: { names: [], positions: [], velocities: [], efforts: [] },
      };
      connectionManager._emit('message', message);

      expect(statusDisplay.getSimulationState()).toBe('unknown');
    });
  });

  describe('error notifications', () => {
    it('shows notification on trajectory failure (aborted)', () => {
      const message: ServerMessage = {
        type: 'trajectory_status',
        status: 'aborted',
        message: 'Joint limit exceeded',
      };
      connectionManager._emit('message', message);

      const notifications = statusDisplay.getNotifications();
      expect(notifications).toHaveLength(1);
      expect(notifications[0].message).toContain('aborted');
      expect(notifications[0].message).toContain('Joint limit exceeded');
    });

    it('shows notification on trajectory preemption', () => {
      const message: ServerMessage = {
        type: 'trajectory_status',
        status: 'preempted',
        message: 'New goal received',
      };
      connectionManager._emit('message', message);

      const notifications = statusDisplay.getNotifications();
      expect(notifications).toHaveLength(1);
      expect(notifications[0].message).toContain('preempted');
    });

    it('does not show notification for successful trajectory', () => {
      const message: ServerMessage = {
        type: 'trajectory_status',
        status: 'succeeded',
        message: 'Goal reached',
      };
      connectionManager._emit('message', message);

      expect(statusDisplay.getNotifications()).toHaveLength(0);
    });

    it('does not show notification for executing trajectory', () => {
      const message: ServerMessage = {
        type: 'trajectory_status',
        status: 'executing',
        message: 'In progress',
      };
      connectionManager._emit('message', message);

      expect(statusDisplay.getNotifications()).toHaveLength(0);
    });

    it('shows notification on error message', () => {
      const message: ServerMessage = {
        type: 'error',
        code: 'VALIDATION_ERROR',
        message: 'Joint position exceeds limit',
      };
      connectionManager._emit('message', message);

      const notifications = statusDisplay.getNotifications();
      expect(notifications).toHaveLength(1);
      expect(notifications[0].message).toContain('VALIDATION_ERROR');
      expect(notifications[0].message).toContain('Joint position exceeds limit');
    });

    it('renders notification elements in the DOM', () => {
      statusDisplay.addNotification('Test error');

      const notifElements = container.querySelectorAll('.status-display__notification');
      expect(notifElements).toHaveLength(1);
      expect(notifElements[0].querySelector('.status-display__notification-message')?.textContent)
        .toBe('Test error');
    });

    it('allows dismissing a notification', () => {
      statusDisplay.addNotification('Error 1');
      statusDisplay.addNotification('Error 2');

      const notifications = statusDisplay.getNotifications();
      expect(notifications).toHaveLength(2);

      statusDisplay.dismissNotification(notifications[0].id);

      expect(statusDisplay.getNotifications()).toHaveLength(1);
      expect(statusDisplay.getNotifications()[0].message).toBe('Error 2');
    });

    it('allows clearing all notifications', () => {
      statusDisplay.addNotification('Error 1');
      statusDisplay.addNotification('Error 2');
      statusDisplay.addNotification('Error 3');

      statusDisplay.clearNotifications();

      expect(statusDisplay.getNotifications()).toHaveLength(0);
      const notifElements = container.querySelectorAll('.status-display__notification');
      expect(notifElements).toHaveLength(0);
    });

    it('renders dismiss button with accessible label', () => {
      statusDisplay.addNotification('Test error');

      const dismissBtn = container.querySelector('.status-display__notification-dismiss');
      expect(dismissBtn).not.toBeNull();
      expect(dismissBtn?.getAttribute('aria-label')).toBe('Dismiss notification');
    });

    it('dismiss button removes the notification', () => {
      statusDisplay.addNotification('Test error');

      const dismissBtn = container.querySelector('.status-display__notification-dismiss') as HTMLButtonElement;
      dismissBtn.click();

      expect(statusDisplay.getNotifications()).toHaveLength(0);
      expect(container.querySelectorAll('.status-display__notification')).toHaveLength(0);
    });
  });

  describe('mount and unmount', () => {
    it('adds status-display class and role on mount', () => {
      expect(container.classList.contains('status-display')).toBe(true);
      expect(container.getAttribute('role')).toBe('status');
      expect(container.getAttribute('aria-live')).toBe('polite');
    });

    it('cleans up on unmount', () => {
      statusDisplay.unmount();

      expect(container.innerHTML).toBe('');
      expect(container.classList.contains('status-display')).toBe(false);
    });

    it('stops responding to state changes after unmount', () => {
      statusDisplay.unmount();

      // This should not throw
      connectionManager._emit('stateChange', 'connected');
      expect(statusDisplay.getConnectionState()).toBe('disconnected');
    });
  });

  describe('accessibility', () => {
    it('notification area has alert role and aria-live assertive', () => {
      const notifArea = container.querySelector('.status-display__notifications');
      expect(notifArea?.getAttribute('role')).toBe('alert');
      expect(notifArea?.getAttribute('aria-live')).toBe('assertive');
    });
  });
});
