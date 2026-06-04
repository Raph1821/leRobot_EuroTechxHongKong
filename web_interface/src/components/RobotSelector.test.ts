/**
 * Unit tests for RobotSelector component.
 *
 * Tests cover:
 * - Robot list displayed on connection (Req 6.3)
 * - Active robot switch and command routing (Req 6.4)
 * - Per-robot status displayed (Req 6.6)
 * - Offline marking after 5s timeout (Req 6.7)
 * - Recovery notification restores online status (Req 6.9)
 * - Mount/unmount lifecycle
 *
 * Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.7, 6.9
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RobotSelector } from './RobotSelector';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { RobotListMessage, RobotStatusChangeMessage, NamespacedJointStateMessage } from '../types';

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

  return mock as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('RobotSelector', () => {
  let container: HTMLElement;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let selector: RobotSelector;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement('div');
    connectionManager = createMockConnectionManager();
    selector = new RobotSelector({
      connectionManager,
      offlineTimeoutMs: 5000,
      healthCheckIntervalMs: 1000,
    });
    selector.mount(container);
  });

  afterEach(() => {
    selector.unmount();
    vi.useRealTimers();
  });

  describe('robot list display (Req 6.3)', () => {
    it('displays robot list on robot_list message', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'offline' },
        ],
      };
      connectionManager._emit('message', message);

      const items = container.querySelectorAll('.robot-selector__item');
      expect(items).toHaveLength(2);
    });

    it('shows empty state when no robots available', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [],
      };
      connectionManager._emit('message', message);

      const emptyItem = container.querySelector('.robot-selector__empty');
      expect(emptyItem?.textContent).toBe('No robots available');
    });

    it('displays robot namespace IDs as labels', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', message);

      const names = container.querySelectorAll('.robot-selector__name');
      expect(names[0]?.textContent).toBe('/robot1');
      expect(names[1]?.textContent).toBe('/robot2');
    });

    it('auto-selects first online robot when no robot is selected', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'offline' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', message);

      expect(selector.getActiveRobotId()).toBe('/robot2');
    });

    it('auto-selects first robot if none are online', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'offline' },
          { robot_id: '/robot2', status: 'offline' },
        ],
      };
      connectionManager._emit('message', message);

      expect(selector.getActiveRobotId()).toBe('/robot1');
    });

    it('sends select_robot message on auto-select', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'select_robot',
        robot_id: '/robot1',
      });
    });
  });

  describe('robot selection (Req 6.4)', () => {
    beforeEach(() => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
          { robot_id: '/robot3', status: 'online' },
        ],
      };
      connectionManager._emit('message', message);
    });

    it('selects robot programmatically', () => {
      selector.selectRobot('/robot2');
      expect(selector.getActiveRobotId()).toBe('/robot2');
    });

    it('sends select_robot message to bridge on selection', () => {
      vi.mocked(connectionManager.send).mockClear();
      selector.selectRobot('/robot3');

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'select_robot',
        robot_id: '/robot3',
      });
    });

    it('invokes onRobotSelected callback on selection change', () => {
      const callback = vi.fn();
      selector.onRobotSelected = callback;

      selector.selectRobot('/robot2');

      expect(callback).toHaveBeenCalledWith('/robot2');
    });

    it('does not invoke callback when selecting the same robot', () => {
      const callback = vi.fn();
      selector.onRobotSelected = callback;

      // Already selected from auto-select on robot_list
      selector.selectRobot('/robot1');
      expect(callback).not.toHaveBeenCalled();
    });

    it('returns false when selecting unknown robot', () => {
      const result = selector.selectRobot('/unknown_robot');
      expect(result).toBe(false);
    });

    it('returns true on successful selection', () => {
      const result = selector.selectRobot('/robot2');
      expect(result).toBe(true);
    });

    it('highlights active robot in DOM', () => {
      selector.selectRobot('/robot2');

      const items = container.querySelectorAll('.robot-selector__item');
      expect(items[0]?.classList.contains('robot-selector__item--active')).toBe(false);
      expect(items[1]?.classList.contains('robot-selector__item--active')).toBe(true);
      expect(items[2]?.classList.contains('robot-selector__item--active')).toBe(false);
    });

    it('shows active indicator for selected robot', () => {
      selector.selectRobot('/robot2');

      const activeIndicators = container.querySelectorAll('.robot-selector__active-indicator');
      expect(activeIndicators).toHaveLength(1);
      // Should be in the second item
      const activeItem = container.querySelector('.robot-selector__item--active');
      expect(activeItem?.querySelector('.robot-selector__active-indicator')).not.toBeNull();
    });

    it('selects robot via click on list item', () => {
      const callback = vi.fn();
      selector.onRobotSelected = callback;

      const items = container.querySelectorAll('.robot-selector__item');
      (items[1] as HTMLElement).click();

      expect(selector.getActiveRobotId()).toBe('/robot2');
      expect(callback).toHaveBeenCalledWith('/robot2');
    });
  });

  describe('per-robot status display (Req 6.6)', () => {
    it('shows online status indicator for online robots', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      const statusDot = container.querySelector('.robot-selector__status--online');
      expect(statusDot).not.toBeNull();
    });

    it('shows offline status indicator for offline robots', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'offline' }],
      };
      connectionManager._emit('message', message);

      const statusDot = container.querySelector('.robot-selector__status--offline');
      expect(statusDot).not.toBeNull();
    });

    it('displays status text for each robot', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'offline' },
        ],
      };
      connectionManager._emit('message', message);

      const statusTexts = container.querySelectorAll('.robot-selector__status-text');
      expect(statusTexts[0]?.textContent).toBe('online');
      expect(statusTexts[1]?.textContent).toBe('offline');
    });

    it('adds offline CSS class for offline robots', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'offline' }],
      };
      connectionManager._emit('message', message);

      const item = container.querySelector('.robot-selector__item');
      expect(item?.classList.contains('robot-selector__item--offline')).toBe(true);
    });
  });

  describe('offline detection after 5s timeout (Req 6.7)', () => {
    it('marks robot offline after 5s without joint state', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      expect(selector.getRobot('/robot1')?.status).toBe('online');

      // Advance time past the 5s timeout
      vi.advanceTimersByTime(6000);

      expect(selector.getRobot('/robot1')?.status).toBe('offline');
    });

    it('does not mark robot offline if joint states are received', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      // Send joint state at 3s
      vi.advanceTimersByTime(3000);
      const jointState: NamespacedJointStateMessage = {
        type: 'joint_state',
        robot_id: '/robot1',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation'],
          positions: [0],
          velocities: [0],
          efforts: [0],
        },
      };
      connectionManager._emit('message', jointState);

      // Advance another 3s (total 6s from start, but only 3s since last joint state)
      vi.advanceTimersByTime(3000);

      expect(selector.getRobot('/robot1')?.status).toBe('online');
    });

    it('marks robot offline after 5s from last joint state', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      // Send joint state at 2s
      vi.advanceTimersByTime(2000);
      const jointState: NamespacedJointStateMessage = {
        type: 'joint_state',
        robot_id: '/robot1',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation'],
          positions: [0],
          velocities: [0],
          efforts: [0],
        },
      };
      connectionManager._emit('message', jointState);

      // Advance 6s from that joint state (total 8s from start)
      vi.advanceTimersByTime(6000);

      expect(selector.getRobot('/robot1')?.status).toBe('offline');
    });
  });

  describe('online status recovery (Req 6.9)', () => {
    it('restores online status when joint states resume', () => {
      const message: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message);

      // Let it go offline
      vi.advanceTimersByTime(6000);
      expect(selector.getRobot('/robot1')?.status).toBe('offline');

      // Receive joint state
      const jointState: NamespacedJointStateMessage = {
        type: 'joint_state',
        robot_id: '/robot1',
        timestamp: Date.now(),
        joints: {
          names: ['Shoulder_Rotation'],
          positions: [0.5],
          velocities: [0],
          efforts: [0],
        },
      };
      connectionManager._emit('message', jointState);

      expect(selector.getRobot('/robot1')?.status).toBe('online');
    });

    it('restores online status via robot_status_change message', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'offline' }],
      };
      connectionManager._emit('message', robotList);
      expect(selector.getRobot('/robot1')?.status).toBe('offline');

      const statusChange: RobotStatusChangeMessage = {
        type: 'robot_status_change',
        robot_id: '/robot1',
        status: 'online',
      };
      connectionManager._emit('message', statusChange);

      expect(selector.getRobot('/robot1')?.status).toBe('online');
    });
  });

  describe('robot_status_change handling', () => {
    it('updates robot status from robot_status_change message', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', robotList);

      const statusChange: RobotStatusChangeMessage = {
        type: 'robot_status_change',
        robot_id: '/robot2',
        status: 'offline',
      };
      connectionManager._emit('message', statusChange);

      expect(selector.getRobot('/robot2')?.status).toBe('offline');
    });

    it('ignores status change for unknown robot', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      const statusChange: RobotStatusChangeMessage = {
        type: 'robot_status_change',
        robot_id: '/unknown',
        status: 'offline',
      };
      connectionManager._emit('message', statusChange);

      // Should not crash, robot list unchanged
      expect(selector.getRobots()).toHaveLength(1);
    });
  });

  describe('connection loss handling', () => {
    it('marks all robots offline on connection loss', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', robotList);

      connectionManager._emit('controlsDisabled');

      expect(selector.getRobot('/robot1')?.status).toBe('offline');
      expect(selector.getRobot('/robot2')?.status).toBe('offline');
    });
  });

  describe('mount and unmount', () => {
    it('adds robot-selector class and role on mount', () => {
      expect(container.classList.contains('robot-selector')).toBe(true);
      expect(container.getAttribute('role')).toBe('group');
      expect(container.getAttribute('aria-label')).toBe('Robot Selector');
    });

    it('renders title element', () => {
      const title = container.querySelector('.robot-selector__title');
      expect(title?.textContent).toBe('Robots');
    });

    it('renders listbox element', () => {
      const list = container.querySelector('.robot-selector__list');
      expect(list?.getAttribute('role')).toBe('listbox');
    });

    it('cleans up on unmount', () => {
      selector.unmount();

      expect(container.innerHTML).toBe('');
      expect(container.classList.contains('robot-selector')).toBe(false);
    });

    it('stops health monitoring on unmount', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      selector.unmount();

      // Advancing time should not cause any changes
      vi.advanceTimersByTime(10000);

      // Robot status stays as it was (online) since health check stopped
      expect(selector.getRobot('/robot1')?.status).toBe('online');
    });

    it('stops responding to messages after unmount', () => {
      selector.unmount();

      // Emitting messages should not throw
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      expect(selector.getRobots()).toHaveLength(0);
    });
  });

  describe('accessibility', () => {
    it('list items have option role', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      const item = container.querySelector('.robot-selector__item');
      expect(item?.getAttribute('role')).toBe('option');
    });

    it('active item has aria-selected=true', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', robotList);

      const items = container.querySelectorAll('.robot-selector__item');
      expect(items[0]?.getAttribute('aria-selected')).toBe('true');
      expect(items[1]?.getAttribute('aria-selected')).toBe('false');
    });

    it('status dot has aria-label', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      const statusDot = container.querySelector('.robot-selector__status');
      expect(statusDot?.getAttribute('aria-label')).toBe('Status: online');
    });
  });

  describe('getRobots and getRobot', () => {
    it('returns empty array when no robots', () => {
      expect(selector.getRobots()).toHaveLength(0);
    });

    it('returns all robot entries after robot_list', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'offline' },
        ],
      };
      connectionManager._emit('message', robotList);

      const robots = selector.getRobots();
      expect(robots).toHaveLength(2);
      expect(robots[0].robot_id).toBe('/robot1');
      expect(robots[1].robot_id).toBe('/robot2');
    });

    it('returns undefined for unknown robot', () => {
      expect(selector.getRobot('/unknown')).toBeUndefined();
    });

    it('returns robot entry by ID', () => {
      const robotList: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', robotList);

      const robot = selector.getRobot('/robot1');
      expect(robot).toBeDefined();
      expect(robot?.robot_id).toBe('/robot1');
      expect(robot?.status).toBe('online');
    });
  });

  describe('robot list updates', () => {
    it('removes robots no longer in the list', () => {
      const message1: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', message1);
      expect(selector.getRobots()).toHaveLength(2);

      const message2: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message2);
      expect(selector.getRobots()).toHaveLength(1);
      expect(selector.getRobot('/robot2')).toBeUndefined();
    });

    it('selects first available when active robot is removed', () => {
      const message1: RobotListMessage = {
        type: 'robot_list',
        robots: [
          { robot_id: '/robot1', status: 'online' },
          { robot_id: '/robot2', status: 'online' },
        ],
      };
      connectionManager._emit('message', message1);
      selector.selectRobot('/robot2');

      const message2: RobotListMessage = {
        type: 'robot_list',
        robots: [{ robot_id: '/robot1', status: 'online' }],
      };
      connectionManager._emit('message', message2);

      expect(selector.getActiveRobotId()).toBe('/robot1');
    });
  });
});
