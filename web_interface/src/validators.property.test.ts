/**
 * Property-based test for Workspace Bounds Validation (Property 5)
 *
 * **Validates: Requirements 3.2**
 *
 * For any Cartesian goal position (x, y, z), the workspace validator SHALL accept
 * the goal if and only if x ∈ [-0.3, 0.3], y ∈ [-0.3, 0.3], and z ∈ [0.0, 0.5] meters.
 * All values outside these ranges SHALL be rejected with an appropriate error message.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { validateWorkspacePosition } from './validators';
import { WORKSPACE_BOUNDS } from './types';

// ─── Helper: check if a position is within bounds ───────────────────────────

function isWithinBounds(x: number, y: number, z: number): boolean {
  return (
    x >= WORKSPACE_BOUNDS.x_min &&
    x <= WORKSPACE_BOUNDS.x_max &&
    y >= WORKSPACE_BOUNDS.y_min &&
    y <= WORKSPACE_BOUNDS.y_max &&
    z >= WORKSPACE_BOUNDS.z_min &&
    z <= WORKSPACE_BOUNDS.z_max
  );
}

// ─── Generators ─────────────────────────────────────────────────────────────

/** Generate a double within workspace x bounds */
const xInBounds = fc.double({ min: WORKSPACE_BOUNDS.x_min, max: WORKSPACE_BOUNDS.x_max, noNaN: true });
/** Generate a double within workspace y bounds */
const yInBounds = fc.double({ min: WORKSPACE_BOUNDS.y_min, max: WORKSPACE_BOUNDS.y_max, noNaN: true });
/** Generate a double within workspace z bounds */
const zInBounds = fc.double({ min: WORKSPACE_BOUNDS.z_min, max: WORKSPACE_BOUNDS.z_max, noNaN: true });

/** Generate a double strictly below the x lower bound */
const xBelowMin = fc.double({ min: -100, max: WORKSPACE_BOUNDS.x_min, noNaN: true, maxExcluded: true });
/** Generate a double strictly above the x upper bound */
const xAboveMax = fc.double({ min: WORKSPACE_BOUNDS.x_max, max: 100, noNaN: true, minExcluded: true });
/** Generate a double outside x bounds */
const xOutOfBounds = fc.oneof(xBelowMin, xAboveMax);

/** Generate a double strictly below the y lower bound */
const yBelowMin = fc.double({ min: -100, max: WORKSPACE_BOUNDS.y_min, noNaN: true, maxExcluded: true });
/** Generate a double strictly above the y upper bound */
const yAboveMax = fc.double({ min: WORKSPACE_BOUNDS.y_max, max: 100, noNaN: true, minExcluded: true });
/** Generate a double outside y bounds */
const yOutOfBounds = fc.oneof(yBelowMin, yAboveMax);

/** Generate a double strictly below the z lower bound (excludes -0 since -0 >= 0 in JS) */
const zBelowMin = fc.double({ min: -100, max: WORKSPACE_BOUNDS.z_min, noNaN: true, maxExcluded: true }).filter(v => v < 0);
/** Generate a double strictly above the z upper bound */
const zAboveMax = fc.double({ min: WORKSPACE_BOUNDS.z_max, max: 100, noNaN: true, minExcluded: true });
/** Generate a double outside z bounds */
const zOutOfBounds = fc.oneof(zBelowMin, zAboveMax);

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: web-control-expansion, Property 5: Workspace bounds validation', () => {
  /**
   * Property 5: Workspace bounds validation
   * **Validates: Requirements 3.2**
   */

  it('should accept any position within workspace bounds', () => {
    fc.assert(
      fc.property(
        xInBounds,
        yInBounds,
        zInBounds,
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          expect(result.valid).toBe(true);
          expect(result.error).toBeUndefined();
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should reject positions where x is outside bounds', () => {
    fc.assert(
      fc.property(
        xOutOfBounds,
        yInBounds,
        zInBounds,
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          expect(result.valid).toBe(false);
          expect(result.error).toBeDefined();
          expect(result.error).toContain('X position');
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should reject positions where y is outside bounds', () => {
    fc.assert(
      fc.property(
        xInBounds,
        yOutOfBounds,
        zInBounds,
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          expect(result.valid).toBe(false);
          expect(result.error).toBeDefined();
          expect(result.error).toContain('Y position');
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should reject positions where z is outside bounds', () => {
    fc.assert(
      fc.property(
        xInBounds,
        yInBounds,
        zOutOfBounds,
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          expect(result.valid).toBe(false);
          expect(result.error).toBeDefined();
          expect(result.error).toContain('Z position');
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should validate correctly for any arbitrary position (biconditional)', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -10, max: 10, noNaN: true }),
        fc.double({ min: -10, max: 10, noNaN: true }),
        fc.double({ min: -10, max: 10, noNaN: true }),
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          const shouldBeValid = isWithinBounds(x, y, z);

          // The validator accepts iff the position is within all three bounds
          expect(result.valid).toBe(shouldBeValid);

          if (shouldBeValid) {
            expect(result.error).toBeUndefined();
          } else {
            expect(result.error).toBeDefined();
            expect(result.error!.length).toBeGreaterThan(0);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should accept boundary values (inclusive bounds)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          WORKSPACE_BOUNDS.x_min,
          WORKSPACE_BOUNDS.x_max,
          0
        ),
        fc.constantFrom(
          WORKSPACE_BOUNDS.y_min,
          WORKSPACE_BOUNDS.y_max,
          0
        ),
        fc.constantFrom(
          WORKSPACE_BOUNDS.z_min,
          WORKSPACE_BOUNDS.z_max,
          0.25
        ),
        (x, y, z) => {
          const result = validateWorkspacePosition(x, y, z);
          expect(result.valid).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});
