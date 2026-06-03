/**
 * Property-based test for Keyboard-to-Velocity Mapping with Scaling (Property 7)
 *
 * **Validates: Requirements 5.1, 5.6**
 *
 * For any set of held keyboard keys from {W, A, S, D, Q, E, ↑, ↓, ←, →}
 * and for any velocity scale factor in [0.01, 0.2], the output velocity vector SHALL have:
 *   linear.x = (D - A) × scale
 *   linear.y = (W - S) × scale
 *   linear.z = (Q - E) × scale
 *   angular.x = (↑ - ↓) × 5°/s × scale
 *   angular.y = (→ - ←) × 5°/s × scale
 *   angular.z = 0
 * When no keys are held, the output SHALL be a zero vector.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { computeKeyboardVelocity } from './TeleopController';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Wrist orientation rate: 5 degrees/s in radians */
const WRIST_ORIENTATION_RATE = (5 * Math.PI) / 180;

/** All tracked teleop keys */
const ALL_KEYS = [
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
] as const;

// ─── Helper ─────────────────────────────────────────────────────────────────

/** Compute the expected velocity from a key set and scale using the defined formula */
function expectedVelocity(
  keys: Set<string>,
  scale: number
): { linear: [number, number, number]; angular: [number, number, number] } {
  const d = keys.has('KeyD') ? 1 : 0;
  const a = keys.has('KeyA') ? 1 : 0;
  const w = keys.has('KeyW') ? 1 : 0;
  const s = keys.has('KeyS') ? 1 : 0;
  const q = keys.has('KeyQ') ? 1 : 0;
  const e = keys.has('KeyE') ? 1 : 0;
  const up = keys.has('ArrowUp') ? 1 : 0;
  const down = keys.has('ArrowDown') ? 1 : 0;
  const right = keys.has('ArrowRight') ? 1 : 0;
  const left = keys.has('ArrowLeft') ? 1 : 0;

  return {
    linear: [
      (d - a) * scale,
      (w - s) * scale,
      (q - e) * scale,
    ],
    angular: [
      (up - down) * WRIST_ORIENTATION_RATE * scale,
      (right - left) * WRIST_ORIENTATION_RATE * scale,
      0,
    ],
  };
}

// ─── Generators ─────────────────────────────────────────────────────────────

/** Generate a subset of tracked teleop keys */
const keySubset = fc.subarray([...ALL_KEYS], { minLength: 0 });

/** Generate a velocity scale in [0.01, 0.2] */
const velocityScale = fc.double({ min: 0.01, max: 0.2, noNaN: true });

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: web-control-expansion, Property 7: Keyboard-to-velocity mapping with scaling', () => {
  /**
   * Property 7: Keyboard-to-velocity mapping with scaling
   * **Validates: Requirements 5.1, 5.6**
   */

  it('should produce velocity matching the defined formula for any key set and scale', () => {
    fc.assert(
      fc.property(
        keySubset,
        velocityScale,
        (keys, scale) => {
          const heldKeys = new Set(keys);
          const result = computeKeyboardVelocity(heldKeys, scale);
          const expected = expectedVelocity(heldKeys, scale);

          // Linear velocity components
          expect(result.linear[0]).toBeCloseTo(expected.linear[0], 10);
          expect(result.linear[1]).toBeCloseTo(expected.linear[1], 10);
          expect(result.linear[2]).toBeCloseTo(expected.linear[2], 10);

          // Angular velocity components
          expect(result.angular[0]).toBeCloseTo(expected.angular[0], 10);
          expect(result.angular[1]).toBeCloseTo(expected.angular[1], 10);
          expect(result.angular[2]).toBe(0);
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should produce zero vector when no keys are held', () => {
    fc.assert(
      fc.property(
        velocityScale,
        (scale) => {
          const heldKeys = new Set<string>();
          const result = computeKeyboardVelocity(heldKeys, scale);

          expect(result.linear[0]).toBe(0);
          expect(result.linear[1]).toBe(0);
          expect(result.linear[2]).toBe(0);
          expect(result.angular[0]).toBe(0);
          expect(result.angular[1]).toBe(0);
          expect(result.angular[2]).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should scale linearly with the velocity scale factor', () => {
    fc.assert(
      fc.property(
        keySubset.filter(keys => keys.length > 0),
        velocityScale,
        fc.double({ min: 1.5, max: 3.0, noNaN: true }),
        (keys, scale, multiplier) => {
          const heldKeys = new Set(keys);
          const scaledScale = Math.min(scale * multiplier, 0.2);

          const result1 = computeKeyboardVelocity(heldKeys, scale);
          const result2 = computeKeyboardVelocity(heldKeys, scaledScale);

          // Velocity should be proportional to scale factor
          const ratio = scaledScale / scale;

          if (result1.linear[0] !== 0) {
            expect(result2.linear[0] / result1.linear[0]).toBeCloseTo(ratio, 5);
          }
          if (result1.linear[1] !== 0) {
            expect(result2.linear[1] / result1.linear[1]).toBeCloseTo(ratio, 5);
          }
          if (result1.linear[2] !== 0) {
            expect(result2.linear[2] / result1.linear[2]).toBeCloseTo(ratio, 5);
          }
          if (result1.angular[0] !== 0) {
            expect(result2.angular[0] / result1.angular[0]).toBeCloseTo(ratio, 5);
          }
          if (result1.angular[1] !== 0) {
            expect(result2.angular[1] / result1.angular[1]).toBeCloseTo(ratio, 5);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should produce opposing keys cancelling each other out', () => {
    fc.assert(
      fc.property(
        velocityScale,
        (scale) => {
          // W and S together → linearY = 0
          const wsKeys = new Set(['KeyW', 'KeyS']);
          const wsResult = computeKeyboardVelocity(wsKeys, scale);
          expect(wsResult.linear[1]).toBe(0);

          // A and D together → linearX = 0
          const adKeys = new Set(['KeyA', 'KeyD']);
          const adResult = computeKeyboardVelocity(adKeys, scale);
          expect(adResult.linear[0]).toBe(0);

          // Q and E together → linearZ = 0
          const qeKeys = new Set(['KeyQ', 'KeyE']);
          const qeResult = computeKeyboardVelocity(qeKeys, scale);
          expect(qeResult.linear[2]).toBe(0);

          // ↑ and ↓ together → angularX = 0
          const udKeys = new Set(['ArrowUp', 'ArrowDown']);
          const udResult = computeKeyboardVelocity(udKeys, scale);
          expect(udResult.angular[0]).toBe(0);

          // ← and → together → angularY = 0
          const lrKeys = new Set(['ArrowLeft', 'ArrowRight']);
          const lrResult = computeKeyboardVelocity(lrKeys, scale);
          expect(lrResult.angular[1]).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });
});
