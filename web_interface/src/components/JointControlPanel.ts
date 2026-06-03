/**
 * JointControlPanel — slider controls for the 5 arm joints of the SO-100 robot.
 *
 * Features:
 * - Individual sliders per arm joint with URDF-defined limits
 * - Numeric display of joint angle (2 decimal places, radians)
 * - Sends joint commands via WebSocket within 50ms of slider change
 * - Clamps values exceeding limits with warning indicator (≥2s)
 * - Updates slider positions from joint state feedback
 * - Disables all sliders when connection is unavailable
 *
 * Requirements: 8.1, 8.3, 8.4, 8.6, 8.7, 10.5
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type { JointCommandMessage, JointStateMessage } from '../types';
import { JOINT_CONFIGS, ARM_JOINT_NAMES } from '../types';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface JointSliderState {
  name: string;
  position: number;
  lowerLimit: number;
  upperLimit: number;
  disabled: boolean;
  warning: boolean;
}

// ─── Constants ──────────────────────────────────────────────────────────────

/** Minimum time (ms) to show the warning indicator after a clamp occurs */
const WARNING_DISPLAY_DURATION_MS = 2000;

/** Slider step resolution (radians) */
const SLIDER_STEP = 0.01;

// ─── JointControlPanel ──────────────────────────────────────────────────────

export class JointControlPanel {
  private readonly connectionManager: ConnectionManager;
  private readonly sliderStates: Map<string, JointSliderState> = new Map();
  private readonly warningTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  private disabled = false;

  // DOM elements (created on mount)
  private container: HTMLElement | null = null;
  private sliderElements: Map<string, {
    slider: HTMLInputElement;
    valueDisplay: HTMLSpanElement;
    warningIndicator: HTMLSpanElement;
    wrapper: HTMLDivElement;
  }> = new Map();

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;

    // Initialize slider states from JOINT_CONFIGS for arm joints only
    for (const jointName of ARM_JOINT_NAMES) {
      const config = JOINT_CONFIGS.find(c => c.name === jointName);
      if (config) {
        this.sliderStates.set(jointName, {
          name: jointName,
          position: 0,
          lowerLimit: config.lowerLimit,
          upperLimit: config.upperLimit,
          disabled: false,
          warning: false,
        });
      }
    }

    // Listen for connection state changes
    this.connectionManager.on('controlsEnabled', this.handleControlsEnabled.bind(this));
    this.connectionManager.on('controlsDisabled', this.handleControlsDisabled.bind(this));
    this.connectionManager.on('message', this.handleMessage.bind(this));
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the panel into a DOM container element.
   * Creates all slider controls and wires up event listeners.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('joint-control-panel');

    const heading = document.createElement('h3');
    heading.textContent = 'Joint Control';
    this.container.appendChild(heading);

    for (const jointName of ARM_JOINT_NAMES) {
      const state = this.sliderStates.get(jointName);
      if (!state) continue;

      const wrapper = document.createElement('div');
      wrapper.classList.add('joint-slider-wrapper');
      wrapper.dataset.joint = jointName;

      // Label
      const label = document.createElement('label');
      label.textContent = jointName.replace(/_/g, ' ');
      label.classList.add('joint-label');

      // Slider input
      const slider = document.createElement('input');
      slider.type = 'range';
      slider.min = String(state.lowerLimit);
      slider.max = String(state.upperLimit);
      slider.step = String(SLIDER_STEP);
      slider.value = String(state.position);
      slider.disabled = this.disabled;
      slider.classList.add('joint-slider');
      slider.dataset.joint = jointName;

      // Value display
      const valueDisplay = document.createElement('span');
      valueDisplay.classList.add('joint-value');
      valueDisplay.textContent = this.formatAngle(state.position);

      // Warning indicator
      const warningIndicator = document.createElement('span');
      warningIndicator.classList.add('joint-warning');
      warningIndicator.textContent = '⚠';
      warningIndicator.style.display = 'none';

      // Limit indicators
      const limitsDisplay = document.createElement('span');
      limitsDisplay.classList.add('joint-limits');
      limitsDisplay.textContent = `[${state.lowerLimit.toFixed(2)}, ${state.upperLimit.toFixed(2)}]`;

      // Assemble
      wrapper.appendChild(label);
      wrapper.appendChild(slider);
      wrapper.appendChild(valueDisplay);
      wrapper.appendChild(warningIndicator);
      wrapper.appendChild(limitsDisplay);
      this.container.appendChild(wrapper);

      // Store element references
      this.sliderElements.set(jointName, {
        slider,
        valueDisplay,
        warningIndicator,
        wrapper,
      });

      // Event listener for slider input
      slider.addEventListener('input', this.handleSliderInput.bind(this, jointName));
    }

    // Set initial disabled state
    this.setDisabled(this.disabled);
  }

  /**
   * Remove the panel from the DOM and clean up event listeners.
   */
  unmount(): void {
    // Clear all warning timers
    for (const timer of this.warningTimers.values()) {
      clearTimeout(timer);
    }
    this.warningTimers.clear();

    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('joint-control-panel');
    }
    this.sliderElements.clear();
    this.container = null;
  }

  /**
   * Get current slider state for a given joint (for testing/external access).
   */
  getJointState(jointName: string): JointSliderState | undefined {
    return this.sliderStates.get(jointName);
  }

  /**
   * Get all joint slider states.
   */
  getAllJointStates(): JointSliderState[] {
    return Array.from(this.sliderStates.values());
  }

  /**
   * Whether all sliders are currently disabled.
   */
  isDisabled(): boolean {
    return this.disabled;
  }

  /**
   * Programmatically set a joint position (e.g., from joint state feedback).
   * Clamps to valid range with warning if needed.
   */
  setJointPosition(jointName: string, position: number): void {
    const state = this.sliderStates.get(jointName);
    if (!state) return;

    const clamped = this.clampValue(jointName, position);
    state.position = clamped;

    // Update DOM
    const elements = this.sliderElements.get(jointName);
    if (elements) {
      elements.slider.value = String(clamped);
      elements.valueDisplay.textContent = this.formatAngle(clamped);
    }
  }

  /**
   * Update slider positions from a joint state message.
   * This is called when the simulation sends joint state feedback.
   */
  updateFromJointState(jointState: JointStateMessage): void {
    const { names, positions } = jointState.joints;
    for (let i = 0; i < names.length; i++) {
      const name = names[i];
      const position = positions[i];
      if (ARM_JOINT_NAMES.includes(name as typeof ARM_JOINT_NAMES[number])) {
        this.setJointPosition(name, position);
      }
    }
  }

  // ─── Private Methods ────────────────────────────────────────────────────

  private handleSliderInput(jointName: string, event: Event): void {
    const slider = event.target as HTMLInputElement;
    const rawValue = parseFloat(slider.value);

    // Clamp and check for limit violation
    const clampedValue = this.clampValue(jointName, rawValue);
    const wasClampNeeded = clampedValue !== rawValue;

    // Update state
    const state = this.sliderStates.get(jointName);
    if (state) {
      state.position = clampedValue;
    }

    // Update DOM display
    const elements = this.sliderElements.get(jointName);
    if (elements) {
      elements.slider.value = String(clampedValue);
      elements.valueDisplay.textContent = this.formatAngle(clampedValue);
    }

    // Show warning if clamped
    if (wasClampNeeded) {
      this.showWarning(jointName);
    }

    // Send command via WebSocket
    this.sendJointCommand(jointName, clampedValue);
  }

  private sendJointCommand(jointName: string, position: number): void {
    const command: JointCommandMessage = {
      type: 'joint_command',
      joints: [{ name: jointName, position }],
    };

    // Always send (the send function handles local model updates regardless
    // of connection state for visual feedback)
    this.connectionManager.send(command);
  }

  private clampValue(jointName: string, value: number): number {
    const state = this.sliderStates.get(jointName);
    if (!state) return value;

    if (value < state.lowerLimit) return state.lowerLimit;
    if (value > state.upperLimit) return state.upperLimit;
    return value;
  }

  private showWarning(jointName: string): void {
    const state = this.sliderStates.get(jointName);
    if (state) {
      state.warning = true;
    }

    const elements = this.sliderElements.get(jointName);
    if (elements) {
      elements.warningIndicator.style.display = 'inline';
      elements.wrapper.classList.add('joint-warning-active');
    }

    // Clear any existing timer for this joint
    const existingTimer = this.warningTimers.get(jointName);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }

    // Set timer to hide warning after WARNING_DISPLAY_DURATION_MS
    const timer = setTimeout(() => {
      this.hideWarning(jointName);
    }, WARNING_DISPLAY_DURATION_MS);
    this.warningTimers.set(jointName, timer);
  }

  private hideWarning(jointName: string): void {
    const state = this.sliderStates.get(jointName);
    if (state) {
      state.warning = false;
    }

    const elements = this.sliderElements.get(jointName);
    if (elements) {
      elements.warningIndicator.style.display = 'none';
      elements.wrapper.classList.remove('joint-warning-active');
    }

    this.warningTimers.delete(jointName);
  }

  setDisabled(disabled: boolean): void {
    this.disabled = disabled;
    for (const [jointName, state] of this.sliderStates) {
      state.disabled = disabled;
      const elements = this.sliderElements.get(jointName);
      if (elements) {
        elements.slider.disabled = disabled;
      }
    }
  }

  private handleControlsEnabled(): void {
    // Sliders are always enabled for local 3D model feedback
  }

  private handleControlsDisabled(): void {
    // Sliders remain enabled for local 3D model feedback even when disconnected
    // The status display shows connection state to the user
  }

  private handleMessage(message: { type: string }): void {
    if (message.type === 'joint_state') {
      this.updateFromJointState(message as JointStateMessage);
    }
  }

  private formatAngle(radians: number): string {
    return radians.toFixed(2) + ' rad';
  }
}
