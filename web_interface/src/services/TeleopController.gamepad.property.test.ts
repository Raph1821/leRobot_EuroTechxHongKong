/**
 * Property-based test for Gamepad Deadzone and Axis Mapping (Property 8)
 *
 * **Validates: Requirements 5.2**
 *
 * For any gamepad axis value in [-1.0, 1.0], if the absolute value is less than 0.1
 * (10% deadzone), the output velocity for that axis SHALL be zero. If the absolute
 * value is ≥ 0.1, the output SHALL be proportional to the axis value scaled by
 * the configured velocity scale factor.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { applyDeadzone, computeGamepadVelocity } from './TeleopController';

// ─── Constants ──────────────────────────────────────────────────────────────

const DEADZONE_THRESHOLD = 0.1;

// ─── Generators ─────────────────────────────────────────────────────────────

/** Generate a gamepad axis value in [-1.0, 1.0] */
const axisValue = fc.float({ min: Math.fround(-1), max: Math.fround(1), noNaN: true });

/** Generate a velocity scale factor in [0.01, 0.2] */
const velocityScale = fc.float({ min: Math.fround(0.01), max: Math.fround(0.2), noNaN: true });

/** Generate an axis value within the deadzone (|value| < 0.1) */
const axisInDeadzone = fc.float({ min: Math.fround(-DEADZONE_THRESHOLD), max: Math.fround(DEADZONE_THRESHOLD), noNaN: true })
  .filter(v => Math.abs(v) < DEADZONE_THRESHOLD);

/** Generate an axis value outside the deadzone (|value| >= 0.1) */
const axisOutsideDeadzone = fc.oneof(
  fc.float({ min: Math.fround(DEADZONE_THRESHOLD), max: Math.fround(1), noNaN: true }),
  fc.float({ min: Math.fround(-1), max: Math.fround(-DEADZONE_THRESHOLD), noNaN: true })
);

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: web-control-expansion, Property 8: Gamepad deadzone and axis mapping', () => {
  /**
   * Property 8: Gamepad deadzone and axis mapping
   * **Validates: Requirements 5.2**
   */

  describe('applyDeadzone', () => {
    it('should return zero for any axis value within the deadzone (|value| < 0.1)', () => {
      fc.assert(
        fc.property(axisInDeadzone, (value) => {
          const result = applyDeadzone(value, DEADZONE_THRESHOLD);
          expect(result).toBe(0);
        }),
        { numRuns: 200 }
      );
    });

    it('should return the value as-is for any axis value outside the deadzone (|value| >= 0.1)', () => {
      fc.assert(
        fc.property(axisOutsideDeadzone, (value) => {
          const result = applyDeadzone(value, DEADZONE_THRESHOLD);
          expect(result).toBe(value);
        }),
        { numRuns: 200 }
      );
    });

    it('should satisfy the biconditional: output is zero iff |value| < threshold', () => {
      fc.assert(
        fc.property(axisValue, (value) => {
          const result = applyDeadzone(value, DEADZONE_THRESHOLD);
          if (Math.abs(value) < DEADZONE_THRESHOLD) {
            expect(result).toBe(0);
          } else {
            expect(result).toBe(value);
          }
        }),
        { numRuns: 200 }
      );
    });
  });

  describe('computeGamepadVelocity', () => {
    it('should output zero linear.x when left stick X is within deadzone', () => {
      fc.assert(
        fc.property(axisInDeadzone, velocityScale, (lx, scale) => {
          const result = computeGamepadVelocity(lx, 0, 0, 0, 0, scale);
          expect(result.linear[0]).toBe(0);
        }),
        { numRuns: 200 }
      );
    });

    it('should output zero linear.y when left stick Y is within deadzone', () => {
      fc.assert(
        fc.property(axisInDeadzone, velocityScale, (ly, scale) => {
          const result = computeGamepadVelocity(0, ly, 0, 0, 0, scale);
          // After deadzone zeroes the input, -0 * scale can produce -0; both ±0 are valid "zero"
          expect(result.linear[1] === 0).toBe(true);
        }),
        { numRuns: 200 }
      );
    });

    it('should output zero linear.z when right stick Y is within deadzone', () => {
      fc.assert(
        fc.property(axisInDeadzone, velocityScale, (ry, scale) => {
          const result = computeGamepadVelocity(0, 0, ry, 0, 0, scale);
          // After deadzone zeroes the input, -0 * scale can produce -0; both ±0 are valid "zero"
          expect(result.linear[2] === 0).toBe(true);
        }),
        { numRuns: 200 }
      );
    });

    it('should output linearX = leftStickX × scale when outside deadzone', () => {
      fc.assert(
        fc.property(axisOutsideDeadzone, velocityScale, (lx, scale) => {
          const result = computeGamepadVelocity(lx, 0, 0, 0, 0, scale);
          const expected = lx * scale;
          expect(result.linear[0]).toBeCloseTo(expected, 10);
        }),
        { numRuns: 200 }
      );
    });

    it('should output linearY = -leftStickY × scale when outside deadzone (inverted)', () => {
      fc.assert(
        fc.property(axisOutsideDeadzone, velocityScale, (ly, scale) => {
          const result = computeGamepadVelocity(0, ly, 0, 0, 0, scale);
          const expected = -ly * scale;
          expect(result.linear[1]).toBeCloseTo(expected, 10);
        }),
        { numRuns: 200 }
      );
    });

    it('should output linearZ = -rightStickY × scale when outside deadzone (inverted)', () => {
      fc.assert(
        fc.property(axisOutsideDeadzone, velocityScale, (ry, scale) => {
          const result = computeGamepadVelocity(0, 0, ry, 0, 0, scale);
          const expected = -ry * scale;
          expect(result.linear[2]).toBeCloseTo(expected, 10);
        }),
        { numRuns: 200 }
      );
    });

    it('should produce all-zero linear output when all axes are within deadzone', () => {
      fc.assert(
        fc.property(
          axisInDeadzone,
          axisInDeadzone,
          axisInDeadzone,
          velocityScale,
          (lx, ly, ry, scale) => {
            const result = computeGamepadVelocity(lx, ly, ry, 0, 0, scale);
            // All axes are zeroed by deadzone; inverted axes may produce -0
            expect(result.linear[0] === 0).toBe(true);
            expect(result.linear[1] === 0).toBe(true);
            expect(result.linear[2] === 0).toBe(true);
          }
        ),
        { numRuns: 200 }
      );
    });

    it('should always output zero angular velocity (gamepad does not map to angular)', () => {
      fc.assert(
        fc.property(
          axisValue,
          axisValue,
          axisValue,
          velocityScale,
          (lx, ly, ry, scale) => {
            const result = computeGamepadVelocity(lx, ly, ry, 0, 0, scale);
            expect(result.angular).toEqual([0, 0, 0]);
          }
        ),
        { numRuns: 200 }
      );
    });
  });
});
