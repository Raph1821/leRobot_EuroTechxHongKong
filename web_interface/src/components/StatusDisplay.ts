/**
 * StatusDisplay — connection and simulation status UI for the SO-100 web control interface.
 *
 * Features:
 * - Connection indicator with three states: Connected (green), Reconnecting (yellow), Disconnected (red)
 * - Simulation status display (running/paused/disconnected) from sim_status messages, updated within 1s
 * - Error notifications area for trajectory failures and validation errors
 * - Notifications persist until dismissed or a new command is issued
 *
 * Requirements: 10.1, 10.6, 9.5
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  ConnectionState,
  ServerMessage,
  SimStatusMessage,
  TrajectoryStatusMessage,
  ErrorMessage,
} from '../types';

// ─── Types ──────────────────────────────────────────────────────────────────

/** Visual indicator color for connection state */
export type IndicatorColor = 'green' | 'yellow' | 'red';

/** Simulation status as reported by the server */
export type SimulationState = 'running' | 'paused' | 'disconnected' | 'unknown';

/** An error notification displayed to the user */
export interface ErrorNotification {
  id: number;
  message: string;
  timestamp: number;
}

// ─── Constants ──────────────────────────────────────────────────────────────

/** Maps connection states to indicator colors */
const CONNECTION_STATE_COLORS: Record<ConnectionState, IndicatorColor> = {
  connected: 'green',
  connecting: 'yellow',
  reconnecting: 'yellow',
  disconnected: 'red',
};

/** Maps connection states to display labels */
const CONNECTION_STATE_LABELS: Record<ConnectionState, string> = {
  connected: 'Connected',
  connecting: 'Connecting',
  reconnecting: 'Reconnecting',
  disconnected: 'Disconnected',
};

/** Maps simulation states to display labels */
const SIM_STATE_LABELS: Record<SimulationState, string> = {
  running: 'Running',
  paused: 'Paused',
  disconnected: 'Disconnected',
  unknown: 'Unknown',
};

// ─── StatusDisplay ──────────────────────────────────────────────────────────

export class StatusDisplay {
  private readonly connectionManager: ConnectionManager;

  // State
  private connectionState: ConnectionState = 'disconnected';
  private simulationState: SimulationState = 'unknown';
  private notifications: ErrorNotification[] = [];
  private nextNotificationId = 1;

  // DOM elements (created on mount)
  private container: HTMLElement | null = null;
  private connectionIndicator: HTMLElement | null = null;
  private connectionLabel: HTMLElement | null = null;
  private simStatusLabel: HTMLElement | null = null;
  private notificationArea: HTMLElement | null = null;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;

    // Listen for connection state changes
    this.connectionManager.on('stateChange', this.handleStateChange);
    this.connectionManager.on('message', this.handleMessage);

    // Initialize from current state
    this.connectionState = this.connectionManager.getState();
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the status display into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('status-display');
    this.container.setAttribute('role', 'status');
    this.container.setAttribute('aria-live', 'polite');

    this.render();
    this.updateConnectionDisplay();
    this.updateSimStatusDisplay();
  }

  /**
   * Remove the status display from the DOM and clean up event listeners.
   */
  unmount(): void {
    this.connectionManager.off('stateChange', this.handleStateChange);
    this.connectionManager.off('message', this.handleMessage);

    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('status-display');
    }
    this.container = null;
    this.connectionIndicator = null;
    this.connectionLabel = null;
    this.simStatusLabel = null;
    this.notificationArea = null;
  }

  /**
   * Get the current connection state.
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Get the indicator color for the current connection state.
   */
  getIndicatorColor(): IndicatorColor {
    return CONNECTION_STATE_COLORS[this.connectionState];
  }

  /**
   * Get the current simulation state.
   */
  getSimulationState(): SimulationState {
    return this.simulationState;
  }

  /**
   * Get all active error notifications.
   */
  getNotifications(): ErrorNotification[] {
    return [...this.notifications];
  }

  /**
   * Add an error notification. Notifications persist until dismissed or cleared.
   */
  addNotification(message: string): void {
    const notification: ErrorNotification = {
      id: this.nextNotificationId++,
      message,
      timestamp: Date.now(),
    };
    this.notifications.push(notification);
    this.renderNotifications();
  }

  /**
   * Dismiss a specific notification by ID.
   */
  dismissNotification(id: number): void {
    this.notifications = this.notifications.filter(n => n.id !== id);
    this.renderNotifications();
  }

  /**
   * Clear all notifications (e.g., when a new trajectory command is issued).
   */
  clearNotifications(): void {
    this.notifications = [];
    this.renderNotifications();
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    if (!this.container) return;

    // Connection status section
    const connectionSection = document.createElement('div');
    connectionSection.className = 'status-display__connection';

    this.connectionIndicator = document.createElement('span');
    this.connectionIndicator.className = 'status-display__indicator';
    this.connectionIndicator.setAttribute('aria-hidden', 'true');
    connectionSection.appendChild(this.connectionIndicator);

    this.connectionLabel = document.createElement('span');
    this.connectionLabel.className = 'status-display__connection-label';
    connectionSection.appendChild(this.connectionLabel);

    this.container.appendChild(connectionSection);

    // Simulation status section
    const simSection = document.createElement('div');
    simSection.className = 'status-display__simulation';

    const simLabel = document.createElement('span');
    simLabel.className = 'status-display__sim-title';
    simLabel.textContent = 'Sim: ';
    simSection.appendChild(simLabel);

    this.simStatusLabel = document.createElement('span');
    this.simStatusLabel.className = 'status-display__sim-state';
    simSection.appendChild(this.simStatusLabel);

    this.container.appendChild(simSection);

    // Notifications area
    this.notificationArea = document.createElement('div');
    this.notificationArea.className = 'status-display__notifications';
    this.notificationArea.setAttribute('role', 'alert');
    this.notificationArea.setAttribute('aria-live', 'assertive');
    this.container.appendChild(this.notificationArea);
  }

  private updateConnectionDisplay(): void {
    if (!this.connectionIndicator || !this.connectionLabel) return;

    const color = this.getIndicatorColor();
    const label = CONNECTION_STATE_LABELS[this.connectionState];

    // Update indicator color
    this.connectionIndicator.className = `status-display__indicator status-display__indicator--${color}`;

    // Update label text
    this.connectionLabel.textContent = label;
    this.connectionLabel.className = `status-display__connection-label status-display__connection-label--${color}`;
  }

  private updateSimStatusDisplay(): void {
    if (!this.simStatusLabel) return;

    const label = SIM_STATE_LABELS[this.simulationState];
    this.simStatusLabel.textContent = label;
    this.simStatusLabel.className = `status-display__sim-state status-display__sim-state--${this.simulationState}`;
  }

  private renderNotifications(): void {
    if (!this.notificationArea) return;

    this.notificationArea.innerHTML = '';

    for (const notification of this.notifications) {
      const notifElement = document.createElement('div');
      notifElement.className = 'status-display__notification';
      notifElement.dataset.notificationId = String(notification.id);

      const messageSpan = document.createElement('span');
      messageSpan.className = 'status-display__notification-message';
      messageSpan.textContent = notification.message;
      notifElement.appendChild(messageSpan);

      const dismissButton = document.createElement('button');
      dismissButton.className = 'status-display__notification-dismiss';
      dismissButton.textContent = '✕';
      dismissButton.setAttribute('aria-label', 'Dismiss notification');
      dismissButton.addEventListener('click', () => {
        this.dismissNotification(notification.id);
      });
      notifElement.appendChild(dismissButton);

      this.notificationArea.appendChild(notifElement);
    }
  }

  // ─── Private: Event Handlers ────────────────────────────────────────────

  private handleStateChange = (state: ConnectionState): void => {
    this.connectionState = state;
    this.updateConnectionDisplay();
  };

  private handleMessage = (message: ServerMessage): void => {
    if (message.type === 'sim_status') {
      this.handleSimStatus(message as SimStatusMessage);
    } else if (message.type === 'trajectory_status') {
      this.handleTrajectoryStatus(message as TrajectoryStatusMessage);
    } else if (message.type === 'error') {
      this.handleError(message as ErrorMessage);
    }
  };

  private handleSimStatus(message: SimStatusMessage): void {
    this.simulationState = message.state;
    this.updateSimStatusDisplay();
  }

  private handleTrajectoryStatus(message: TrajectoryStatusMessage): void {
    if (message.status === 'aborted' || message.status === 'preempted') {
      this.addNotification(
        `Trajectory ${message.status}: ${message.message}`
      );
    }
  }

  private handleError(message: ErrorMessage): void {
    this.addNotification(`Error [${message.code}]: ${message.message}`);
  }
}
