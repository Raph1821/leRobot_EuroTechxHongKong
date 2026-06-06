/**
 * Property-based test for UI Slider Synchronization with Joint State (Property 9)
 *
 * **Validates: Requirements 8.7, 8.4**
 *
 * For any valid joint state vector (6 values each within their respective joint limits),
 * applying it to the UI state SHALL result in every slider's visual position reflecting
 * the corresponding joint angle value, and the displayed numeric value SHALL equal the
 * joint angle rounded to two decimal places.
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { JointControlPanel } from './JointControlPanel';
import { JOINT_CONFIGS, ARM_JOINT_NAMES, ALL_JOINT_NAMES } from '../types';
import type { JointStateMessage, ConnectionState } from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

/**
 * Minimal mock of ConnectionManager to satisfy JointControlPanel constructor.
 * Provides event registration and a controllable connection state.
 */
class MockConnectionManager {
  private listeners: Map<string, Array<(...args: unknown[]) => void>> = new Map();
  private state: ConnectionState = 'connected';

  on(event: string, handler: (...args: unknown[]) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(handler);
  }

  off(event: string, handler: (...args: unknown[]) => void): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      const idx = handlers.indexOf(handler);
      if (idx >= 0) handlers.splice(idx, 1);
    }
  }

  emit(event: string, ...args: unknown[]): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      for (const handler of handlers) {
        handler(...args);
      }
    }
  }

  getState(): ConnectionState {
    return this.state;
  }

  setState(state: ConnectionState): void {
    this.state = state;
  }

  send(_message: unknown): void {
    // no-op for testing
  }
}

// ─── Generators ─────────────────────────────────────────────────────────────

/**
 * Generator for a valid joint state vector: 6 floats each within their respective limits.
 */
function validJointPositionsArb(): fc.Arbitrary<number[]> {
  const jointArbitraries = JOINT_CONFIGS.map((config) =>
    fc.double({ min: config.lowerLimit, max: config.upperLimit, noNaN: true })
  );
  return fc.tuple(...(jointArbitraries as [fc.Arbitrary<number>, fc.Arbitrary<number>, fc.Arbitrary<number>, fc.Arbitrary<number>, fc.Arbitrary<number>, fc.Arbitrary<number>]));
}

/**
 * Build a JointStateMessage from a positions array.
 */
function buildJointStateMessage(positions: number[]): JointStateMessage {
  return {
    type: 'joint_state',
    timestamp: Date.now() / 1000,
    joints: {
      names: [...ALL_JOINT_NAMES],
      positions,
      velocities: positions.map(() => 0),
      efforts: positions.map(() => 0),
    },
  };
}

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: so100-isaacsim-web-control, Property 9: UI slider synchronization with joint state', () => {
  let panel: JointControlPanel;
  let mockConnectionManager: MockConnectionManager;
  let container: HTMLDivElement;

  beforeEach(() => {
    // Create a minimal DOM container
    container = document.createElement('div');
    mockConnectionManager = new MockConnectionManager();
    panel = new JointControlPanel(mockConnectionManager as unknown as import('../services/ConnectionManager').ConnectionManager);
    panel.mount(container);

    // Enable controls
    mockConnectionManager.emit('controlsEnabled');
  });

  /**
   * Property 9: UI slider synchronization with joint state
   * **Validates: Requirements 8.7, 8.4**
   *
   * For any valid joint state vector, all slider positions match corresponding
   * joint angle values, and numeric displays show values rounded to 2 decimal places.
   */
  it('should synchronize all slider positions with joint state values', () => {
    fc.assert(
      fc.property(
        validJointPositionsArb(),
        (positions) => {
          const jointStateMsg = buildJointStateMessage(positions);
          panel.updateFromJointState(jointStateMsg);

          // Verify each arm joint slider reflects the corresponding position
          for (let i = 0; i < ARM_JOINT_NAMES.length; i++) {
            const jointName = ARM_JOINT_NAMES[i];
            const expectedPosition = positions[i];

            const state = panel.getJointState(jointName);
            expect(state).toBeDefined();
            expect(state!.position).toBeCloseTo(expectedPosition, 10);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should display numeric values rounded to exactly 2 decimal places', () => {
    fc.assert(
      fc.property(
        validJointPositionsArb(),
        (positions) => {
          const jointStateMsg = buildJointStateMessage(positions);
          panel.updateFromJointState(jointStateMsg);

          // Check that numeric display elements show the value rounded to 2 decimal places
          for (let i = 0; i < ARM_JOINT_NAMES.length; i++) {
            const jointName = ARM_JOINT_NAMES[i];
            const expectedPosition = positions[i];

            // Find the value display element in the DOM
            const wrapper = container.querySelector(`[data-joint="${jointName}"]`) as HTMLDivElement;
            expect(wrapper).not.toBeNull();

            const valueDisplay = wrapper.querySelector('.joint-value') as HTMLSpanElement;
            expect(valueDisplay).not.toBeNull();

            // The displayed text should be the value rounded to 2 decimal places + ' rad'
            const expectedText = expectedPosition.toFixed(2) + ' rad';
            expect(valueDisplay.textContent).toBe(expectedText);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should synchronize slider input element values with joint positions', () => {
    fc.assert(
      fc.property(
        validJointPositionsArb(),
        (positions) => {
          const jointStateMsg = buildJointStateMessage(positions);
          panel.updateFromJointState(jointStateMsg);

          // Verify that the slider input element values match the positions
          for (let i = 0; i < ARM_JOINT_NAMES.length; i++) {
            const jointName = ARM_JOINT_NAMES[i];
            const expectedPosition = positions[i];

            const wrapper = container.querySelector(`[data-joint="${jointName}"]`) as HTMLDivElement;
            expect(wrapper).not.toBeNull();

            const slider = wrapper.querySelector('.joint-slider') as HTMLInputElement;
            expect(slider).not.toBeNull();

            // Slider value should match the position (as string)
            expect(parseFloat(slider.value)).toBeCloseTo(expectedPosition, 10);
          }
        }
      ),
      { numRuns: 200 }
    );
  });
});
