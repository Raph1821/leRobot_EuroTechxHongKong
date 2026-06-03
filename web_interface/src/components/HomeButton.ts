/**
 * HomeButton — "Home Position" button for the SO-100 robot arm.
 *
 * Commands all 5 arm joints to position 0.0 radians on click.
 * Discards the command and shows a notification if the WebSocket is disconnected.
 *
 * Validates: Requirements 8.5, 8.6
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type { JointCommandMessage } from '../types';
import { ARM_JOINT_NAMES } from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Duration (ms) to show the disconnected notification */
const NOTIFICATION_DISPLAY_DURATION_MS = 3000;

// ─── HomeButton ─────────────────────────────────────────────────────────────

export interface HomeButtonConfig {
  /** The ConnectionManager instance for WebSocket communication */
  connectionManager: ConnectionManager;
  /** Optional container element to render into */
  container?: HTMLElement;
}

/**
 * HomeButton sends all arm joints to position 0.0 radians (home position).
 *
 * Features:
 * - Single button that commands all 5 arm joints to 0.0 rad
 * - Shows a notification when the command is discarded due to disconnection
 * - Disables when connection is unavailable
 */
export class HomeButton {
  private readonly connectionManager: ConnectionManager;
  private readonly container: HTMLElement;

  // DOM elements
  private rootElement: HTMLElement | null = null;
  private buttonElement: HTMLButtonElement | null = null;
  private notificationElement: HTMLElement | null = null;
  private notificationTimer: ReturnType<typeof setTimeout> | null = null;

  /** Whether the button is enabled (connected) */
  private enabled = false;

  constructor(config: HomeButtonConfig) {
    this.connectionManager = config.connectionManager;
    this.container = config.container ?? document.createElement('div');

    this.render();
    this.attachEvents();
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /** Get the root DOM element for this component */
  getElement(): HTMLElement {
    return this.rootElement!;
  }

  /** Check if the button is currently enabled */
  isEnabled(): boolean {
    return this.enabled;
  }

  /** Enable the button (called on WebSocket connect) */
  enable(): void {
    this.enabled = true;
    if (this.buttonElement) {
      this.buttonElement.disabled = false;
    }
  }

  /** Disable the button (called on WebSocket disconnect) */
  disable(): void {
    this.enabled = false;
    if (this.buttonElement) {
      this.buttonElement.disabled = true;
    }
  }

  /** Check if the notification is currently visible */
  isNotificationVisible(): boolean {
    if (!this.notificationElement) return false;
    return this.notificationElement.style.display !== 'none';
  }

  /** Clean up event listeners and DOM elements */
  dispose(): void {
    this.clearNotificationTimer();
    this.detachEvents();
    if (this.rootElement && this.rootElement.parentNode) {
      this.rootElement.parentNode.removeChild(this.rootElement);
    }
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    this.rootElement = document.createElement('div');
    this.rootElement.className = 'home-button';

    // Button
    this.buttonElement = document.createElement('button');
    this.buttonElement.className = 'home-button__btn';
    this.buttonElement.textContent = 'Home Position';
    this.buttonElement.setAttribute('aria-label', 'Move all joints to home position (0.0 radians)');
    this.buttonElement.disabled = !this.enabled;
    this.rootElement.appendChild(this.buttonElement);

    // Notification area
    this.notificationElement = document.createElement('div');
    this.notificationElement.className = 'home-button__notification';
    this.notificationElement.setAttribute('role', 'alert');
    this.notificationElement.style.display = 'none';
    this.rootElement.appendChild(this.notificationElement);

    this.container.appendChild(this.rootElement);
  }

  // ─── Private: Events ────────────────────────────────────────────────────

  private onButtonClick = (): void => {
    const state = this.connectionManager.getState();

    if (state !== 'connected') {
      // Discard command and show notification (Req 8.6)
      this.showNotification('Command not delivered: WebSocket disconnected');
      return;
    }

    // Build joint command with all arm joints at 0.0 radians (Req 8.5)
    const command: JointCommandMessage = {
      type: 'joint_command',
      joints: ARM_JOINT_NAMES.map((name) => ({ name, position: 0.0 })),
    };

    const sent = this.connectionManager.send(command);
    if (!sent) {
      this.showNotification('Command not delivered: WebSocket disconnected');
    }
  };

  private onControlsEnabled = (): void => {
    this.enable();
  };

  private onControlsDisabled = (): void => {
    this.disable();
  };

  private attachEvents(): void {
    this.buttonElement?.addEventListener('click', this.onButtonClick);
    this.connectionManager.on('controlsEnabled', this.onControlsEnabled);
    this.connectionManager.on('controlsDisabled', this.onControlsDisabled);
  }

  private detachEvents(): void {
    this.buttonElement?.removeEventListener('click', this.onButtonClick);
    this.connectionManager.off('controlsEnabled', this.onControlsEnabled);
    this.connectionManager.off('controlsDisabled', this.onControlsDisabled);
  }

  // ─── Private: Notification ──────────────────────────────────────────────

  private showNotification(message: string): void {
    if (!this.notificationElement) return;

    this.notificationElement.textContent = message;
    this.notificationElement.style.display = 'block';

    // Clear any existing timer
    this.clearNotificationTimer();

    // Auto-hide after duration
    this.notificationTimer = setTimeout(() => {
      this.hideNotification();
    }, NOTIFICATION_DISPLAY_DURATION_MS);
  }

  private hideNotification(): void {
    if (this.notificationElement) {
      this.notificationElement.style.display = 'none';
      this.notificationElement.textContent = '';
    }
    this.notificationTimer = null;
  }

  private clearNotificationTimer(): void {
    if (this.notificationTimer !== null) {
      clearTimeout(this.notificationTimer);
      this.notificationTimer = null;
    }
  }
}
