/**
 * Property-based tests for spawn request validation.
 *
 * Feature: web-control-expansion, Property 3: Spawn request validation
 *
 * **Validates: Requirements 2.2, 2.8**
 */

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import {
  validateSpawnRequest,
  SPAWN_BOUNDS,
  DIMENSION_LENGTHS,
} from './validation';

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Generate a valid dimensions array for a given object type. */
function validDimensionsArb(
  objectType: 'box' | 'sphere' | 'cylinder',
): fc.Arbitrary<number[]> {
  const len = DIMENSION_LENGTHS[objectType];
  // Dimensions must be in (0.0, 2.0] — exclusive lower, inclusive upper
  return fc.array(
    fc.double({ min: 0.001, max: 2.0, noNaN: true }),
    { minLength: len, maxLength: len },
  );
}

/** Arbitrary for valid object types. */
const objectTypeArb = fc.constantFrom(
  'box' as const,
  'sphere' as const,
  'cylinder' as const,
);

/** Arbitrary for a valid position coordinate in [-10.0, 10.0]. */
const validPositionCoordArb = fc.double({
  min: -10.0,
  max: 10.0,
  noNaN: true,
});

/** Arbitrary for a valid orientation value in [-π, π]. */
const validOrientationArb = fc.double({
  min: -Math.PI,
  max: Math.PI,
  noNaN: true,
});

/** Arbitrary for a valid color component in [0.0, 1.0]. */
const validColorArb = fc.double({ min: 0.0, max: 1.0, noNaN: true });

/** Arbitrary for a valid mass in (0.0, 50.0]. */
const validMassArb = fc.double({ min: 0.001, max: 50.0, noNaN: true });

/** Generate a fully valid spawn request. */
function validSpawnRequestArb() {
  return objectTypeArb.chain((objectType) =>
    fc.record({
      object_type: fc.constant(objectType),
      dimensions: validDimensionsArb(objectType),
      position: fc.tuple(
        validPositionCoordArb,
        validPositionCoordArb,
        validPositionCoordArb,
      ) as fc.Arbitrary<[number, number, number]>,
      orientation: fc.tuple(
        validOrientationArb,
        validOrientationArb,
        validOrientationArb,
      ) as fc.Arbitrary<[number, number, number]>,
      color: fc.tuple(
        validColorArb,
        validColorArb,
        validColorArb,
        validColorArb,
      ) as fc.Arbitrary<[number, number, number, number]>,
      mass: validMassArb,
    }),
  );
}

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Property 3: Spawn request validation', () => {
  it('accepts all valid spawn requests', () => {
    fc.assert(
      fc.property(validSpawnRequestArb(), (request) => {
        const result = validateSpawnRequest(request);
        expect(result.valid).toBe(true);
        expect(result.error).toBeNull();
      }),
      { numRuns: 200 },
    );
  });

  it('rejects requests with dimensions <= 0', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.nat({ max: 2 }),
        fc.double({ min: -100, max: 0.0, noNaN: true }),
        (request, dimIndex, badValue) => {
          // Only modify an index that exists for this object type
          const maxIdx = DIMENSION_LENGTHS[request.object_type] - 1;
          const idx = dimIndex <= maxIdx ? dimIndex : 0;
          const modified = {
            ...request,
            dimensions: [...request.dimensions],
          };
          modified.dimensions[idx] = badValue;
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('dimensions');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with dimensions > 2.0', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.nat({ max: 2 }),
        fc.double({ min: 2.001, max: 1000, noNaN: true }),
        (request, dimIndex, badValue) => {
          const maxIdx = DIMENSION_LENGTHS[request.object_type] - 1;
          const idx = dimIndex <= maxIdx ? dimIndex : 0;
          const modified = {
            ...request,
            dimensions: [...request.dimensions],
          };
          modified.dimensions[idx] = badValue;
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('dimensions');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with position out of bounds', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.nat({ max: 2 }),
        fc.oneof(
          fc.double({ min: -1000, max: -10.001, noNaN: true }),
          fc.double({ min: 10.001, max: 1000, noNaN: true }),
        ),
        (request, coordIndex, badValue) => {
          const modified = {
            ...request,
            position: [...request.position] as [number, number, number],
          };
          modified.position[coordIndex] = badValue;
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('position');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with orientation out of bounds', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.nat({ max: 2 }),
        fc.oneof(
          fc.double({ min: -100, max: -(Math.PI + 0.001), noNaN: true }),
          fc.double({ min: Math.PI + 0.001, max: 100, noNaN: true }),
        ),
        (request, coordIndex, badValue) => {
          const modified = {
            ...request,
            orientation: [...request.orientation] as [
              number,
              number,
              number,
            ],
          };
          modified.orientation[coordIndex] = badValue;
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('orientation');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with color out of [0, 1] range', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.nat({ max: 3 }),
        fc.oneof(
          fc.double({ min: -100, max: -0.001, noNaN: true }),
          fc.double({ min: 1.001, max: 100, noNaN: true }),
        ),
        (request, colorIndex, badValue) => {
          const modified = {
            ...request,
            color: [...request.color] as [number, number, number, number],
          };
          modified.color[colorIndex] = badValue;
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('color');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with mass <= 0', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.double({ min: -100, max: 0.0, noNaN: true }),
        (request, badMass) => {
          const modified = { ...request, mass: badMass };
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('mass');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with mass > 50', () => {
    fc.assert(
      fc.property(
        validSpawnRequestArb(),
        fc.double({ min: 50.001, max: 10000, noNaN: true }),
        (request, badMass) => {
          const modified = { ...request, mass: badMass };
          const result = validateSpawnRequest(modified);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('mass');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('rejects requests with wrong dimension array length for object type', () => {
    fc.assert(
      fc.property(
        objectTypeArb,
        fc.double({ min: 0.001, max: 2.0, noNaN: true }),
        validMassArb,
        (objectType, dimValue, mass) => {
          const expectedLen = DIMENSION_LENGTHS[objectType];
          // Create a dimensions array with wrong length (either too short or too long)
          const wrongLen = expectedLen === 1 ? 3 : 1;
          const wrongDimensions = Array(wrongLen).fill(dimValue);

          const request = {
            object_type: objectType,
            dimensions: wrongDimensions,
            position: [0, 0, 0] as [number, number, number],
            orientation: [0, 0, 0] as [number, number, number],
            color: [0.5, 0.5, 0.5, 1.0] as [number, number, number, number],
            mass,
          };
          const result = validateSpawnRequest(request);
          expect(result.valid).toBe(false);
          expect(result.error).toContain('dimension');
        },
      ),
      { numRuns: 200 },
    );
  });

  it('validates the full property: accepts iff all values in bounds and dimension length matches', () => {
    // This is the comprehensive property test that validates the full specification:
    // For any combination of object_type, dimensions, position, orientation, color, and mass,
    // the validator accepts iff all values are within defined bounds and dimension array
    // length matches object type.
    fc.assert(
      fc.property(
        objectTypeArb,
        // Generate arbitrary dimensions (could be valid or invalid length)
        fc.array(
          fc.double({ min: -10, max: 10, noNaN: true }),
          { minLength: 0, maxLength: 5 },
        ),
        fc.tuple(
          fc.double({ min: -20, max: 20, noNaN: true }),
          fc.double({ min: -20, max: 20, noNaN: true }),
          fc.double({ min: -20, max: 20, noNaN: true }),
        ),
        fc.tuple(
          fc.double({ min: -10, max: 10, noNaN: true }),
          fc.double({ min: -10, max: 10, noNaN: true }),
          fc.double({ min: -10, max: 10, noNaN: true }),
        ),
        fc.tuple(
          fc.double({ min: -2, max: 2, noNaN: true }),
          fc.double({ min: -2, max: 2, noNaN: true }),
          fc.double({ min: -2, max: 2, noNaN: true }),
          fc.double({ min: -2, max: 2, noNaN: true }),
        ),
        fc.double({ min: -10, max: 100, noNaN: true }),
        (objectType, dimensions, position, orientation, color, mass) => {
          const request = {
            object_type: objectType,
            dimensions,
            position: position as [number, number, number],
            orientation: orientation as [number, number, number],
            color: color as [number, number, number, number],
            mass,
          };

          const result = validateSpawnRequest(request);

          // Compute expected validity manually
          const expectedLen = DIMENSION_LENGTHS[objectType];
          const dimLenOk = dimensions.length === expectedLen;
          const dimsOk =
            dimLenOk &&
            dimensions.every(
              (d) => d > SPAWN_BOUNDS.minDimension && d <= SPAWN_BOUNDS.maxDimension,
            );
          const posOk = position.every(
            (p) =>
              p >= SPAWN_BOUNDS.minPosition && p <= SPAWN_BOUNDS.maxPosition,
          );
          const orientOk = orientation.every(
            (o) =>
              o >= SPAWN_BOUNDS.minOrientation &&
              o <= SPAWN_BOUNDS.maxOrientation,
          );
          const colorOk = color.every(
            (c) => c >= SPAWN_BOUNDS.minColor && c <= SPAWN_BOUNDS.maxColor,
          );
          const massOk =
            mass > SPAWN_BOUNDS.minMass && mass <= SPAWN_BOUNDS.maxMass;

          const shouldBeValid =
            dimLenOk && dimsOk && posOk && orientOk && colorOk && massOk;

          expect(result.valid).toBe(shouldBeValid);
        },
      ),
      { numRuns: 500 },
    );
  });
});
