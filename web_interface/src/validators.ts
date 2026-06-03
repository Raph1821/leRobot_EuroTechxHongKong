/**
 * Validation utilities for the SO-100 Web Control Interface.
 * Provides client-side pre-validation for commands before sending to the bridge.
 */

import { WORKSPACE_BOUNDS } from './types';

/**
 * Result of a workspace position validation.
 */
export interface WorkspaceValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates that a Cartesian goal position is within the robot's reachable workspace.
 *
 * The workspace bounds are defined relative to the robot base_link frame:
 * - x: [-0.3, 0.3] meters
 * - y: [-0.3, 0.3] meters
 * - z: [0.0, 0.5] meters
 *
 * @param x - X coordinate in meters
 * @param y - Y coordinate in meters
 * @param z - Z coordinate in meters
 * @returns Validation result indicating whether the position is within bounds
 */
export function validateWorkspacePosition(
  x: number,
  y: number,
  z: number
): WorkspaceValidationResult {
  if (x < WORKSPACE_BOUNDS.x_min || x > WORKSPACE_BOUNDS.x_max) {
    return {
      valid: false,
      error: `X position ${x} is outside workspace bounds [${WORKSPACE_BOUNDS.x_min}, ${WORKSPACE_BOUNDS.x_max}]`,
    };
  }

  if (y < WORKSPACE_BOUNDS.y_min || y > WORKSPACE_BOUNDS.y_max) {
    return {
      valid: false,
      error: `Y position ${y} is outside workspace bounds [${WORKSPACE_BOUNDS.y_min}, ${WORKSPACE_BOUNDS.y_max}]`,
    };
  }

  if (z < WORKSPACE_BOUNDS.z_min || z > WORKSPACE_BOUNDS.z_max) {
    return {
      valid: false,
      error: `Z position ${z} is outside workspace bounds [${WORKSPACE_BOUNDS.z_min}, ${WORKSPACE_BOUNDS.z_max}]`,
    };
  }

  return { valid: true };
}
