/**
 * TeleopPanel — Teleoperation mode UI panel for the SO-100 robot arm.
 *
 * Provides:
 * - Teleop mode toggle (must be explicitly activated before input capture)
 * - Velocity scale slider (range 0.01 to 0.2, default 0.05)
 * - Active input device indicator (keyboard/gamepad)
 * - Key/button mapping overlay
 * - Unreachable motion indicator on IK failure
 * - Deactivate teleop + show warning on WebSocket loss
 *
 * Validates: Requirements 5.4, 5.5, 5.6, 5.8, 5.9
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  TeleopModeMessage,
  ServerMessage,
  ErrorMessage,
  ConnectionState,
} from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Minimum velocity scale factor (m/s) */
export const VELOCITY_SCALE_MIN = 0.01;

/** Maximum velocity scale factor (m/s) */
export const VELOCITY_SCALE_MAX = 0.2;

/** Default velocity scale factor (m/s) */
export const VELOCITY_SCALE_DEFAULT = 0.05;

/** Slider step for velocity scale */
const VELOCITY_SCALE_STEP = 0.01;

/** Active input device types */
export type InputDevice = 'keyboard' | 'gamepad' | 'none';

// ─── Keyboard Mapping ───────────────────────────────────────────────────────

/** Keyboard mapping reference for the help overlay */
export const KEYBOARD_MAPPING = [
  { keys: 'W / S', action: '+Y / -Y Cartesian velocity' },
  { keys: 'A / D', action: '-X / +X Cartesian velocity' },
  { keys: 'Q / E', action: '+Z / -Z Cartesian velocity' },
  { keys: '↑ / ↓', action: 'Wrist pitch (±5°/s × scale)' },
  { keys: '← / →', action: 'Wrist roll (±5°/s × scale)' },
] as const;

/** Gamepad mapping reference for the help overlay */
export const GAMEPAD_MAPPING = [
  { input: 'Left Stick X/Y', action: 'XY Cartesian velocity' },
  { input: 'Right Stick Y', action: 'Z Cartesian velocity' },
  { input: 'Left Trigger', action: 'Gripper close' },
  { input: 'Right Trigger', action: 'Gripper open' },
] as const;

// ─── TeleopPanel ────────────────────────────────────────────────────────────

export interface TeleopPanelConfig {
  /** The ConnectionManager instance for WebSocket communication */
  connectionManager: ConnectionManager;
}

/**
 * TeleopPanel manages the teleoperation mode UI.
 *
 * The panel provides a mode toggle, velocity slider, device indicator,
 * and key mapping overlay. It deactivates teleop on WebSocket loss and
 * displays unreachable motion indicators when IK fails.
 */
export class TeleopPanel {
  private readonly connectionManager: ConnectionManager;

  // State
  private teleopEnabled = false;
  private velocityScale = VELOCITY_SCALE_DEFAULT;
  private activeDevice: InputDevice = 'none';
  private unreachableIndicatorVisible = false;
  private connectionLostWarningVisible = false;

  // DOM elements (created on mount)
  private container: HTMLElement | null = null;
  private rootElement: HTMLElement | null = null;
  private toggleButton: HTMLButtonElement | null = null;
  private velocitySlider: HTMLInputElement | null = null;
  private velocityValueDisplay: HTMLElement | null = null;
  private deviceIndicator: HTMLElement | null = null;
  private mappingOverlay: HTMLElement | null = null;
  private unreachableIndicator: HTMLElement | null = null;
  private warningBanner: HTMLElement | null = null;

  constructor(config: TeleopPanelConfig) {
    this.connectionManager = config.connectionManager;
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the teleop panel into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.render();
    this.attachEvents();
  }

  /**
   * Remove the teleop panel from the DOM and clean up event listeners.
   */
  unmount(): void {
    this.detachEvents();

    if (this.rootElement && this.container) {
      this.container.removeChild(this.rootElement);
    }

    this.container = null;
    this.rootElement = null;
    this.toggleButton = null;
    this.velocitySlider = null;
    this.velocityValueDisplay = null;
    this.deviceIndicator = null;
    this.mappingOverlay = null;
    this.unreachableIndicator = null;
    this.warningBanner = null;
  }

  /**
   * Handle incoming server messages relevant to the teleop panel.
   * Routes error messages to display unreachable indicator on IK failure.
   */
  handleMessage(message: ServerMessage): void {
    if (message.type === 'error') {
      this.handleError(message as ErrorMessage);
    }
  }

  /**
   * Get whether teleop mode is currently active.
   */
  isEnabled(): boolean {
    return this.teleopEnabled;
  }

  /**
   * Get the current velocity scale factor.
   */
  getVelocityScale(): number {
    return this.velocityScale;
  }

  /**
   * Get the currently active input device.
   */
  getActiveDevice(): InputDevice {
    return this.activeDevice;
  }

  /**
   * Set the active input device indicator.
   * Called externally by the TeleopController when device changes.
   */
  setActiveDevice(device: InputDevice): void {
    this.activeDevice = device;
    this.updateDeviceIndicator();
  }

  /**
   * Show the unreachable motion indicator (called on IK failure).
   */
  showUnreachableIndicator(): void {
    this.unreachableIndicatorVisible = true;
    if (this.unreachableIndicator) {
      this.unreachableIndicator.classList.add('teleop-panel__unreachable--visible');
      this.unreachableIndicator.setAttribute('aria-hidden', 'false');
    }
  }

  /**
   * Hide the unreachable motion indicator.
   */
  hideUnreachableIndicator(): void {
    this.unreachableIndicatorVisible = false;
    if (this.unreachableIndicator) {
      this.unreachableIndicator.classList.remove('teleop-panel__unreachable--visible');
      this.unreachableIndicator.setAttribute('aria-hidden', 'true');
    }
  }

  /**
   * Check if the unreachable indicator is currently visible.
   */
  isUnreachableVisible(): boolean {
    return this.unreachableIndicatorVisible;
  }

  /**
   * Check if the connection lost warning is currently visible.
   */
  isConnectionLostWarningVisible(): boolean {
    return this.connectionLostWarningVisible;
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    this.rootElement = document.createElement('div');
    this.rootElement.className = 'teleop-panel';
    this.rootElement.setAttribute('role', 'region');
    this.rootElement.setAttribute('aria-label', 'Teleoperation Controls');

    // Header
    const header = document.createElement('h3');
    header.className = 'teleop-panel__header';
    header.textContent = 'Teleoperation';
    this.rootElement.appendChild(header);

    // Warning banner (hidden by default)
    this.warningBanner = document.createElement('div');
    this.warningBanner.className = 'teleop-panel__warning';
    this.warningBanner.setAttribute('role', 'alert');
    this.warningBanner.setAttribute('aria-hidden', 'true');
    this.warningBanner.textContent =
      'Teleoperation suspended: connection lost';
    this.rootElement.appendChild(this.warningBanner);

    // Toggle button
    this.toggleButton = document.createElement('button');
    this.toggleButton.className = 'teleop-panel__toggle';
    this.toggleButton.setAttribute('aria-pressed', 'false');
    this.toggleButton.setAttribute('aria-label', 'Toggle teleoperation mode');
    this.toggleButton.textContent = 'Activate Teleop';
    this.rootElement.appendChild(this.toggleButton);

    // Velocity scale control
    const velocityGroup = document.createElement('div');
    velocityGroup.className = 'teleop-panel__velocity-group';

    const velocityLabel = document.createElement('label');
    velocityLabel.className = 'teleop-panel__velocity-label';
    velocityLabel.htmlFor = 'teleop-velocity-scale';
    velocityLabel.textContent = 'Velocity Scale';
    velocityGroup.appendChild(velocityLabel);

    const sliderRow = document.createElement('div');
    sliderRow.className = 'teleop-panel__slider-row';

    this.velocitySlider = document.createElement('input');
    this.velocitySlider.type = 'range';
    this.velocitySlider.id = 'teleop-velocity-scale';
    this.velocitySlider.className = 'teleop-panel__velocity-slider';
    this.velocitySlider.min = String(VELOCITY_SCALE_MIN);
    this.velocitySlider.max = String(VELOCITY_SCALE_MAX);
    this.velocitySlider.step = String(VELOCITY_SCALE_STEP);
    this.velocitySlider.value = String(this.velocityScale);
    this.velocitySlider.setAttribute('aria-label', 'Velocity scale factor');
    this.velocitySlider.setAttribute('aria-valuemin', String(VELOCITY_SCALE_MIN));
    this.velocitySlider.setAttribute('aria-valuemax', String(VELOCITY_SCALE_MAX));
    this.velocitySlider.setAttribute('aria-valuenow', String(this.velocityScale));
    sliderRow.appendChild(this.velocitySlider);

    this.velocityValueDisplay = document.createElement('span');
    this.velocityValueDisplay.className = 'teleop-panel__velocity-value';
    this.velocityValueDisplay.textContent = this.formatVelocityScale(this.velocityScale);
    sliderRow.appendChild(this.velocityValueDisplay);

    velocityGroup.appendChild(sliderRow);
    this.rootElement.appendChild(velocityGroup);

    // Active device indicator
    this.deviceIndicator = document.createElement('div');
    this.deviceIndicator.className = 'teleop-panel__device-indicator';
    this.deviceIndicator.setAttribute('aria-label', 'Active input device');
    this.updateDeviceIndicator();
    this.rootElement.appendChild(this.deviceIndicator);

    // Unreachable motion indicator (hidden by default)
    this.unreachableIndicator = document.createElement('div');
    this.unreachableIndicator.className = 'teleop-panel__unreachable';
    this.unreachableIndicator.setAttribute('role', 'alert');
    this.unreachableIndicator.setAttribute('aria-hidden', 'true');
    this.unreachableIndicator.textContent = 'Motion unreachable';
    this.rootElement.appendChild(this.unreachableIndicator);

    // Key/button mapping overlay
    this.mappingOverlay = document.createElement('div');
    this.mappingOverlay.className = 'teleop-panel__mapping-overlay';
    this.mappingOverlay.setAttribute('aria-label', 'Key and button mappings');
    this.renderMappingOverlay();
    this.rootElement.appendChild(this.mappingOverlay);

    this.container!.appendChild(this.rootElement);
  }

  private renderMappingOverlay(): void {
    if (!this.mappingOverlay) return;

    this.mappingOverlay.innerHTML = '';

    // Keyboard mappings section
    const kbSection = document.createElement('div');
    kbSection.className = 'teleop-panel__mapping-section';

    const kbTitle = document.createElement('h4');
    kbTitle.textContent = 'Keyboard';
    kbSection.appendChild(kbTitle);

    const kbList = document.createElement('dl');
    kbList.className = 'teleop-panel__mapping-list';
    for (const mapping of KEYBOARD_MAPPING) {
      const dt = document.createElement('dt');
      dt.textContent = mapping.keys;
      kbList.appendChild(dt);
      const dd = document.createElement('dd');
      dd.textContent = mapping.action;
      kbList.appendChild(dd);
    }
    kbSection.appendChild(kbList);
    this.mappingOverlay.appendChild(kbSection);

    // Gamepad mappings section
    const gpSection = document.createElement('div');
    gpSection.className = 'teleop-panel__mapping-section';

    const gpTitle = document.createElement('h4');
    gpTitle.textContent = 'Gamepad';
    gpSection.appendChild(gpTitle);

    const gpList = document.createElement('dl');
    gpList.className = 'teleop-panel__mapping-list';
    for (const mapping of GAMEPAD_MAPPING) {
      const dt = document.createElement('dt');
      dt.textContent = mapping.input;
      gpList.appendChild(dt);
      const dd = document.createElement('dd');
      dd.textContent = mapping.action;
      gpList.appendChild(dd);
    }
    gpSection.appendChild(gpList);
    this.mappingOverlay.appendChild(gpSection);
  }

  // ─── Private: Events ────────────────────────────────────────────────────

  private attachEvents(): void {
    this.toggleButton?.addEventListener('click', this.onToggleClick);
    this.velocitySlider?.addEventListener('input', this.onVelocitySliderInput);

    this.connectionManager.on('stateChange', this.onConnectionStateChange);
    this.connectionManager.on('message', this.onServerMessage);
  }

  private detachEvents(): void {
    this.toggleButton?.removeEventListener('click', this.onToggleClick);
    this.velocitySlider?.removeEventListener('input', this.onVelocitySliderInput);

    this.connectionManager.off('stateChange', this.onConnectionStateChange);
    this.connectionManager.off('message', this.onServerMessage);
  }

  private onToggleClick = (): void => {
    this.teleopEnabled = !this.teleopEnabled;
    this.updateToggleDisplay();
    this.sendTeleopModeMessage();

    // Clear unreachable indicator when toggling
    if (!this.teleopEnabled) {
      this.hideUnreachableIndicator();
    }
  };

  private onVelocitySliderInput = (): void => {
    if (!this.velocitySlider) return;

    const value = parseFloat(this.velocitySlider.value);
    this.velocityScale = this.clampVelocityScale(value);
    this.updateVelocityDisplay();
    this.sendTeleopModeMessage();
  };

  private onConnectionStateChange = (state: ConnectionState): void => {
    if (
      (state === 'disconnected' || state === 'reconnecting') &&
      this.teleopEnabled
    ) {
      // Deactivate teleop and show warning on WebSocket loss (Req 5.8)
      this.teleopEnabled = false;
      this.updateToggleDisplay();
      this.showConnectionLostWarning();
    }

    if (state === 'connected') {
      this.hideConnectionLostWarning();
    }
  };

  private onServerMessage = (message: ServerMessage): void => {
    this.handleMessage(message);
  };

  // ─── Private: Error Handling ────────────────────────────────────────────

  private handleError(message: ErrorMessage): void {
    // Show unreachable indicator on IK failures during teleop (Req 5.9)
    if (
      this.teleopEnabled &&
      (message.code === 'IK_NO_SOLUTION' ||
        message.code === 'IK_SINGULARITY' ||
        message.code === 'WORKSPACE_BOUNDARY')
    ) {
      this.showUnreachableIndicator();

      // Auto-hide after a short period
      setTimeout(() => {
        this.hideUnreachableIndicator();
      }, 2000);
    }
  }

  // ─── Private: Display Updates ───────────────────────────────────────────

  private updateToggleDisplay(): void {
    if (!this.toggleButton) return;

    this.toggleButton.setAttribute(
      'aria-pressed',
      String(this.teleopEnabled)
    );
    this.toggleButton.textContent = this.teleopEnabled
      ? 'Deactivate Teleop'
      : 'Activate Teleop';
    this.toggleButton.classList.toggle(
      'teleop-panel__toggle--active',
      this.teleopEnabled
    );
  }

  private updateVelocityDisplay(): void {
    if (this.velocitySlider) {
      this.velocitySlider.value = String(this.velocityScale);
      this.velocitySlider.setAttribute('aria-valuenow', String(this.velocityScale));
    }
    if (this.velocityValueDisplay) {
      this.velocityValueDisplay.textContent = this.formatVelocityScale(this.velocityScale);
    }
  }

  private updateDeviceIndicator(): void {
    if (!this.deviceIndicator) return;

    let icon: string;
    let label: string;

    switch (this.activeDevice) {
      case 'keyboard':
        icon = '⌨️';
        label = 'Keyboard active';
        break;
      case 'gamepad':
        icon = '🎮';
        label = 'Gamepad active';
        break;
      default:
        icon = '—';
        label = 'No active input device';
        break;
    }

    this.deviceIndicator.textContent = `${icon} ${label}`;
    this.deviceIndicator.setAttribute('aria-label', label);
  }

  private showConnectionLostWarning(): void {
    this.connectionLostWarningVisible = true;
    if (this.warningBanner) {
      this.warningBanner.classList.add('teleop-panel__warning--visible');
      this.warningBanner.setAttribute('aria-hidden', 'false');
    }
  }

  private hideConnectionLostWarning(): void {
    this.connectionLostWarningVisible = false;
    if (this.warningBanner) {
      this.warningBanner.classList.remove('teleop-panel__warning--visible');
      this.warningBanner.setAttribute('aria-hidden', 'true');
    }
  }

  // ─── Private: Helpers ───────────────────────────────────────────────────

  private sendTeleopModeMessage(): void {
    const message: TeleopModeMessage = {
      type: 'teleop_mode',
      enabled: this.teleopEnabled,
      velocity_scale: this.velocityScale,
    };
    this.connectionManager.send(message);
  }

  private clampVelocityScale(value: number): number {
    return Math.max(VELOCITY_SCALE_MIN, Math.min(VELOCITY_SCALE_MAX, value));
  }

  private formatVelocityScale(value: number): string {
    return value.toFixed(2) + ' m/s';
  }
}
