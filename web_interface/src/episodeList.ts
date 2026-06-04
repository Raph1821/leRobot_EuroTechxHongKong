/**
 * Episode list formatting utility.
 *
 * Sorts episode records by timestamp descending (most recent first)
 * and caps the result at 100 entries.
 */

import { EpisodeRecord } from './types';

/** Maximum number of episodes returned in a formatted list */
export const MAX_EPISODE_LIST_SIZE = 100;

/**
 * Formats a list of episode records by sorting them in descending timestamp
 * order (most recent first) and capping the result at 100 entries.
 *
 * If the input has more than 100 records, only the 100 most recent are returned.
 */
export function formatEpisodeList(episodes: EpisodeRecord[]): EpisodeRecord[] {
  return [...episodes]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, MAX_EPISODE_LIST_SIZE);
}
