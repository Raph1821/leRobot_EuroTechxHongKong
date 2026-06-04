/**
 * Property-based test for Trajectory Goal Construction from Poses (Property 6)
 *
 * **Validates: Requirements 9.3, 9.4**
 *
 * For any non-empty ordered list of saved poses (each containing valid positions
 * for all 5 arm joints) and for any time_from_start value in [0.5, 30.0] seconds,
 * the constructed trajectory goal message SHALL contain waypoints equal in count
 * to the number of poses, with each waypoint's joint positions matching the
 * corresponding pose and each waypoint's time_from_start equal to (index + 1) × interval_seconds.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { buildTrajectoryGoal } from './PoseManager';
import type { SavedPose } from '../types';
import { JOINT_CONFIGS, ARM_JOINT_NAMES } from '../types';

// ─── Generators ─────────────────────────────────────────────────────────────

/** Joint limits for the 5 arm joints (excluding Gripper) */
const armJointLimits: Record<string, { lower: number; upper: number }> = {};
for (const config of JOINT_CONFIGS) {
  if ((ARM_JOINT_NAMES as readonly string[]).includes(config.name)) {
    armJointLimits[config.name] = {
      lower: config.lowerLimit,
      upper: config.upperLimit,
    };
  }
}

/**
 * Generator for valid arm joint positions (all 5 arm joints within limits).
 */
function validArmPositionsArb(): fc.Arbitrary<Record<string, number>> {
  return fc.record(
    Object.fromEntries(
      ARM_JOINT_NAMES.map((name) => [
        name,
        fc.double({
          min: armJointLimits[name].lower,
          max: armJointLimits[name].upper,
          noNaN: true,
          noDefaultInfinity: true,
        }),
      ])
    )
  ) as fc.Arbitrary<Record<string, number>>;
}

/**
 * Generator for a valid SavedPose with arm joint positions within limits.
 */
function savedPoseArb(): fc.Arbitrary<SavedPose> {
  return fc.record({
    name: fc.string({ minLength: 1, maxLength: 64 }),
    positions: validArmPositionsArb(),
    savedAt: fc.integer({ min: 0, max: Number.MAX_SAFE_INTEGER }),
  });
}

/**
 * Generator for a non-empty array of saved poses (1–20 poses).
 */
function nonEmptyPoseArrayArb(): fc.Arbitrary<SavedPose[]> {
  return fc.array(savedPoseArb(), { minLength: 1, maxLength: 20 });
}

/**
 * Generator for a valid interval in [0.5, 30.0] seconds.
 */
function validIntervalArb(): fc.Arbitrary<number> {
  return fc.double({ min: 0.5, max: 30.0, noNaN: true, noDefaultInfinity: true });
}

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: so100-isaacsim-web-control, Property 6: Trajectory goal construction from poses', () => {
  /**
   * Property 6a: Waypoint count matches pose count.
   * **Validates: Requirements 9.3, 9.4**
   */
  it('should produce waypoints equal in count to the number of poses', () => {
    fc.assert(
      fc.property(
        nonEmptyPoseArrayArb(),
        validIntervalArb(),
        (poses, interval) => {
          const result = buildTrajectoryGoal(poses, interval);
          expect(result.waypoints.length).toBe(poses.length);
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 6b: Each waypoint's time_from_start equals (index + 1) × interval.
   * **Validates: Requirements 9.3, 9.4**
   */
  it('should set time_from_start = (index + 1) × interval for each waypoint', () => {
    fc.assert(
      fc.property(
        nonEmptyPoseArrayArb(),
        validIntervalArb(),
        (poses, interval) => {
          const result = buildTrajectoryGoal(poses, interval);
          for (let i = 0; i < result.waypoints.length; i++) {
            const expected = (i + 1) * interval;
            expect(result.waypoints[i].time_from_start).toBeCloseTo(expected, 10);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 6c: Each waypoint's joint positions match the corresponding pose.
   * **Validates: Requirements 9.3, 9.4**
   */
  it('should have waypoint positions matching the corresponding pose positions', () => {
    fc.assert(
      fc.property(
        nonEmptyPoseArrayArb(),
        validIntervalArb(),
        (poses, interval) => {
          const result = buildTrajectoryGoal(poses, interval);
          for (let i = 0; i < result.waypoints.length; i++) {
            const waypoint = result.waypoints[i];
            const pose = poses[i];
            for (const jointName of ARM_JOINT_NAMES) {
              expect(waypoint.positions[jointName]).toBe(pose.positions[jointName]);
            }
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Property 6d: The result message type is always 'trajectory_goal'.
   * **Validates: Requirements 9.3, 9.4**
   */
  it('should always produce a message with type trajectory_goal', () => {
    fc.assert(
      fc.property(
        nonEmptyPoseArrayArb(),
        validIntervalArb(),
        (poses, interval) => {
          const result = buildTrajectoryGoal(poses, interval);
          expect(result.type).toBe('trajectory_goal');
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 6e: Intervals outside [0.5, 30.0] are clamped to the valid range.
   * **Validates: Requirements 9.3, 9.4**
   */
  it('should clamp intervals outside [0.5, 30.0] to the valid range', () => {
    fc.assert(
      fc.property(
        nonEmptyPoseArrayArb(),
        fc.double({ min: -100, max: 100, noNaN: true, noDefaultInfinity: true }),
        (poses, interval) => {
          const result = buildTrajectoryGoal(poses, interval);
          const clampedInterval = Math.max(0.5, Math.min(30.0, interval));
          for (let i = 0; i < result.waypoints.length; i++) {
            const expected = (i + 1) * clampedInterval;
            expect(result.waypoints[i].time_from_start).toBeCloseTo(expected, 10);
          }
        }
      ),
      { numRuns: 200 }
    );
  });
});
