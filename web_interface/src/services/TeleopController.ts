/**
 * TeleopController — Captures keyboard and gamepad input for real-time
 * teleoperation of the SO-100 arm.
 *
 * - Keyboard: WASD for XY, Q/E for Z, arrows for wrist orientation
 * - Gamepad: Left stick XY, right stick Z, triggers for gripper
 * - 10% stick deadzone threshold
 * - Sends velocity commands at 20 Hz while inputs are active
 * - Sends zero-velocity within 50ms of all inputs released
 * - Applies configurable velocity scale factor
 * - Respects teleop mode enabled/disabled state
 *
 * Requirements: 5.1, 5.2, 5.3, 5.7
 */

import type { TeleopVelocityMessage } from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Command rate in Hz */
const COMMAND_RATE_HZ = 20;

/** Interval between commands in ms */
const COMMAND_INTERVAL_MS = 1000 / COMMAND_RATE_HZ; // 50ms

/** Timeout to send zero-velocity after all inputs released (ms) */
const ZERO_VELOCITY_TIMEOUT_MS = 50;

/** Stick deadzone as fraction of full axis range */
const DEADZONE_THRESHOLD = 0.1;

/** Wrist orientation rate in radians per second (5 degrees/s) */
const WRIST_ORIENTATION_RATE = (5 * Math.PI) / 180;

// ─── Types ──────────────────────────────────────────────────────────────────

/** Callback to send a velocity command */
export type SendCommandCallback = (message: TeleopVelocityMessage) => void;

/** Keys tracked for teleoperation */
export type TeleopKey =
  | 'KeyW'
  | 'KeyA'
  | 'KeyS'
  | 'KeyD'
  | 'KeyQ'
  | 'KeyE'
  | 'ArrowUp'
  | 'ArrowDown'
  | 'ArrowLeft'
  | 'ArrowRight';

const TRACKED_KEYS: Set<string> = new Set([
  'KeyW',
  'KeyA',
  'KeyS',
  'KeyD',
  'KeyQ',
  'KeyE',
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
]);

// ─── Utility Functions (exported for testing) ────────────────────────────────

/**
 * Apply deadzone to a gamepad axis value.
 * If |value| < threshold, returns 0. Otherwise returns the value as-is.
 */
export function applyDeadzone(value: number, threshold: number = DEADZONE_THRESHOLD): number {
  if (Math.abs(value) < threshold) {
    return 0;
  }
  return value;
}

/**
 * Compute velocity vector from a set of held keyboard keys and a velocity scale factor.
 *
 * Keyboard mapping:
 * - D/A → +X / -X linear velocity
 * - W/S → +Y / -Y linear velocity
 * - Q/E → +Z / -Z linear velocity (Q = up, E = down)
 * - ↑/↓ → Wrist pitch (angular.x) at ±5°/s × scale
 * - ←/→ → Wrist roll (angular.y) at ±5°/s × scale
 */
export function computeKeyboardVelocity(
  heldKeys: Set<string>,
  velocityScale: number
): { linear: [number, number, number]; angular: [number, number, number] } {
  // Linear velocity from WASD + Q/E
  const linearX = ((heldKeys.has('KeyD') ? 1 : 0) - (heldKeys.has('KeyA') ? 1 : 0)) * velocityScale;
  const linearY = ((heldKeys.has('KeyW') ? 1 : 0) - (heldKeys.has('KeyS') ? 1 : 0)) * velocityScale;
  const linearZ = ((heldKeys.has('KeyQ') ? 1 : 0) - (heldKeys.has('KeyE') ? 1 : 0)) * velocityScale;

  // Angular velocity from arrow keys (wrist orientation at 5°/s × scale)
  const angularX =
    ((heldKeys.has('ArrowUp') ? 1 : 0) - (heldKeys.has('ArrowDown') ? 1 : 0)) *
    WRIST_ORIENTATION_RATE *
    velocityScale;
  const angularY =
    ((heldKeys.has('ArrowRight') ? 1 : 0) - (heldKeys.has('ArrowLeft') ? 1 : 0)) *
    WRIST_ORIENTATION_RATE *
    velocityScale;
  const angularZ = 0;

  return {
    linear: [linearX, linearY, linearZ],
    angular: [angularX, angularY, angularZ],
  };
}

/**
 * Compute velocity vector from gamepad state.
 *
 * Gamepad mapping:
 * - Left stick X → X Cartesian velocity
 * - Left stick Y → Y Cartesian velocity (inverted: stick up = -1 axis = +Y)
 * - Right stick Y → Z Cartesian velocity (inverted: stick up = -1 axis = +Z)
 * - Left trigger (axis or button) → Gripper close (-1)
 * - Right trigger (axis or button) → Gripper open (+1)
 */
export function computeGamepadVelocity(
  leftStickX: number,
  leftStickY: number,
  rightStickY: number,
  leftTrigger: number,
  rightTrigger: number,
  velocityScale: number
): { linear: [number, number, number]; angular: [number, number, number]; gripper: number } {
  const lx = applyDeadzone(leftStickX);
  const ly = applyDeadzone(leftStickY);
  const ry = applyDeadzone(rightStickY);

  // Invert Y axes (gamepad up = -1, we want +Y for forward / +Z for up)
  const linearX = lx * velocityScale;
  const linearY = -ly * velocityScale;
  const linearZ = -ry * velocityScale;

  // Gripper: right trigger opens (+1), left trigger closes (-1)
  const gripper = rightTrigger - leftTrigger;

  return {
    linear: [linearX, linearY, linearZ],
    angular: [0, 0, 0],
    gripper,
  };
}

// ─── TeleopController Class ─────────────────────────────────────────────────

export class TeleopController {
  private enabled = false;
  private velocityScale = 0.05;
  private sendCommand: SendCommandCallback;

  // Keyboard state
  private heldKeys: Set<string> = new Set();

  // Timers
  private commandIntervalId: ReturnType<typeof setInterval> | null = null;
  private zeroVelocityTimeoutId: ReturnType<typeof setTimeout> | null = null;

  // Bound event handlers (for removal)
  private readonly onKeyDown: (ev: KeyboardEvent) => void;
  private readonly onKeyUp: (ev: KeyboardEvent) => void;

  // Track whether we have active input (to manage the 20 Hz loop)
  private hasActiveInput = false;

  constructor(sendCommand: SendCommandCallback) {
    this.sendCommand = sendCommand;

    // Bind handlers
    this.onKeyDown = this.handleKeyDown.bind(this);
    this.onKeyUp = this.handleKeyUp.bind(this);
  }

  // ─── Public API ───────────────────────────────────────────────────────

  /** Enable teleoperation mode — start capturing inputs */
  enable(): void {
    if (this.enabled) return;
    this.enabled = true;
    this.attachKeyboardListeners();
    this.startCommandLoop();
  }

  /** Disable teleoperation mode — stop capturing and send zero velocity */
  disable(): void {
    if (!this.enabled) return;
    this.enabled = false;
    this.detachKeyboardListeners();
    this.stopCommandLoop();
    this.heldKeys.clear();
    this.hasActiveInput = false;

    // Send zero velocity immediately on disable
    this.sendZeroVelocity();
    this.clearZeroVelocityTimeout();
  }

  /** Check if teleop mode is enabled */
  isEnabled(): boolean {
    return this.enabled;
  }

  /** Get the current velocity scale factor */
  getVelocityScale(): number {
    return this.velocityScale;
  }

  /** Set velocity scale factor (clamped to 0.01 – 0.2) */
  setVelocityScale(scale: number): void {
    this.velocityScale = Math.max(0.01, Math.min(0.2, scale));
  }

  /** Cleanup all resources — call on destroy */
  dispose(): void {
    this.disable();
  }

  // ─── Private: Keyboard Handling ───────────────────────────────────────

  private attachKeyboardListeners(): void {
    if (typeof window !== 'undefined') {
      window.addEventListener('keydown', this.onKeyDown);
      window.addEventListener('keyup', this.onKeyUp);
    }
  }

  private detachKeyboardListeners(): void {
    if (typeof window !== 'undefined') {
      window.removeEventListener('keydown', this.onKeyDown);
      window.removeEventListener('keyup', this.onKeyUp);
    }
  }

  private handleKeyDown(ev: KeyboardEvent): void {
    if (!this.enabled) return;
    if (!TRACKED_KEYS.has(ev.code)) return;

    // Prevent default browser behavior for tracked keys
    ev.preventDefault();

    if (!this.heldKeys.has(ev.code)) {
      this.heldKeys.add(ev.code);
      this.onInputActive();
    }
  }

  private handleKeyUp(ev: KeyboardEvent): void {
    if (!this.enabled) return;
    if (!TRACKED_KEYS.has(ev.code)) return;

    ev.preventDefault();

    if (this.heldKeys.has(ev.code)) {
      this.heldKeys.delete(ev.code);
      this.checkInputReleased();
    }
  }

  // ─── Private: Gamepad Handling ────────────────────────────────────────

  /**
   * Read gamepad state. Called each tick of the command loop.
   * Returns null if no gamepad is connected or all axes are in deadzone.
   */
  private readGamepad(): {
    linear: [number, number, number];
    angular: [number, number, number];
    gripper: number;
  } | null {
    if (typeof navigator === 'undefined' || !navigator.getGamepads) {
      return null;
    }

    const gamepads = navigator.getGamepads();
    let gamepad: Gamepad | null = null;
    for (const gp of gamepads) {
      if (gp && gp.connected) {
        gamepad = gp;
        break;
      }
    }

    if (!gamepad) return null;

    // Standard gamepad mapping:
    // axes[0] = left stick X, axes[1] = left stick Y
    // axes[2] = right stick X, axes[3] = right stick Y
    const leftStickX = gamepad.axes[0] ?? 0;
    const leftStickY = gamepad.axes[1] ?? 0;
    const rightStickY = gamepad.axes[3] ?? 0;

    // Triggers: buttons[6] = left trigger, buttons[7] = right trigger
    const leftTrigger = gamepad.buttons[6]?.value ?? 0;
    const rightTrigger = gamepad.buttons[7]?.value ?? 0;

    const result = computeGamepadVelocity(
      leftStickX,
      leftStickY,
      rightStickY,
      leftTrigger,
      rightTrigger,
      this.velocityScale
    );

    // Check if gamepad has any meaningful input
    const hasInput =
      result.linear[0] !== 0 ||
      result.linear[1] !== 0 ||
      result.linear[2] !== 0 ||
      Math.abs(result.gripper) > 0;

    return hasInput ? result : null;
  }

  // ─── Private: Command Loop ────────────────────────────────────────────

  private startCommandLoop(): void {
    if (this.commandIntervalId !== null) return;

    this.commandIntervalId = setInterval(() => {
      this.tick();
    }, COMMAND_INTERVAL_MS);
  }

  private stopCommandLoop(): void {
    if (this.commandIntervalId !== null) {
      clearInterval(this.commandIntervalId);
      this.commandIntervalId = null;
    }
  }

  /**
   * Called at 20 Hz. Computes and sends velocity command
   * from combined keyboard + gamepad input.
   */
  private tick(): void {
    if (!this.enabled) return;

    const keyboard = computeKeyboardVelocity(this.heldKeys, this.velocityScale);
    const gamepad = this.readGamepad();

    // Combine keyboard and gamepad inputs (additive)
    const linear: [number, number, number] = [
      keyboard.linear[0] + (gamepad?.linear[0] ?? 0),
      keyboard.linear[1] + (gamepad?.linear[1] ?? 0),
      keyboard.linear[2] + (gamepad?.linear[2] ?? 0),
    ];
    const angular: [number, number, number] = [
      keyboard.angular[0] + (gamepad?.angular[0] ?? 0),
      keyboard.angular[1] + (gamepad?.angular[1] ?? 0),
      keyboard.angular[2] + (gamepad?.angular[2] ?? 0),
    ];

    const hasKeyboardInput = this.heldKeys.size > 0;
    const hasGamepadInput = gamepad !== null;
    const hasInput = hasKeyboardInput || hasGamepadInput;

    if (hasInput) {
      this.hasActiveInput = true;
      this.clearZeroVelocityTimeout();

      const message: TeleopVelocityMessage = {
        type: 'teleop_velocity',
        linear,
        angular,
      };

      if (gamepad && gamepad.gripper !== 0) {
        message.gripper = gamepad.gripper;
      }

      this.sendCommand(message);
    } else if (this.hasActiveInput) {
      // Input just released — schedule zero-velocity send
      this.hasActiveInput = false;
      this.scheduleZeroVelocity();
    }
  }

  // ─── Private: Input State Management ──────────────────────────────────

  private onInputActive(): void {
    this.clearZeroVelocityTimeout();
  }

  private checkInputReleased(): void {
    if (this.heldKeys.size === 0) {
      // All keyboard keys released — gamepad will be checked on next tick
      // But if no gamepad active, schedule zero velocity
      const gamepad = this.readGamepad();
      if (!gamepad) {
        this.hasActiveInput = false;
        this.scheduleZeroVelocity();
      }
    }
  }

  // ─── Private: Zero Velocity ───────────────────────────────────────────

  private scheduleZeroVelocity(): void {
    this.clearZeroVelocityTimeout();
    this.zeroVelocityTimeoutId = setTimeout(() => {
      this.sendZeroVelocity();
      this.zeroVelocityTimeoutId = null;
    }, ZERO_VELOCITY_TIMEOUT_MS);
  }

  private clearZeroVelocityTimeout(): void {
    if (this.zeroVelocityTimeoutId !== null) {
      clearTimeout(this.zeroVelocityTimeoutId);
      this.zeroVelocityTimeoutId = null;
    }
  }

  private sendZeroVelocity(): void {
    this.sendCommand({
      type: 'teleop_velocity',
      linear: [0, 0, 0],
      angular: [0, 0, 0],
    });
  }
}
