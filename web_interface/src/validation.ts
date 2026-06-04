/**
 * Client-side validation for spawn requests and workspace bounds.
 * Mirrors the Python validation logic in message_schemas.py.
 */

import type { SpawnObjectMessage } from './types';

// ─── Spawn Bounds ───────────────────────────────────────────────────────────

export interface SpawnBounds {
  minDimension: number; // exclusive lower bound (> 0)
  maxDimension: number; // inclusive upper bound
  minPosition: number; // inclusive
  maxPosition: number; // inclusive
  minOrientation: number; // inclusive (-π)
  maxOrientation: number; // inclusive (+π)
  minMass: number; // exclusive lower bound (> 0)
  maxMass: number; // inclusive upper bound
  minColor: number; // inclusive
  maxColor: number; // inclusive
}

export const SPAWN_BOUNDS: SpawnBounds = {
  minDimension: 0.0,
  maxDimension: 2.0,
  minPosition: -10.0,
  maxPosition: 10.0,
  minOrientation: -Math.PI,
  maxOrientation: Math.PI,
  minMass: 0.0,
  maxMass: 50.0,
  minColor: 0.0,
  maxColor: 1.0,
};

// Expected dimension array lengths per object type.
export const DIMENSION_LENGTHS: Record<string, number> = {
  box: 3, // [length, width, height]
  sphere: 1, // [radius]
  cylinder: 2, // [radius, height]
};

export const VALID_OBJECT_TYPES = Object.keys(DIMENSION_LENGTHS);

// ─── Validation Result ──────────────────────────────────────────────────────

export type ValidationResult =
  | { valid: true; error: null }
  | { valid: false; error: string };

// ─── Spawn Request Validation ───────────────────────────────────────────────

/**
 * Validate a spawn object request against defined bounds.
 *
 * Checks that all numeric values fall within the constraints specified
 * by SpawnBounds, and that the dimensions array length matches the object type.
 *
 * @param request - The spawn object message to validate (without the `type` field requirement).
 * @param bounds - SpawnBounds instance to validate against. Defaults to SPAWN_BOUNDS.
 * @returns A ValidationResult indicating whether the request is valid.
 */
export function validateSpawnRequest(
  request: Omit<SpawnObjectMessage, 'type'>,
  bounds: SpawnBounds = SPAWN_BOUNDS,
): ValidationResult {
  const { object_type, dimensions, position, orientation, color, mass } =
    request;

  // Validate object_type.
  if (!VALID_OBJECT_TYPES.includes(object_type)) {
    return {
      valid: false,
      error: `Invalid object_type '${object_type}'. Valid types: ${VALID_OBJECT_TYPES.sort().join(', ')}`,
    };
  }

  // Validate dimensions array length matches object type.
  const expectedLen = DIMENSION_LENGTHS[object_type];
  if (dimensions.length !== expectedLen) {
    return {
      valid: false,
      error: `object_type '${object_type}' requires ${expectedLen} dimension(s), got ${dimensions.length}`,
    };
  }

  // Validate each dimension value: must be in (0.0, 2.0].
  for (let i = 0; i < dimensions.length; i++) {
    const dim = dimensions[i];
    if (dim <= bounds.minDimension) {
      return {
        valid: false,
        error: `dimensions[${i}] = ${dim} must be greater than ${bounds.minDimension}`,
      };
    }
    if (dim > bounds.maxDimension) {
      return {
        valid: false,
        error: `dimensions[${i}] = ${dim} exceeds maximum ${bounds.maxDimension}`,
      };
    }
  }

  // Validate position: [x, y, z] each in [-10.0, 10.0].
  for (let i = 0; i < 3; i++) {
    const coord = position[i];
    if (coord < bounds.minPosition || coord > bounds.maxPosition) {
      return {
        valid: false,
        error: `position[${i}] = ${coord} out of bounds [${bounds.minPosition}, ${bounds.maxPosition}]`,
      };
    }
  }

  // Validate orientation: [roll, pitch, yaw] each in [-π, π].
  for (let i = 0; i < 3; i++) {
    const angle = orientation[i];
    if (angle < bounds.minOrientation || angle > bounds.maxOrientation) {
      return {
        valid: false,
        error: `orientation[${i}] = ${angle} out of bounds [${bounds.minOrientation}, ${bounds.maxOrientation}]`,
      };
    }
  }

  // Validate color: [r, g, b, a] each in [0.0, 1.0].
  for (let i = 0; i < 4; i++) {
    const c = color[i];
    if (c < bounds.minColor || c > bounds.maxColor) {
      return {
        valid: false,
        error: `color[${i}] = ${c} out of bounds [${bounds.minColor}, ${bounds.maxColor}]`,
      };
    }
  }

  // Validate mass: must be in (0.0, 50.0].
  if (mass <= bounds.minMass) {
    return {
      valid: false,
      error: `mass = ${mass} must be greater than ${bounds.minMass}`,
    };
  }
  if (mass > bounds.maxMass) {
    return {
      valid: false,
      error: `mass = ${mass} exceeds maximum ${bounds.maxMass}`,
    };
  }

  return { valid: true, error: null };
}
