/**
 * GripperControl — gripper slider/buttons for the SO-100 robot arm.
 *
 * Provides a slider control for the gripper joint with range [-0.1792, 1.5708] radians.
 * Sends gripper commands via WebSocket on adjustment and displays the current
 * gripper position from joint state feedback.
 *
 * Validates: Requirements 8.2
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type { GripperCommandMessage, JointStateMessage } from '../types';
import { JOINT_CONFIGS } from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Gripper joint configuration from URDF */
const GRIPPER_CONFIG = JOINT_CONFIGS.find((j) => j.name === 'Gripper')!;

/** Minimum gripper position in radians */
export const GRIPPER_MIN = GRIPPER_CONFIG.lowerLimit; // -0.1792

/** Maximum gripper position in radians */
export const GRIPPER_MAX = GRIPPER_CONFIG.upperLimit; // 1.5708

/** Slider step resolution */
const SLIDER_STEP = 0.01;

// ─── GripperControl ─────────────────────────────────────────────────────────

export interface GripperControlConfig {
  /** The ConnectionManager instance for WebSocket communication */
  connectionManager: ConnectionManager;
  /** Optional container element to render into */
  container?: HTMLElement;
}

/**
 * GripperControl manages a slider + open/close buttons for the SO-100 gripper joint.
 *
 * Features:
 * - Range slider for precise gripper position control [-0.1792, 1.5708] rad
 * - "Open" and "Close" convenience buttons
 * - Numeric display of current position (2 decimal places)
 * - Automatic updates from joint state feedback
 * - Disables controls when connection is unavailable
 */
export class GripperControl {
  private readonly connectionManager: ConnectionManager;
  private readonly container: HTMLElement;

  // DOM elements
  private rootElement: HTMLElement | null = null;
  private sliderElement: HTMLInputElement | null = null;
  private valueDisplay: HTMLElement | null = null;
  private openButton: HTMLButtonElement | null = null;
  private closeButton: HTMLButtonElement | null = null;

  /** Current gripper position in radians */
  private currentPosition = 0;

  /** Whether controls are enabled (connected) */
  private enabled = false;

  constructor(config: GripperControlConfig) {
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

  /** Get the current gripper position */
  getPosition(): number {
    return this.currentPosition;
  }

  /** Check if controls are currently enabled */
  isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Update the gripper position from a joint state message.
   * Call this when a joint_state message is received.
   */
  updateFromJointState(message: JointStateMessage): void {
    const gripperIndex = message.joints.names.indexOf('Gripper');
    if (gripperIndex === -1) return;

    const position = message.joints.positions[gripperIndex];
    if (position === undefined || !isFinite(position)) return;

    this.currentPosition = position;
    this.updateDisplay();
  }

  /** Enable controls (called on WebSocket connect) */
  enable(): void {
    this.enabled = true;
    this.setControlsDisabled(false);
  }

  /** Disable controls (called on WebSocket disconnect) */
  disable(): void {
    this.enabled = false;
    this.setControlsDisabled(true);
  }

  /** Clean up event listeners and DOM elements */
  dispose(): void {
    this.detachEvents();
    if (this.rootElement && this.rootElement.parentNode) {
      this.rootElement.parentNode.removeChild(this.rootElement);
    }
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    this.rootElement = document.createElement('div');
    this.rootElement.className = 'gripper-control';
    this.rootElement.setAttribute('role', 'group');
    this.rootElement.setAttribute('aria-label', 'Gripper Control');

    // Label
    const label = document.createElement('label');
    label.className = 'gripper-control__label';
    label.textContent = 'Gripper';
    label.htmlFor = 'gripper-slider';
    this.rootElement.appendChild(label);

    // Slider container
    const sliderContainer = document.createElement('div');
    sliderContainer.className = 'gripper-control__slider-container';

    // Range slider
    this.sliderElement = document.createElement('input');
    this.sliderElement.type = 'range';
    this.sliderElement.id = 'gripper-slider';
    this.sliderElement.className = 'gripper-control__slider';
    this.sliderElement.min = String(GRIPPER_MIN);
    this.sliderElement.max = String(GRIPPER_MAX);
    this.sliderElement.step = String(SLIDER_STEP);
    this.sliderElement.value = String(this.currentPosition);
    this.sliderElement.setAttribute('aria-label', 'Gripper position');
    this.sliderElement.setAttribute('aria-valuemin', String(GRIPPER_MIN));
    this.sliderElement.setAttribute('aria-valuemax', String(GRIPPER_MAX));
    this.sliderElement.setAttribute('aria-valuenow', String(this.currentPosition));
    this.sliderElement.disabled = !this.enabled;
    sliderContainer.appendChild(this.sliderElement);

    // Value display
    this.valueDisplay = document.createElement('span');
    this.valueDisplay.className = 'gripper-control__value';
    this.valueDisplay.textContent = this.formatPosition(this.currentPosition);
    sliderContainer.appendChild(this.valueDisplay);

    this.rootElement.appendChild(sliderContainer);

    // Buttons container
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'gripper-control__buttons';

    // Open button (max position)
    this.openButton = document.createElement('button');
    this.openButton.className = 'gripper-control__btn gripper-control__btn--open';
    this.openButton.textContent = 'Open';
    this.openButton.setAttribute('aria-label', 'Open gripper');
    this.openButton.disabled = !this.enabled;
    buttonsContainer.appendChild(this.openButton);

    // Close button (min position)
    this.closeButton = document.createElement('button');
    this.closeButton.className = 'gripper-control__btn gripper-control__btn--close';
    this.closeButton.textContent = 'Close';
    this.closeButton.setAttribute('aria-label', 'Close gripper');
    this.closeButton.disabled = !this.enabled;
    buttonsContainer.appendChild(this.closeButton);

    this.rootElement.appendChild(buttonsContainer);

    // Range indicators
    const rangeIndicator = document.createElement('div');
    rangeIndicator.className = 'gripper-control__range';
    rangeIndicator.innerHTML = `<span>${GRIPPER_MIN.toFixed(4)}</span><span>${GRIPPER_MAX.toFixed(4)}</span>`;
    this.rootElement.appendChild(rangeIndicator);

    this.container.appendChild(this.rootElement);
  }

  // ─── Private: Events ────────────────────────────────────────────────────

  private onSliderInput = (): void => {
    if (!this.sliderElement || !this.enabled) return;

    const value = parseFloat(this.sliderElement.value);
    const clamped = this.clampPosition(value);
    this.currentPosition = clamped;
    this.updateDisplay();
    this.sendGripperCommand(clamped);
  };

  private onOpenClick = (): void => {
    if (!this.enabled) return;
    this.currentPosition = GRIPPER_MAX;
    this.updateDisplay();
    this.sendGripperCommand(GRIPPER_MAX);
  };

  private onCloseClick = (): void => {
    if (!this.enabled) return;
    this.currentPosition = GRIPPER_MIN;
    this.updateDisplay();
    this.sendGripperCommand(GRIPPER_MIN);
  };

  private attachEvents(): void {
    this.sliderElement?.addEventListener('input', this.onSliderInput);
    this.openButton?.addEventListener('click', this.onOpenClick);
    this.closeButton?.addEventListener('click', this.onCloseClick);

    // Listen for connection state changes
    this.connectionManager.on('controlsEnabled', this.onControlsEnabled);
    this.connectionManager.on('controlsDisabled', this.onControlsDisabled);
    this.connectionManager.on('message', this.onMessage);
  }

  private detachEvents(): void {
    this.sliderElement?.removeEventListener('input', this.onSliderInput);
    this.openButton?.removeEventListener('click', this.onOpenClick);
    this.closeButton?.removeEventListener('click', this.onCloseClick);

    this.connectionManager.off('controlsEnabled', this.onControlsEnabled);
    this.connectionManager.off('controlsDisabled', this.onControlsDisabled);
    this.connectionManager.off('message', this.onMessage);
  }

  private onControlsEnabled = (): void => {
    this.enable();
  };

  private onControlsDisabled = (): void => {
    this.disable();
  };

  private onMessage = (message: unknown): void => {
    const msg = message as { type?: string };
    if (msg && msg.type === 'joint_state') {
      this.updateFromJointState(message as JointStateMessage);
    }
  };

  // ─── Private: Helpers ───────────────────────────────────────────────────

  private sendGripperCommand(position: number): void {
    const command: GripperCommandMessage = {
      type: 'gripper_command',
      position,
    };
    this.connectionManager.send(command);
  }

  private clampPosition(value: number): number {
    return Math.max(GRIPPER_MIN, Math.min(GRIPPER_MAX, value));
  }

  private formatPosition(value: number): string {
    return value.toFixed(2) + ' rad';
  }

  private updateDisplay(): void {
    if (this.sliderElement) {
      this.sliderElement.value = String(this.currentPosition);
      this.sliderElement.setAttribute('aria-valuenow', String(this.currentPosition));
    }
    if (this.valueDisplay) {
      this.valueDisplay.textContent = this.formatPosition(this.currentPosition);
    }
  }

  private setControlsDisabled(disabled: boolean): void {
    if (this.sliderElement) {
      this.sliderElement.disabled = disabled;
    }
    if (this.openButton) {
      this.openButton.disabled = disabled;
    }
    if (this.closeButton) {
      this.closeButton.disabled = disabled;
    }
  }
}
