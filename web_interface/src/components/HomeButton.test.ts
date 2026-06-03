/**
 * Unit tests for HomeButton component.
 *
 * Tests cover:
 * - Home button sends all-zero joint command (Req 8.5)
 * - Command discarded with notification when disconnected (Req 8.6)
 * - Button disabled/enabled based on connection state
 * - Notification auto-hides after timeout
 *
 * Requirements: 8.5, 8.6
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { HomeButton } from './HomeButton';
import type { ConnectionManager } from '../services/ConnectionManager';
import { ARM_JOINT_NAMES } from '../types';

// ─── Mock ConnectionManager ────────────────────────────────────────────────

function createMockConnectionManager(initialState: string = 'connected') {
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
    getState: vi.fn(() => initialState as 'connected' | 'disconnected' | 'reconnecting' | 'connecting'),
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

// ─── Test Helpers ──────────────────────────────────────────────────────────

function createContainer(): HTMLDivElement {
  const container = document.createElement('div');
  document.body.appendChild(container);
  return container;
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('HomeButton', () => {
  let homeButton: HomeButton;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.useFakeTimers();
    connectionManager = createMockConnectionManager('connected');
    container = createContainer();
    homeButton = new HomeButton({
      connectionManager: connectionManager as unknown as ConnectionManager,
      container,
    });
  });

  afterEach(() => {
    homeButton.dispose();
    document.body.removeChild(container);
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('should render a button with "Home Position" text', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      expect(button).not.toBeNull();
      expect(button.textContent).toBe('Home Position');
    });

    it('should have an accessible label on the button', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      expect(button.getAttribute('aria-label')).toContain('home position');
    });

    it('should render a notification area that is initially hidden', () => {
      const notification = container.querySelector('.home-button__notification') as HTMLElement;
      expect(notification).not.toBeNull();
      expect(notification.style.display).toBe('none');
    });
  });

  describe('sending home command (Req 8.5)', () => {
    beforeEach(() => {
      homeButton.enable();
    });

    it('should send joint command with all 5 arm joints at 0.0 radians', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(connectionManager.send).toHaveBeenCalledTimes(1);
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'joint_command',
        joints: ARM_JOINT_NAMES.map((name) => ({ name, position: 0.0 })),
      });
    });

    it('should send exactly 5 joint positions in the command', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      const call = (connectionManager.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(call.joints).toHaveLength(5);
    });

    it('should include all arm joint names in the command', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      const call = (connectionManager.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
      const sentNames = call.joints.map((j: { name: string }) => j.name);
      expect(sentNames).toEqual([...ARM_JOINT_NAMES]);
    });

    it('should set all positions to exactly 0.0', () => {
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      const call = (connectionManager.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
      for (const joint of call.joints) {
        expect(joint.position).toBe(0.0);
      }
    });
  });

  describe('disconnected behavior (Req 8.6)', () => {
    it('should discard command when connection state is disconnected', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');
      homeButton.enable(); // Button might still be enabled briefly

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(connectionManager.send).not.toHaveBeenCalled();
    });

    it('should discard command when connection state is reconnecting', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('reconnecting');
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(connectionManager.send).not.toHaveBeenCalled();
    });

    it('should discard command when connection state is connecting', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('connecting');
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(connectionManager.send).not.toHaveBeenCalled();
    });

    it('should show notification when command is discarded due to disconnection', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(homeButton.isNotificationVisible()).toBe(true);
      const notification = container.querySelector('.home-button__notification') as HTMLElement;
      expect(notification.textContent).toContain('disconnected');
    });

    it('should show notification when send() returns false (connection lost during send)', () => {
      (connectionManager.send as ReturnType<typeof vi.fn>).mockReturnValue(false);
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(homeButton.isNotificationVisible()).toBe(true);
    });

    it('should auto-hide notification after 3 seconds', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(homeButton.isNotificationVisible()).toBe(true);

      vi.advanceTimersByTime(3000);

      expect(homeButton.isNotificationVisible()).toBe(false);
    });

    it('should not show notification when command is successfully sent', () => {
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      expect(homeButton.isNotificationVisible()).toBe(false);
    });
  });

  describe('enable/disable state', () => {
    it('should start disabled', () => {
      expect(homeButton.isEnabled()).toBe(false);
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      expect(button.disabled).toBe(true);
    });

    it('should enable when controlsEnabled event fires', () => {
      connectionManager._emit('controlsEnabled');

      expect(homeButton.isEnabled()).toBe(true);
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      expect(button.disabled).toBe(false);
    });

    it('should disable when controlsDisabled event fires', () => {
      connectionManager._emit('controlsEnabled');
      connectionManager._emit('controlsDisabled');

      expect(homeButton.isEnabled()).toBe(false);
      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      expect(button.disabled).toBe(true);
    });
  });

  describe('dispose', () => {
    it('should remove the root element from the container', () => {
      homeButton.dispose();
      const button = container.querySelector('.home-button__btn');
      expect(button).toBeNull();
    });

    it('should clear notification timer on dispose', () => {
      (connectionManager.getState as ReturnType<typeof vi.fn>).mockReturnValue('disconnected');
      homeButton.enable();

      const button = container.querySelector('.home-button__btn') as HTMLButtonElement;
      button.click();

      homeButton.dispose();
      // Advancing time should not throw
      vi.advanceTimersByTime(5000);
    });
  });
});
