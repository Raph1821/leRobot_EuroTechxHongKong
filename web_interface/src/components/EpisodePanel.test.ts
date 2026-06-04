/**
 * Unit tests for EpisodePanel component.
 *
 * Tests: recording controls, recording indicator, episode list,
 * replay progress, control disabling during replay, unavailable state,
 * error display.
 *
 * Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  EpisodePanel,
  formatElapsedTime,
  formatTimestamp,
  sortAndCapEpisodes,
} from './EpisodePanel';
import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  EpisodeListMessage,
  EpisodeRecord,
  RecordingStatusMessage,
  ErrorMessage,
} from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

function createMockConnectionManager(): ConnectionManager & { _emit: Function } {
  const listeners: Record<string, Function[]> = {};
  return {
    on: vi.fn((event: string, listener: Function) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(listener);
    }),
    off: vi.fn(),
    send: vi.fn(() => true),
    getState: vi.fn(() => 'connected' as const),
    removeAllListeners: vi.fn(),
    _emit: (event: string, ...args: unknown[]) => {
      for (const listener of listeners[event] || []) {
        listener(...args);
      }
    },
  } as unknown as ConnectionManager & { _emit: Function };
}

// ─── Mock DOM ───────────────────────────────────────────────────────────────

function createContainer(): HTMLElement {
  return document.createElement('div');
}

// ─── Helper: Episode Records ────────────────────────────────────────────────

function createEpisodeRecord(overrides: Partial<EpisodeRecord> = {}): EpisodeRecord {
  return {
    id: 'episode_001',
    name: 'Test Episode',
    timestamp: Date.now(),
    duration_seconds: 30,
    ...overrides,
  };
}

// ─── Tests: Utility Functions ───────────────────────────────────────────────

describe('formatElapsedTime', () => {
  it('formats 0 seconds as 00:00', () => {
    expect(formatElapsedTime(0)).toBe('00:00');
  });

  it('formats 65 seconds as 01:05', () => {
    expect(formatElapsedTime(65)).toBe('01:05');
  });

  it('formats 3600 seconds as 60:00', () => {
    expect(formatElapsedTime(3600)).toBe('60:00');
  });

  it('handles negative values as 00:00', () => {
    expect(formatElapsedTime(-5)).toBe('00:00');
  });

  it('floors fractional seconds', () => {
    expect(formatElapsedTime(5.9)).toBe('00:05');
  });
});

describe('formatTimestamp', () => {
  it('returns a non-empty string for valid epoch ms', () => {
    const result = formatTimestamp(1700000000000);
    expect(result.length).toBeGreaterThan(0);
  });
});

describe('sortAndCapEpisodes', () => {
  it('sorts episodes by timestamp descending', () => {
    const episodes: EpisodeRecord[] = [
      createEpisodeRecord({ id: 'ep1', timestamp: 100 }),
      createEpisodeRecord({ id: 'ep3', timestamp: 300 }),
      createEpisodeRecord({ id: 'ep2', timestamp: 200 }),
    ];
    const result = sortAndCapEpisodes(episodes);
    expect(result[0].id).toBe('ep3');
    expect(result[1].id).toBe('ep2');
    expect(result[2].id).toBe('ep1');
  });

  it('caps at 100 episodes', () => {
    const episodes: EpisodeRecord[] = Array.from({ length: 150 }, (_, i) =>
      createEpisodeRecord({ id: `ep_${i}`, timestamp: i })
    );
    const result = sortAndCapEpisodes(episodes);
    expect(result.length).toBe(100);
  });

  it('keeps the 100 most recent when capping', () => {
    const episodes: EpisodeRecord[] = Array.from({ length: 150 }, (_, i) =>
      createEpisodeRecord({ id: `ep_${i}`, timestamp: i })
    );
    const result = sortAndCapEpisodes(episodes);
    // Most recent are the highest timestamps (149, 148, ... 50)
    expect(result[0].id).toBe('ep_149');
    expect(result[99].id).toBe('ep_50');
  });

  it('returns empty array for empty input', () => {
    expect(sortAndCapEpisodes([])).toEqual([]);
  });
});

// ─── Tests: EpisodePanel Component ──────────────────────────────────────────

describe('EpisodePanel', () => {
  let panel: EpisodePanel;
  let connectionManager: ConnectionManager & { _emit: Function };
  let container: HTMLElement;

  beforeEach(() => {
    vi.useFakeTimers();
    connectionManager = createMockConnectionManager();
    panel = new EpisodePanel(connectionManager);
    container = createContainer();
    panel.mount(container);
  });

  afterEach(() => {
    panel.unmount();
    vi.useRealTimers();
  });

  describe('mount and unmount', () => {
    it('adds episode-panel class on mount', () => {
      expect(container.classList.contains('episode-panel')).toBe(true);
    });

    it('creates control buttons', () => {
      const startBtn = container.querySelector('.episode-start-button');
      const stopSaveBtn = container.querySelector('.episode-stop-save-button');
      const discardBtn = container.querySelector('.episode-discard-button');
      expect(startBtn).not.toBeNull();
      expect(stopSaveBtn).not.toBeNull();
      expect(discardBtn).not.toBeNull();
    });

    it('cleans up DOM on unmount', () => {
      panel.unmount();
      expect(container.innerHTML).toBe('');
      expect(container.classList.contains('episode-panel')).toBe(false);
    });
  });

  describe('initial state', () => {
    it('starts in idle state', () => {
      expect(panel.getState()).toBe('idle');
    });

    it('start button is enabled in idle state', () => {
      const startBtn = container.querySelector('.episode-start-button') as HTMLButtonElement;
      expect(startBtn.disabled).toBe(false);
    });

    it('stop & save button is disabled in idle state', () => {
      const stopSaveBtn = container.querySelector('.episode-stop-save-button') as HTMLButtonElement;
      expect(stopSaveBtn.disabled).toBe(true);
    });

    it('discard button is disabled in idle state', () => {
      const discardBtn = container.querySelector('.episode-discard-button') as HTMLButtonElement;
      expect(discardBtn.disabled).toBe(true);
    });

    it('recording indicator is hidden', () => {
      const indicator = container.querySelector('.episode-recording-indicator') as HTMLElement;
      expect(indicator.style.display).toBe('none');
    });

    it('requests episode list on mount', () => {
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'list_episodes',
      });
    });
  });

  describe('recording (Req 4.2, 4.3)', () => {
    it('sends start_recording command when Start Recording clicked', () => {
      const startBtn = container.querySelector('.episode-start-button') as HTMLButtonElement;
      startBtn.click();
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'start_recording',
      });
    });

    it('disables Start button during recording', () => {
      const statusMsg: RecordingStatusMessage = {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      };
      connectionManager._emit('message', statusMsg);

      const startBtn = container.querySelector('.episode-start-button') as HTMLButtonElement;
      expect(startBtn.disabled).toBe(true);
    });

    it('shows recording indicator with red dot during recording', () => {
      const statusMsg: RecordingStatusMessage = {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      };
      connectionManager._emit('message', statusMsg);

      const indicator = container.querySelector('.episode-recording-indicator') as HTMLElement;
      expect(indicator.style.display).toBe('flex');

      const redDot = indicator.querySelector('.episode-red-dot');
      expect(redDot).not.toBeNull();
    });

    it('updates elapsed time counter at least once per second', () => {
      const statusMsg: RecordingStatusMessage = {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      };
      connectionManager._emit('message', statusMsg);

      // Advance 3 seconds
      vi.advanceTimersByTime(3000);

      const elapsedSpan = container.querySelector('.episode-elapsed-time') as HTMLElement;
      // Should show approximately 00:03
      expect(elapsedSpan.textContent).toBe('00:03');
    });

    it('sends stop_recording command when Stop & Save clicked', () => {
      // Enter recording state
      const statusMsg: RecordingStatusMessage = {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      };
      connectionManager._emit('message', statusMsg);

      const stopSaveBtn = container.querySelector('.episode-stop-save-button') as HTMLButtonElement;
      stopSaveBtn.click();
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'stop_recording',
      });
    });

    it('sends discard_recording command when Discard clicked', () => {
      // Enter recording state
      const statusMsg: RecordingStatusMessage = {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      };
      connectionManager._emit('message', statusMsg);

      const discardBtn = container.querySelector('.episode-discard-button') as HTMLButtonElement;
      discardBtn.click();
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'discard_recording',
      });
    });

    it('hides recording indicator when transitioning to idle', () => {
      // Start recording
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      } as RecordingStatusMessage);

      // Stop recording
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'idle',
      } as RecordingStatusMessage);

      const indicator = container.querySelector('.episode-recording-indicator') as HTMLElement;
      expect(indicator.style.display).toBe('none');
    });
  });

  describe('episode list (Req 4.4, 4.5)', () => {
    it('displays episodes from episode_list message', () => {
      const episodes: EpisodeRecord[] = [
        createEpisodeRecord({ id: 'ep1', name: 'Episode 1', timestamp: 200 }),
        createEpisodeRecord({ id: 'ep2', name: 'Episode 2', timestamp: 100 }),
      ];
      const listMsg: EpisodeListMessage = {
        type: 'episode_list',
        episodes,
      };
      connectionManager._emit('message', listMsg);

      const items = container.querySelectorAll('.episode-item');
      expect(items.length).toBe(2);
    });

    it('sorts episodes by most recent first', () => {
      const episodes: EpisodeRecord[] = [
        createEpisodeRecord({ id: 'ep1', name: 'Older', timestamp: 100 }),
        createEpisodeRecord({ id: 'ep2', name: 'Newer', timestamp: 200 }),
      ];
      const listMsg: EpisodeListMessage = {
        type: 'episode_list',
        episodes,
      };
      connectionManager._emit('message', listMsg);

      const items = container.querySelectorAll('.episode-item');
      const firstItem = items[0] as HTMLElement;
      expect(firstItem.dataset.episodeId).toBe('ep2');
    });

    it('shows episode name, timestamp, and duration', () => {
      const episodes: EpisodeRecord[] = [
        createEpisodeRecord({ id: 'ep1', name: 'My Episode', timestamp: 1700000000000, duration_seconds: 45 }),
      ];
      connectionManager._emit('message', {
        type: 'episode_list',
        episodes,
      } as EpisodeListMessage);

      const nameEl = container.querySelector('.episode-name');
      const durationEl = container.querySelector('.episode-duration');
      expect(nameEl?.textContent).toBe('My Episode');
      expect(durationEl?.textContent).toBe('00:45');
    });

    it('includes a Replay button for each episode', () => {
      connectionManager._emit('message', {
        type: 'episode_list',
        episodes: [createEpisodeRecord()],
      } as EpisodeListMessage);

      const replayBtn = container.querySelector('.episode-replay-button');
      expect(replayBtn).not.toBeNull();
    });

    it('requests episode list after recording stops', () => {
      // Start recording
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'recording',
        elapsed_seconds: 0,
      } as RecordingStatusMessage);

      // Clear previous send calls
      (connectionManager.send as ReturnType<typeof vi.fn>).mockClear();

      // Stop recording
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'idle',
      } as RecordingStatusMessage);

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'list_episodes',
      });
    });
  });

  describe('replay (Req 4.6, 4.7, 4.9)', () => {
    beforeEach(() => {
      // Populate episode list
      connectionManager._emit('message', {
        type: 'episode_list',
        episodes: [createEpisodeRecord({ id: 'ep_test', name: 'Test' })],
      } as EpisodeListMessage);
    });

    it('sends replay_episode command when Replay clicked', () => {
      const replayBtn = container.querySelector('.episode-replay-button') as HTMLButtonElement;
      replayBtn.click();
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'replay_episode',
        episode_id: 'ep_test',
      });
    });

    it('shows replay progress indicator during playback', () => {
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 5,
        total_seconds: 30,
        episode_id: 'ep_test',
      } as RecordingStatusMessage);

      const progress = container.querySelector('.episode-replay-progress') as HTMLElement;
      expect(progress.style.display).toBe('block');
      expect(progress.textContent).toContain('00:05');
      expect(progress.textContent).toContain('00:30');
    });

    it('shows Stop Replay button during playback', () => {
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      const stopBtn = container.querySelector('.episode-stop-replay-button') as HTMLElement;
      expect(stopBtn.style.display).toBe('inline-block');
    });

    it('sends stop_replay command when Stop Replay clicked', () => {
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      const stopBtn = container.querySelector('.episode-stop-replay-button') as HTMLButtonElement;
      stopBtn.click();
      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'episode_control',
        command: 'stop_replay',
      });
    });

    it('disables replay buttons during playback', () => {
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      const replayBtn = container.querySelector('.episode-replay-button') as HTMLButtonElement;
      expect(replayBtn.disabled).toBe(true);
    });

    it('calls onReplayStateChange(true) when replay starts', () => {
      const callback = vi.fn();
      panel.setOnReplayStateChange(callback);

      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      expect(callback).toHaveBeenCalledWith(true);
    });

    it('calls onReplayStateChange(false) when replay ends', () => {
      const callback = vi.fn();
      panel.setOnReplayStateChange(callback);

      // Start replay
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      // End replay
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'idle',
      } as RecordingStatusMessage);

      expect(callback).toHaveBeenCalledWith(false);
    });

    it('updates replay progress at least once per second', () => {
      connectionManager._emit('message', {
        type: 'recording_status',
        state: 'replaying',
        elapsed_seconds: 0,
        total_seconds: 30,
      } as RecordingStatusMessage);

      vi.advanceTimersByTime(3000);

      const progress = container.querySelector('.episode-replay-progress') as HTMLElement;
      expect(progress.textContent).toContain('00:03');
    });
  });

  describe('unavailable state (Req 4.8)', () => {
    it('shows unavailable message when recorder is unavailable', () => {
      panel.setUnavailable();

      const msg = container.querySelector('.episode-unavailable') as HTMLElement;
      expect(msg.style.display).toBe('block');
    });

    it('disables all buttons when unavailable', () => {
      panel.setUnavailable();

      const startBtn = container.querySelector('.episode-start-button') as HTMLButtonElement;
      expect(startBtn.disabled).toBe(true);
    });

    it('handles RECORDER_UNAVAILABLE error message', () => {
      const errorMsg: ErrorMessage = {
        type: 'error',
        code: 'RECORDER_UNAVAILABLE',
        message: 'Episode recorder not running',
      };
      connectionManager._emit('message', errorMsg);

      expect(panel.getState()).toBe('unavailable');
    });

    it('can return to available state', () => {
      panel.setUnavailable();
      panel.setAvailable();
      expect(panel.getState()).toBe('idle');

      const msg = container.querySelector('.episode-unavailable') as HTMLElement;
      expect(msg.style.display).toBe('none');
    });
  });

  describe('error display (Req 4.10)', () => {
    it('displays start_recording error message', () => {
      const errorMsg: ErrorMessage = {
        type: 'error',
        code: 'START_RECORDING_FAILED',
        message: 'Missing required topics',
      };
      connectionManager._emit('message', errorMsg);

      const errorDisplay = container.querySelector('.episode-error') as HTMLElement;
      expect(errorDisplay.style.display).toBe('block');
      expect(errorDisplay.textContent).toBe('Missing required topics');
    });

    it('error message stays visible for at least 5 seconds', () => {
      const errorMsg: ErrorMessage = {
        type: 'error',
        code: 'START_RECORDING_FAILED',
        message: 'Error message',
      };
      connectionManager._emit('message', errorMsg);

      // Advance 4 seconds - error should still be visible
      vi.advanceTimersByTime(4000);
      const errorDisplay = container.querySelector('.episode-error') as HTMLElement;
      expect(errorDisplay.style.display).toBe('block');

      // Advance past 5 seconds - error should be hidden
      vi.advanceTimersByTime(1500);
      expect(errorDisplay.style.display).toBe('none');
    });
  });
});
