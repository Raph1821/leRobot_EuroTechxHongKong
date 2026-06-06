/**
 * CartesianControlPanel — End-effector Cartesian control for the SO-100 arm.
 *
 * Features:
 * - Numeric inputs for target position (x, y, z) constrained to [-0.5, 0.5]
 * - Numeric inputs for orientation (roll, pitch, yaw) constrained to [-3.14, 3.14]
 * - "Move To" button that sends Cartesian goal message
 * - Displays current end-effector position (3 decimal places) and orientation (2 decimal places)
 * - Updates FK display within 100ms of joint state update
 * - Shows error notifications for IK failures and timeouts
 * - Renders translucent target marker (opacity 0.4) in 3D viewer at goal position
 * - Removes marker on motion complete or fail
 *
 * Requirements: 3.4, 3.5, 3.6, 3.8, 3.9
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type { SceneSetup } from './SceneSetup';
import type {
  CartesianGoalMessage,
  EndEffectorPoseMessage,
  ServerMessage,
} from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Position input constraints (meters) */
const POSITION_MIN = -0.5;
const POSITION_MAX = 0.5;
const POSITION_STEP = 0.001;

/** Orientation input constraints (radians) */
const ORIENTATION_MIN = -3.14;
const ORIENTATION_MAX = 3.14;
const ORIENTATION_STEP = 0.01;

/** Error notification display duration (ms) */
const ERROR_DISPLAY_DURATION_MS = 5000;

/** Marker opacity for translucent target visualization */
const MARKER_OPACITY = 0.4;

/** Marker radius (meters) for the target sphere */
const MARKER_RADIUS = 0.015;

// ─── Interfaces ─────────────────────────────────────────────────────────────

export interface CartesianPanelState {
  /** Target position inputs [x, y, z] */
  targetPosition: [number, number, number];
  /** Target orientation inputs [roll, pitch, yaw] */
  targetOrientation: [number, number, number];
  /** Current end-effector position from FK */
  currentPosition: [number, number, number] | null;
  /** Current end-effector orientation from FK */
  currentOrientation: [number, number, number] | null;
  /** Whether the panel is disabled */
  disabled: boolean;
  /** Current error message, if any */
  errorMessage: string | null;
  /** Whether a motion is in progress */
  motionInProgress: boolean;
}

/**
 * Minimal 3D marker interface to avoid tight coupling to Three.js.
 * In production, this wraps a THREE.Mesh with SphereGeometry + MeshBasicMaterial.
 */
export interface TargetMarker {
  /** Set the marker position */
  setPosition(x: number, y: number, z: number): void;
  /** Get the underlying 3D object to add/remove from scene */
  getObject3D(): unknown;
  /** Dispose of geometry and material */
  dispose(): void;
}

// ─── CartesianControlPanel ──────────────────────────────────────────────────

export class CartesianControlPanel {
  private readonly connectionManager: ConnectionManager;
  private readonly sceneSetup: SceneSetup | null;

  private state: CartesianPanelState = {
    targetPosition: [0, 0, 0],
    targetOrientation: [0, 0, 0],
    currentPosition: null,
    currentOrientation: null,
    disabled: false,
    errorMessage: null,
    motionInProgress: false,
  };

  // DOM elements
  private container: HTMLElement | null = null;
  private positionInputs: { x: HTMLInputElement; y: HTMLInputElement; z: HTMLInputElement } | null = null;
  private orientationInputs: { roll: HTMLInputElement; pitch: HTMLInputElement; yaw: HTMLInputElement } | null = null;
  private moveButton: HTMLButtonElement | null = null;
  private currentPositionDisplay: HTMLElement | null = null;
  private currentOrientationDisplay: HTMLElement | null = null;
  private errorDisplay: HTMLElement | null = null;
  private errorTimer: ReturnType<typeof setTimeout> | null = null;

  // 3D target marker
  private targetMarker: TargetMarker | null = null;
  private markerFactory: (() => TargetMarker) | null = null;

  constructor(
    connectionManager: ConnectionManager,
    sceneSetup: SceneSetup | null = null,
    markerFactory?: () => TargetMarker,
  ) {
    this.connectionManager = connectionManager;
    this.sceneSetup = sceneSetup;
    this.markerFactory = markerFactory ?? null;

    // Listen for messages
    this.connectionManager.on('message', this.handleMessage);
    this.connectionManager.on('controlsDisabled', this.handleControlsDisabled);
    this.connectionManager.on('controlsEnabled', this.handleControlsEnabled);
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the panel into a DOM container.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('cartesian-control-panel');

    const heading = document.createElement('h3');
    heading.textContent = 'Cartesian Control';
    this.container.appendChild(heading);

    // Current FK display section
    this.createFKDisplay();

    // Target input section
    this.createTargetInputs();

    // Move button
    this.createMoveButton();

    // Error notification area
    this.createErrorDisplay();

    this.updateDisabledState();
  }

  /**
   * Remove the panel from the DOM and clean up resources.
   */
  unmount(): void {
    this.connectionManager.off('message', this.handleMessage);
    this.connectionManager.off('controlsDisabled', this.handleControlsDisabled);
    this.connectionManager.off('controlsEnabled', this.handleControlsEnabled);

    if (this.errorTimer) {
      clearTimeout(this.errorTimer);
      this.errorTimer = null;
    }

    this.removeTargetMarker();

    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('cartesian-control-panel');
    }

    this.container = null;
    this.positionInputs = null;
    this.orientationInputs = null;
    this.moveButton = null;
    this.currentPositionDisplay = null;
    this.currentOrientationDisplay = null;
    this.errorDisplay = null;
  }

  /**
   * Get the current panel state (for testing/external access).
   */
  getState(): Readonly<CartesianPanelState> {
    return { ...this.state };
  }

  /**
   * Check if a motion is currently in progress.
   */
  isMotionInProgress(): boolean {
    return this.state.motionInProgress;
  }

  /**
   * Programmatically set the panel disabled state (e.g., during replay).
   */
  setDisabled(disabled: boolean): void {
    this.state.disabled = disabled;
    this.updateDisabledState();
  }

  // ─── Message Handling ───────────────────────────────────────────────────

  private handleMessage = (message: ServerMessage): void => {
    switch (message.type) {
      case 'end_effector_pose':
        this.handleEndEffectorPose(message as EndEffectorPoseMessage);
        break;
      case 'error':
        this.handleError(message as { type: 'error'; code: string; message: string });
        break;
      case 'trajectory_status':
        this.handleTrajectoryStatus(message as { type: 'trajectory_status'; status: string; message: string });
        break;
    }
  };

  private handleEndEffectorPose(msg: EndEffectorPoseMessage): void {
    this.state.currentPosition = [...msg.position];
    this.state.currentOrientation = [...msg.orientation];
    this.updateFKDisplay();
  }

  private handleError(msg: { type: 'error'; code: string; message: string }): void {
    // Only handle IK-related errors
    if (msg.code === 'IK_NO_SOLUTION' || msg.code === 'IK_TIMEOUT') {
      this.state.errorMessage = msg.message;
      this.state.motionInProgress = false;
      this.showError(msg.message);
      this.removeTargetMarker();
    }
  }

  private handleTrajectoryStatus(msg: { type: 'trajectory_status'; status: string; message: string }): void {
    if (msg.status === 'succeeded' || msg.status === 'aborted' || msg.status === 'preempted') {
      this.state.motionInProgress = false;
      this.removeTargetMarker();
    }
  }

  private handleControlsDisabled = (): void => {
    this.state.disabled = true;
    this.updateDisabledState();
  };

  private handleControlsEnabled = (): void => {
    this.state.disabled = false;
    this.updateDisabledState();
  };

  // ─── UI Creation ────────────────────────────────────────────────────────

  private createFKDisplay(): void {
    const section = document.createElement('div');
    section.classList.add('cartesian-fk-display');

    const label = document.createElement('h4');
    label.textContent = 'Current End-Effector Pose';
    section.appendChild(label);

    this.currentPositionDisplay = document.createElement('div');
    this.currentPositionDisplay.classList.add('cartesian-current-position');
    this.currentPositionDisplay.textContent = 'Position: --';
    section.appendChild(this.currentPositionDisplay);

    this.currentOrientationDisplay = document.createElement('div');
    this.currentOrientationDisplay.classList.add('cartesian-current-orientation');
    this.currentOrientationDisplay.textContent = 'Orientation: --';
    section.appendChild(this.currentOrientationDisplay);

    this.container!.appendChild(section);
  }

  private createTargetInputs(): void {
    const section = document.createElement('div');
    section.classList.add('cartesian-target-inputs');

    // Position inputs
    const posLabel = document.createElement('h4');
    posLabel.textContent = 'Target Position (m)';
    section.appendChild(posLabel);

    const posRow = document.createElement('div');
    posRow.classList.add('cartesian-input-row');

    const xInput = this.createNumericInput('x', POSITION_MIN, POSITION_MAX, POSITION_STEP, 0);
    const yInput = this.createNumericInput('y', POSITION_MIN, POSITION_MAX, POSITION_STEP, 0);
    const zInput = this.createNumericInput('z', POSITION_MIN, POSITION_MAX, POSITION_STEP, 0);

    posRow.appendChild(xInput.wrapper);
    posRow.appendChild(yInput.wrapper);
    posRow.appendChild(zInput.wrapper);
    section.appendChild(posRow);

    this.positionInputs = { x: xInput.input, y: yInput.input, z: zInput.input };

    // Orientation inputs
    const oriLabel = document.createElement('h4');
    oriLabel.textContent = 'Target Orientation (rad)';
    section.appendChild(oriLabel);

    const oriRow = document.createElement('div');
    oriRow.classList.add('cartesian-input-row');

    const rollInput = this.createNumericInput('roll', ORIENTATION_MIN, ORIENTATION_MAX, ORIENTATION_STEP, 0);
    const pitchInput = this.createNumericInput('pitch', ORIENTATION_MIN, ORIENTATION_MAX, ORIENTATION_STEP, 0);
    const yawInput = this.createNumericInput('yaw', ORIENTATION_MIN, ORIENTATION_MAX, ORIENTATION_STEP, 0);

    oriRow.appendChild(rollInput.wrapper);
    oriRow.appendChild(pitchInput.wrapper);
    oriRow.appendChild(yawInput.wrapper);
    section.appendChild(oriRow);

    this.orientationInputs = { roll: rollInput.input, pitch: pitchInput.input, yaw: yawInput.input };

    this.container!.appendChild(section);
  }

  private createNumericInput(
    labelText: string,
    min: number,
    max: number,
    step: number,
    defaultValue: number,
  ): { wrapper: HTMLDivElement; input: HTMLInputElement } {
    const wrapper = document.createElement('div');
    wrapper.classList.add('cartesian-input-group');

    const label = document.createElement('label');
    label.textContent = labelText;
    label.classList.add('cartesian-input-label');

    const input = document.createElement('input');
    input.type = 'number';
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(defaultValue);
    input.classList.add('cartesian-input');
    input.dataset.field = labelText;

    input.addEventListener('input', this.handleInputChange);

    wrapper.appendChild(label);
    wrapper.appendChild(input);

    return { wrapper, input };
  }

  private createMoveButton(): void {
    this.moveButton = document.createElement('button');
    this.moveButton.type = 'button';
    this.moveButton.textContent = 'Move To';
    this.moveButton.classList.add('cartesian-move-button');
    this.moveButton.addEventListener('click', this.handleMoveTo);
    this.container!.appendChild(this.moveButton);
  }

  private createErrorDisplay(): void {
    this.errorDisplay = document.createElement('div');
    this.errorDisplay.classList.add('cartesian-error-display');
    this.errorDisplay.style.display = 'none';
    this.container!.appendChild(this.errorDisplay);
  }

  // ─── Event Handlers ─────────────────────────────────────────────────────

  private handleInputChange = (): void => {
    if (!this.positionInputs || !this.orientationInputs) return;

    this.state.targetPosition = [
      this.clamp(parseFloat(this.positionInputs.x.value) || 0, POSITION_MIN, POSITION_MAX),
      this.clamp(parseFloat(this.positionInputs.y.value) || 0, POSITION_MIN, POSITION_MAX),
      this.clamp(parseFloat(this.positionInputs.z.value) || 0, POSITION_MIN, POSITION_MAX),
    ];

    this.state.targetOrientation = [
      this.clamp(parseFloat(this.orientationInputs.roll.value) || 0, ORIENTATION_MIN, ORIENTATION_MAX),
      this.clamp(parseFloat(this.orientationInputs.pitch.value) || 0, ORIENTATION_MIN, ORIENTATION_MAX),
      this.clamp(parseFloat(this.orientationInputs.yaw.value) || 0, ORIENTATION_MIN, ORIENTATION_MAX),
    ];
  };

  private handleMoveTo = (): void => {
    if (this.state.disabled || this.state.motionInProgress) return;

    // Read and clamp current input values
    this.handleInputChange();

    const goal: CartesianGoalMessage = {
      type: 'cartesian_goal',
      position: [...this.state.targetPosition],
      orientation: [...this.state.targetOrientation],
    };

    // Send the goal message
    const sent = this.connectionManager.send(goal);
    if (sent) {
      this.state.motionInProgress = true;
      this.state.errorMessage = null;
      this.hideError();
      this.addTargetMarker(this.state.targetPosition);
    }
  };

  // ─── Display Updates ────────────────────────────────────────────────────

  private updateFKDisplay(): void {
    if (this.currentPositionDisplay && this.state.currentPosition) {
      const [x, y, z] = this.state.currentPosition;
      this.currentPositionDisplay.textContent =
        `Position: x=${x.toFixed(3)}, y=${y.toFixed(3)}, z=${z.toFixed(3)} m`;
    }

    if (this.currentOrientationDisplay && this.state.currentOrientation) {
      const [roll, pitch, yaw] = this.state.currentOrientation;
      this.currentOrientationDisplay.textContent =
        `Orientation: roll=${roll.toFixed(2)}, pitch=${pitch.toFixed(2)}, yaw=${yaw.toFixed(2)} rad`;
    }
  }

  private showError(message: string): void {
    if (!this.errorDisplay) return;

    this.errorDisplay.textContent = message;
    this.errorDisplay.style.display = 'block';
    this.errorDisplay.classList.add('cartesian-error-visible');

    // Clear previous timer
    if (this.errorTimer) {
      clearTimeout(this.errorTimer);
    }

    // Auto-hide after duration
    this.errorTimer = setTimeout(() => {
      this.hideError();
    }, ERROR_DISPLAY_DURATION_MS);
  }

  private hideError(): void {
    if (!this.errorDisplay) return;
    this.errorDisplay.style.display = 'none';
    this.errorDisplay.classList.remove('cartesian-error-visible');
    this.state.errorMessage = null;
  }

  private updateDisabledState(): void {
    const disabled = this.state.disabled;

    if (this.positionInputs) {
      this.positionInputs.x.disabled = disabled;
      this.positionInputs.y.disabled = disabled;
      this.positionInputs.z.disabled = disabled;
    }

    if (this.orientationInputs) {
      this.orientationInputs.roll.disabled = disabled;
      this.orientationInputs.pitch.disabled = disabled;
      this.orientationInputs.yaw.disabled = disabled;
    }

    if (this.moveButton) {
      this.moveButton.disabled = disabled || this.state.motionInProgress;
    }
  }

  // ─── 3D Target Marker ──────────────────────────────────────────────────

  private addTargetMarker(position: [number, number, number]): void {
    // Remove any existing marker first
    this.removeTargetMarker();

    if (!this.sceneSetup || !this.markerFactory) return;

    this.targetMarker = this.markerFactory();
    this.targetMarker.setPosition(position[0], position[1], position[2]);

    const obj = this.targetMarker.getObject3D();
    if (obj) {
      this.sceneSetup.add(obj as import('three').Object3D);
    }
  }

  private removeTargetMarker(): void {
    if (!this.targetMarker) return;

    if (this.sceneSetup) {
      const obj = this.targetMarker.getObject3D();
      if (obj) {
        this.sceneSetup.remove(obj as import('three').Object3D);
      }
    }

    this.targetMarker.dispose();
    this.targetMarker = null;
  }

  // ─── Utilities ──────────────────────────────────────────────────────────

  private clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
  }
}

/**
 * Default factory for creating a translucent sphere marker using Three.js.
 * This is provided as a separate export so it can be used when Three.js is available.
 */
export function createDefaultMarkerFactory(THREE: {
  SphereGeometry: new (radius: number, widthSegments: number, heightSegments: number) => unknown;
  MeshBasicMaterial: new (params: { color: number; transparent: boolean; opacity: number }) => unknown;
  Mesh: new (geometry: unknown, material: unknown) => unknown;
}): () => TargetMarker {
  return () => {
    const geometry = new THREE.SphereGeometry(MARKER_RADIUS, 16, 16);
    const material = new THREE.MeshBasicMaterial({
      color: 0x00ff88,
      transparent: true,
      opacity: MARKER_OPACITY,
    });
    const mesh = new THREE.Mesh(geometry, material) as unknown as {
      position: { set(x: number, y: number, z: number): void };
      geometry: { dispose(): void };
      material: { dispose(): void };
    };

    return {
      setPosition(x: number, y: number, z: number): void {
        mesh.position.set(x, y, z);
      },
      getObject3D(): unknown {
        return mesh;
      },
      dispose(): void {
        mesh.geometry.dispose();
        mesh.material.dispose();
      },
    };
  };
}
