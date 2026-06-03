/**
 * Property-based test for Pose Name and Capacity Validation (Property 7)
 *
 * **Validates: Requirements 9.1**
 *
 * For any string of length between 1 and 64 characters inclusive, the pose save
 * operation SHALL accept the name. For any string of length 0 or greater than 64,
 * it SHALL reject. For any pose store containing fewer than 50 poses, saving a new
 * pose SHALL succeed. When the store contains exactly 50 poses, saving SHALL be rejected.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { validatePoseName, validatePoseCapacity } from './PoseManager';

// ─── Generators ─────────────────────────────────────────────────────────────

/**
 * Generator for valid pose names: strings of length 1–64.
 */
function validPoseNameArb(): fc.Arbitrary<string> {
  return fc.string({ minLength: 1, maxLength: 64 });
}

/**
 * Generator for pose names that are too short (length 0 = empty string).
 */
function emptyPoseNameArb(): fc.Arbitrary<string> {
  return fc.constant('');
}

/**
 * Generator for pose names that are too long (length > 64).
 */
function tooLongPoseNameArb(): fc.Arbitrary<string> {
  return fc.string({ minLength: 65, maxLength: 200 });
}

/**
 * Generator for a pose store size below capacity (0–49).
 */
function belowCapacityArb(): fc.Arbitrary<number> {
  return fc.integer({ min: 0, max: 49 });
}

/**
 * Generator for a pose store size at or above capacity (≥50).
 */
function atOrAboveCapacityArb(): fc.Arbitrary<number> {
  return fc.integer({ min: 50, max: 200 });
}

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: so100-isaacsim-web-control, Property 7: Pose name and capacity validation', () => {
  /**
   * Property 7a: Valid pose names (1–64 chars) are accepted.
   * **Validates: Requirements 9.1**
   */
  it('should accept any pose name with length between 1 and 64 characters', () => {
    fc.assert(
      fc.property(
        validPoseNameArb(),
        (name) => {
          const result = validatePoseName(name);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 7b: Empty pose names (length 0) are rejected.
   * **Validates: Requirements 9.1**
   */
  it('should reject a pose name with length 0 (empty string)', () => {
    fc.assert(
      fc.property(
        emptyPoseNameArb(),
        (name) => {
          const result = validatePoseName(name);
          expect(result).not.toBeNull();
          expect(typeof result).toBe('string');
        }
      ),
      { numRuns: 10 }
    );
  });

  /**
   * Property 7c: Pose names exceeding 64 characters are rejected.
   * **Validates: Requirements 9.1**
   */
  it('should reject any pose name with length greater than 64 characters', () => {
    fc.assert(
      fc.property(
        tooLongPoseNameArb(),
        (name) => {
          const result = validatePoseName(name);
          expect(result).not.toBeNull();
          expect(typeof result).toBe('string');
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 7d: Pose store below capacity (< 50 poses) allows saving.
   * **Validates: Requirements 9.1**
   */
  it('should allow saving when pose store has fewer than 50 poses', () => {
    fc.assert(
      fc.property(
        belowCapacityArb(),
        (currentCount) => {
          const result = validatePoseCapacity(currentCount);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 7e: Pose store at or above capacity (≥ 50 poses) rejects saving.
   * **Validates: Requirements 9.1**
   */
  it('should reject saving when pose store contains 50 or more poses', () => {
    fc.assert(
      fc.property(
        atOrAboveCapacityArb(),
        (currentCount) => {
          const result = validatePoseCapacity(currentCount);
          expect(result).not.toBeNull();
          expect(typeof result).toBe('string');
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 7f: For any arbitrary string, validation is consistent —
   * accepted iff length is in [1, 64].
   * **Validates: Requirements 9.1**
   */
  it('should accept names iff length is in [1, 64] for arbitrary strings', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 0, maxLength: 200 }),
        (name) => {
          const result = validatePoseName(name);
          if (name.length >= 1 && name.length <= 64) {
            expect(result).toBeNull();
          } else {
            expect(result).not.toBeNull();
          }
        }
      ),
      { numRuns: 500 }
    );
  });
});
