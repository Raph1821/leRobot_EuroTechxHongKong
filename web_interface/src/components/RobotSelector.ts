/**
 * RobotSelector — multi-robot namespace selection panel for the SO-100 web control interface.
 *
 * Displays available robot namespaces reported by the WebSocket bridge, shows per-robot
 * online/offline status, and allows the user to select the active robot for control.
 * On selection change, notifies other components via a callback so they can synchronize
 * joint state, update the 3D viewer highlight, and route commands to the selected namespace.
 *
 * Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.7, 6.9
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  SelectRobotMessage,
  RobotListMessage,
  RobotStatusChangeMessage,
  NamespacedJointStateMessage,
  ServerMessage,
} from '../types';

// ─── Types ──────────────────────────────────────────────────────────────────

/** Per-robot entry in the selector */
export interface RobotEntry {
  robot_id: string;
  status: 'online' | 'offline';
  /** Timestamp of last received joint state (ms since epoch) */
  lastJointStateTime: number;
}

/** Configuration for the RobotSelector component */
export interface RobotSelectorConfig {
  /** The ConnectionManager instance for WebSocket communication */
  connectionManager: ConnectionManager;
  /** Timeout in ms before marking a robot offline (default: 5000) */
  offlineTimeoutMs?: number;
  /** Interval in ms for checking robot health (default: 1000) */
  healthCheckIntervalMs?: number;
}

/** Callback type for robot selection changes */
export type RobotSelectedCallback = (robotId: string) => void;

// ─── Constants ──────────────────────────────────────────────────────────────

/** Default time in ms without joint state before marking a robot offline */
const DEFAULT_OFFLINE_TIMEOUT_MS = 5000;

/** Default interval in ms for health monitoring checks */
const DEFAULT_HEALTH_CHECK_INTERVAL_MS = 1000;

// ─── RobotSelector ──────────────────────────────────────────────────────────

/**
 * RobotSelector manages the multi-robot namespace selection UI.
 *
 * Features:
 * - Displays list of robot namespaces from bridge's `robot_list` message
 * - Shows per-robot status (online/offline) with visual indicators
 * - User can click to select active robot for control
 * - Highlights active robot with distinct visual indicator
 * - Marks robot offline after 5s without joint state
 * - Restores online status when joint states resume
 * - Sends `select_robot` command to bridge on selection change
 * - Synchronization with control panels via onRobotSelected callback
 */
export class RobotSelector {
  private readonly connectionManager: ConnectionManager;
  private readonly offlineTimeoutMs: number;
  private readonly healthCheckIntervalMs: number;

  // State
  private robots: Map<string, RobotEntry> = new Map();
  private activeRobotId: string = '';
  private healthCheckTimer: ReturnType<typeof setInterval> | null = null;

  // DOM
  private container: HTMLElement | null = null;
  private listElement: HTMLElement | null = null;

  // Callbacks
  private onRobotSelectedCallback: RobotSelectedCallback | null = null;

  constructor(config: RobotSelectorConfig) {
    this.connectionManager = config.connectionManager;
    this.offlineTimeoutMs = config.offlineTimeoutMs ?? DEFAULT_OFFLINE_TIMEOUT_MS;
    this.healthCheckIntervalMs = config.healthCheckIntervalMs ?? DEFAULT_HEALTH_CHECK_INTERVAL_MS;
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the robot selector into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('robot-selector');
    this.container.setAttribute('role', 'group');
    this.container.setAttribute('aria-label', 'Robot Selector');

    this.render();
    this.attachEvents();
    this.startHealthMonitoring();
  }

  /**
   * Remove the robot selector from the DOM and clean up event listeners and timers.
   */
  unmount(): void {
    this.stopHealthMonitoring();
    this.detachEvents();

    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('robot-selector');
      this.container.removeAttribute('role');
      this.container.removeAttribute('aria-label');
    }

    this.container = null;
    this.listElement = null;
  }

  /**
   * Set the callback invoked when the user selects a different robot.
   * The callback receives the robot_id (namespace string).
   */
  set onRobotSelected(callback: RobotSelectedCallback | null) {
    this.onRobotSelectedCallback = callback;
  }

  /**
   * Get the callback for robot selection changes.
   */
  get onRobotSelected(): RobotSelectedCallback | null {
    return this.onRobotSelectedCallback;
  }

  /**
   * Get the currently active robot ID (namespace).
   */
  getActiveRobotId(): string {
    return this.activeRobotId;
  }

  /**
   * Get all known robot entries.
   */
  getRobots(): RobotEntry[] {
    return Array.from(this.robots.values());
  }

  /**
   * Get a specific robot entry by ID.
   */
  getRobot(robotId: string): RobotEntry | undefined {
    return this.robots.get(robotId);
  }

  /**
   * Handle an incoming server message. Route to appropriate internal handler.
   * Call this from the main message dispatch.
   */
  handleMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'robot_list':
        this.handleRobotList(message as RobotListMessage);
        break;
      case 'robot_status_change':
        this.handleRobotStatusChange(message as RobotStatusChangeMessage);
        break;
      case 'joint_state':
        this.handleJointState(message as NamespacedJointStateMessage);
        break;
    }
  }

  /**
   * Programmatically select a robot by ID.
   * Returns true if selection was successful, false if robot_id is unknown.
   */
  selectRobot(robotId: string): boolean {
    if (!this.robots.has(robotId)) {
      return false;
    }

    if (this.activeRobotId === robotId) {
      return true;
    }

    this.activeRobotId = robotId;

    // Send select_robot message to bridge
    const message: SelectRobotMessage = {
      type: 'select_robot',
      robot_id: robotId,
    };
    this.connectionManager.send(message);

    // Notify listeners
    if (this.onRobotSelectedCallback) {
      this.onRobotSelectedCallback(robotId);
    }

    // Update UI
    this.renderList();

    return true;
  }

  // ─── Private: Message Handlers ──────────────────────────────────────────

  private handleRobotList(message: RobotListMessage): void {
    const now = Date.now();

    // Update robots map from the full list
    const incomingIds = new Set(message.robots.map((r) => r.robot_id));

    // Remove robots no longer in the list
    for (const existingId of this.robots.keys()) {
      if (!incomingIds.has(existingId)) {
        this.robots.delete(existingId);
      }
    }

    // Add/update robots from the message
    for (const robot of message.robots) {
      const existing = this.robots.get(robot.robot_id);
      this.robots.set(robot.robot_id, {
        robot_id: robot.robot_id,
        status: robot.status,
        lastJointStateTime: existing?.lastJointStateTime ?? (robot.status === 'online' ? now : 0),
      });
    }

    // Auto-select first robot if none selected
    if (!this.activeRobotId && this.robots.size > 0) {
      const firstOnline = message.robots.find((r) => r.status === 'online');
      const firstRobot = firstOnline ?? message.robots[0];
      if (firstRobot) {
        this.activeRobotId = firstRobot.robot_id;
        // Send select to bridge
        const selectMsg: SelectRobotMessage = {
          type: 'select_robot',
          robot_id: this.activeRobotId,
        };
        this.connectionManager.send(selectMsg);

        if (this.onRobotSelectedCallback) {
          this.onRobotSelectedCallback(this.activeRobotId);
        }
      }
    }

    // If active robot was removed, select the first available
    if (this.activeRobotId && !this.robots.has(this.activeRobotId)) {
      const first = this.robots.keys().next().value;
      if (first) {
        this.activeRobotId = first;
        const selectMsg: SelectRobotMessage = {
          type: 'select_robot',
          robot_id: this.activeRobotId,
        };
        this.connectionManager.send(selectMsg);

        if (this.onRobotSelectedCallback) {
          this.onRobotSelectedCallback(this.activeRobotId);
        }
      } else {
        this.activeRobotId = '';
      }
    }

    this.renderList();
  }

  private handleRobotStatusChange(message: RobotStatusChangeMessage): void {
    const robot = this.robots.get(message.robot_id);
    if (!robot) return;

    robot.status = message.status;

    // If coming back online, update last joint state time
    if (message.status === 'online') {
      robot.lastJointStateTime = Date.now();
    }

    this.renderList();
  }

  private handleJointState(message: NamespacedJointStateMessage): void {
    // Only process namespaced joint states (those with robot_id)
    if (!message.robot_id) return;

    const robot = this.robots.get(message.robot_id);
    if (!robot) return;

    robot.lastJointStateTime = Date.now();

    // Restore online status if previously offline
    if (robot.status === 'offline') {
      robot.status = 'online';
      this.renderList();
    }
  }

  // ─── Private: Health Monitoring ─────────────────────────────────────────

  private startHealthMonitoring(): void {
    this.healthCheckTimer = setInterval(() => {
      this.checkRobotHealth();
    }, this.healthCheckIntervalMs);
  }

  private stopHealthMonitoring(): void {
    if (this.healthCheckTimer !== null) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }

  private checkRobotHealth(): void {
    const now = Date.now();
    let changed = false;

    for (const robot of this.robots.values()) {
      if (
        robot.status === 'online' &&
        robot.lastJointStateTime > 0 &&
        now - robot.lastJointStateTime > this.offlineTimeoutMs
      ) {
        robot.status = 'offline';
        changed = true;
      }
    }

    if (changed) {
      this.renderList();
    }
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    if (!this.container) return;

    // Title
    const title = document.createElement('h3');
    title.className = 'robot-selector__title';
    title.textContent = 'Robots';
    this.container.appendChild(title);

    // Robot list
    this.listElement = document.createElement('ul');
    this.listElement.className = 'robot-selector__list';
    this.listElement.setAttribute('role', 'listbox');
    this.listElement.setAttribute('aria-label', 'Available robots');
    this.container.appendChild(this.listElement);

    this.renderList();
  }

  private renderList(): void {
    if (!this.listElement) return;

    this.listElement.innerHTML = '';

    if (this.robots.size === 0) {
      const emptyItem = document.createElement('li');
      emptyItem.className = 'robot-selector__empty';
      emptyItem.textContent = 'No robots available';
      this.listElement.appendChild(emptyItem);
      return;
    }

    for (const robot of this.robots.values()) {
      const item = document.createElement('li');
      item.className = 'robot-selector__item';
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', String(robot.robot_id === this.activeRobotId));
      item.dataset.robotId = robot.robot_id;

      if (robot.robot_id === this.activeRobotId) {
        item.classList.add('robot-selector__item--active');
      }

      if (robot.status === 'offline') {
        item.classList.add('robot-selector__item--offline');
      }

      // Status indicator
      const statusDot = document.createElement('span');
      statusDot.className = `robot-selector__status robot-selector__status--${robot.status}`;
      statusDot.setAttribute('aria-label', `Status: ${robot.status}`);
      item.appendChild(statusDot);

      // Robot name label
      const nameLabel = document.createElement('span');
      nameLabel.className = 'robot-selector__name';
      nameLabel.textContent = robot.robot_id;
      item.appendChild(nameLabel);

      // Status text
      const statusText = document.createElement('span');
      statusText.className = 'robot-selector__status-text';
      statusText.textContent = robot.status;
      item.appendChild(statusText);

      // Active indicator
      if (robot.robot_id === this.activeRobotId) {
        const activeIndicator = document.createElement('span');
        activeIndicator.className = 'robot-selector__active-indicator';
        activeIndicator.textContent = '▶';
        activeIndicator.setAttribute('aria-label', 'Active robot');
        item.appendChild(activeIndicator);
      }

      // Click to select
      item.addEventListener('click', () => {
        this.selectRobot(robot.robot_id);
      });

      this.listElement.appendChild(item);
    }
  }

  // ─── Private: Events ────────────────────────────────────────────────────

  private attachEvents(): void {
    this.connectionManager.on('message', this.onMessage);
    this.connectionManager.on('controlsDisabled', this.onControlsDisabled);
  }

  private detachEvents(): void {
    this.connectionManager.off('message', this.onMessage);
    this.connectionManager.off('controlsDisabled', this.onControlsDisabled);
  }

  private onMessage = (message: unknown): void => {
    this.handleMessage(message as ServerMessage);
  };

  private onControlsDisabled = (): void => {
    // When connection is lost, mark all robots as offline
    for (const robot of this.robots.values()) {
      robot.status = 'offline';
    }
    this.renderList();
  };
}
