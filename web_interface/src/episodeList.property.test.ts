/**
 * Property-based test for Episode List Sorting and Capping (Property 6)
 *
 * **Validates: Requirements 4.5**
 *
 * For any list of episode records with arbitrary timestamps and sizes,
 * the episode list formatter SHALL return records sorted by timestamp
 * descending (most recent first) with a maximum of 100 entries.
 * If the input has more than 100 records, only the 100 most recent SHALL be returned.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { formatEpisodeList, MAX_EPISODE_LIST_SIZE } from './episodeList';
import { EpisodeRecord } from './types';

// ─── Generators ─────────────────────────────────────────────────────────────

/** Generate an arbitrary EpisodeRecord */
const episodeRecordArb: fc.Arbitrary<EpisodeRecord> = fc.record({
  id: fc.string({ minLength: 1, maxLength: 30 }),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  timestamp: fc.integer({ min: 0, max: Number.MAX_SAFE_INTEGER }),
  duration_seconds: fc.double({ min: 0, max: 3600, noNaN: true }),
});

/** Generate a list of episode records (any size) */
const episodeListArb = fc.array(episodeRecordArb, { minLength: 0, maxLength: 200 });

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: web-control-expansion, Property 6: Episode list sorting and capping', () => {
  /**
   * Property 6: Episode list sorting and capping
   * **Validates: Requirements 4.5**
   */

  it('should return at most 100 entries for any input list', () => {
    fc.assert(
      fc.property(episodeListArb, (episodes) => {
        const result = formatEpisodeList(episodes);
        expect(result.length).toBeLessThanOrEqual(MAX_EPISODE_LIST_SIZE);
      }),
      { numRuns: 200 }
    );
  });

  it('should return records sorted by timestamp descending', () => {
    fc.assert(
      fc.property(episodeListArb, (episodes) => {
        const result = formatEpisodeList(episodes);
        for (let i = 1; i < result.length; i++) {
          expect(result[i - 1].timestamp).toBeGreaterThanOrEqual(result[i].timestamp);
        }
      }),
      { numRuns: 200 }
    );
  });

  it('should only contain entries that exist in the original input', () => {
    fc.assert(
      fc.property(episodeListArb, (episodes) => {
        const result = formatEpisodeList(episodes);
        for (const record of result) {
          expect(episodes).toContainEqual(record);
        }
      }),
      { numRuns: 200 }
    );
  });

  it('should preserve the 100 most recent entries when input exceeds 100', () => {
    fc.assert(
      fc.property(
        fc.array(episodeRecordArb, { minLength: 101, maxLength: 200 }),
        (episodes) => {
          const result = formatEpisodeList(episodes);

          // Sort input by timestamp descending to get expected top 100
          const sortedInput = [...episodes].sort((a, b) => b.timestamp - a.timestamp);
          const expectedTop100 = sortedInput.slice(0, MAX_EPISODE_LIST_SIZE);

          expect(result.length).toBe(MAX_EPISODE_LIST_SIZE);
          expect(result).toEqual(expectedTop100);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should return all entries when input has 100 or fewer records', () => {
    fc.assert(
      fc.property(
        fc.array(episodeRecordArb, { minLength: 0, maxLength: 100 }),
        (episodes) => {
          const result = formatEpisodeList(episodes);
          expect(result.length).toBe(episodes.length);
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should not mutate the original input array', () => {
    fc.assert(
      fc.property(episodeListArb, (episodes) => {
        const originalCopy = [...episodes];
        formatEpisodeList(episodes);
        expect(episodes).toEqual(originalCopy);
      }),
      { numRuns: 100 }
    );
  });
});
