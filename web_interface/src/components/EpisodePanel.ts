/**
 * EpisodePanel — episode recording and replay control for the SO-100 robot arm.
 *
 * Features:
 * - "Start Recording", "Stop & Save", "Discard" buttons
 * - Recording indicator: red dot + elapsed time counter (updated ≥1/s)
 * - Disable "Start" button during recording
 * - Episode list showing name, timestamp, duration (sorted most recent first, max 100)
 * - "Replay" button per episode
 * - Replay progress indicator (elapsed/total, updated ≥1/s)
 * - "Stop Replay" button during playback
 * - Disable all manual controls during replay (sliders, Cartesian, teleop)
 * - Re-enable controls within 1s of replay end
 * - Show disabled state with message when recorder unavailable
 * - Display start_recording errors for ≥5s
 *
 * Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  EpisodeControlMessage,
  EpisodeListMessage,
  EpisodeRecord,
  RecordingStatusMessage,
  ServerMessage,
} from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Maximum number of episodes to display in the list */
const MAX_EPISODES = 100;

/** Minimum duration (ms) to display error messages */
const ERROR_DISPLAY_DURATION_MS = 5000;

/** Interval (ms) for updating elapsed time counters */
const TIMER_INTERVAL_MS = 1000;

// ─── Helpers ────────────────────────────────────────────────────────────────

/**
 * Format seconds into a "MM:SS" string.
 */
export function formatElapsedTime(seconds: number): string {
  const totalSeconds = Math.floor(Math.max(0, seconds));
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format an epoch millisecond timestamp to a human-readable date/time string.
 */
export function formatTimestamp(epochMs: number): string {
  const date = new Date(epochMs);
  return date.toLocaleString();
}

/**
 * Sort episodes by timestamp descending (most recent first) and cap at MAX_EPISODES.
 */
export function sortAndCapEpisodes(episodes: EpisodeRecord[]): EpisodeRecord[] {
  const sorted = [...episodes].sort((a, b) => b.timestamp - a.timestamp);
  return sorted.slice(0, MAX_EPISODES);
}

// ─── Types ──────────────────────────────────────────────────────────────────

/** Callback type for notifying parent when replay state changes (to disable/enable controls) */
export type ReplayStateChangeCallback = (replaying: boolean) => void;

/** Internal state of the episode panel */
type PanelState = 'idle' | 'recording' | 'replaying' | 'unavailable';

// ─── EpisodePanel ───────────────────────────────────────────────────────────

export class EpisodePanel {
  private readonly connectionManager: ConnectionManager;
  private onReplayStateChange: ReplayStateChangeCallback | null = null;

  // State
  private state: PanelState = 'idle';
  private episodes: EpisodeRecord[] = [];
  private recordingStartTime: number = 0;
  private replayElapsed: number = 0;
  private replayTotal: number = 0;
  private errorMessage: string | null = null;
  private errorTimer: ReturnType<typeof setTimeout> | null = null;
  private elapsedTimer: ReturnType<typeof setInterval> | null = null;

  // DOM elements
  private container: HTMLElement | null = null;
  private startButton: HTMLButtonElement | null = null;
  private stopSaveButton: HTMLButtonElement | null = null;
  private discardButton: HTMLButtonElement | null = null;
  private recordingIndicator: HTMLDivElement | null = null;
  private episodeListElement: HTMLUListElement | null = null;
  private replayProgressElement: HTMLDivElement | null = null;
  private stopReplayButton: HTMLButtonElement | null = null;
  private unavailableMessage: HTMLDivElement | null = null;
  private errorDisplay: HTMLDivElement | null = null;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;
    this.connectionManager.on('message', this.handleMessage.bind(this));
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Set the callback that fires when replay state changes.
   * Used to disable/enable manual controls (sliders, Cartesian, teleop).
   */
  setOnReplayStateChange(callback: ReplayStateChangeCallback): void {
    this.onReplayStateChange = callback;
  }

  /**
   * Mount the episode panel into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('episode-panel');

    const heading = document.createElement('h3');
    heading.textContent = 'Episode Recording';
    this.container.appendChild(heading);

    // Unavailable message (shown when recorder is not available)
    this.unavailableMessage = document.createElement('div');
    this.unavailableMessage.classList.add('episode-unavailable');
    this.unavailableMessage.textContent =
      'Episode recorder service is unavailable.';
    this.unavailableMessage.style.display = 'none';
    this.container.appendChild(this.unavailableMessage);

    // Control buttons
    const controlsDiv = document.createElement('div');
    controlsDiv.classList.add('episode-controls');

    this.startButton = document.createElement('button');
    this.startButton.textContent = 'Start Recording';
    this.startButton.classList.add('episode-start-button');
    this.startButton.addEventListener('click', this.handleStartRecording.bind(this));
    controlsDiv.appendChild(this.startButton);

    this.stopSaveButton = document.createElement('button');
    this.stopSaveButton.textContent = 'Stop & Save';
    this.stopSaveButton.classList.add('episode-stop-save-button');
    this.stopSaveButton.addEventListener('click', this.handleStopSave.bind(this));
    controlsDiv.appendChild(this.stopSaveButton);

    this.discardButton = document.createElement('button');
    this.discardButton.textContent = 'Discard';
    this.discardButton.classList.add('episode-discard-button');
    this.discardButton.addEventListener('click', this.handleDiscard.bind(this));
    controlsDiv.appendChild(this.discardButton);

    this.container.appendChild(controlsDiv);

    // Recording indicator (red dot + elapsed time)
    this.recordingIndicator = document.createElement('div');
    this.recordingIndicator.classList.add('episode-recording-indicator');
    this.recordingIndicator.style.display = 'none';
    const redDot = document.createElement('span');
    redDot.classList.add('episode-red-dot');
    redDot.textContent = '●';
    this.recordingIndicator.appendChild(redDot);
    const elapsedSpan = document.createElement('span');
    elapsedSpan.classList.add('episode-elapsed-time');
    elapsedSpan.textContent = '00:00';
    this.recordingIndicator.appendChild(elapsedSpan);
    this.container.appendChild(this.recordingIndicator);

    // Replay progress indicator
    this.replayProgressElement = document.createElement('div');
    this.replayProgressElement.classList.add('episode-replay-progress');
    this.replayProgressElement.style.display = 'none';
    this.container.appendChild(this.replayProgressElement);

    // Stop Replay button
    this.stopReplayButton = document.createElement('button');
    this.stopReplayButton.textContent = 'Stop Replay';
    this.stopReplayButton.classList.add('episode-stop-replay-button');
    this.stopReplayButton.style.display = 'none';
    this.stopReplayButton.addEventListener('click', this.handleStopReplay.bind(this));
    this.container.appendChild(this.stopReplayButton);

    // Error display
    this.errorDisplay = document.createElement('div');
    this.errorDisplay.classList.add('episode-error');
    this.errorDisplay.style.display = 'none';
    this.container.appendChild(this.errorDisplay);

    // Episode list
    const listHeading = document.createElement('h4');
    listHeading.textContent = 'Recorded Episodes';
    this.container.appendChild(listHeading);

    this.episodeListElement = document.createElement('ul');
    this.episodeListElement.classList.add('episode-list');
    this.container.appendChild(this.episodeListElement);

    // Initial UI state
    this.updateUI();

    // Request episode list on mount
    this.requestEpisodeList();
  }

  /**
   * Remove the component from the DOM and clean up timers.
   */
  unmount(): void {
    this.clearTimers();

    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('episode-panel');
    }

    this.container = null;
    this.startButton = null;
    this.stopSaveButton = null;
    this.discardButton = null;
    this.recordingIndicator = null;
    this.episodeListElement = null;
    this.replayProgressElement = null;
    this.stopReplayButton = null;
    this.unavailableMessage = null;
    this.errorDisplay = null;
  }

  /**
   * Handle incoming server messages relevant to the episode panel.
   */
  handleServerMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'episode_list':
        this.handleEpisodeList(message as EpisodeListMessage);
        break;
      case 'recording_status':
        this.handleRecordingStatus(message as RecordingStatusMessage);
        break;
      case 'error':
        if (message.code === 'RECORDER_UNAVAILABLE') {
          this.setUnavailable();
        } else if (
          message.code === 'START_RECORDING_FAILED' ||
          message.code === 'RECORDING_ERROR'
        ) {
          this.showError(message.message);
        }
        break;
    }
  }

  /**
   * Get the current panel state.
   */
  getState(): PanelState {
    return this.state;
  }

  /**
   * Get the current list of episodes.
   */
  getEpisodes(): EpisodeRecord[] {
    return [...this.episodes];
  }

  /**
   * Mark the panel as unavailable (recorder not reachable).
   */
  setUnavailable(): void {
    this.state = 'unavailable';
    this.clearTimers();
    this.updateUI();
  }

  /**
   * Mark the panel as available again.
   */
  setAvailable(): void {
    if (this.state === 'unavailable') {
      this.state = 'idle';
      this.updateUI();
    }
  }

  // ─── Private: Message Handlers ──────────────────────────────────────────

  private handleMessage(message: ServerMessage): void {
    this.handleServerMessage(message);
  }

  private handleEpisodeList(message: EpisodeListMessage): void {
    this.episodes = sortAndCapEpisodes(message.episodes);
    this.renderEpisodeList();
  }

  private handleRecordingStatus(message: RecordingStatusMessage): void {
    const previousState = this.state;

    switch (message.state) {
      case 'idle':
        this.state = 'idle';
        this.clearTimers();
        // If transitioning from replaying, notify to re-enable controls
        if (previousState === 'replaying') {
          this.notifyReplayStateChange(false);
        }
        break;

      case 'recording':
        this.state = 'recording';
        if (previousState !== 'recording') {
          this.recordingStartTime = Date.now();
          this.startElapsedTimer();
        }
        if (message.elapsed_seconds !== undefined) {
          this.updateRecordingElapsed(message.elapsed_seconds);
        }
        break;

      case 'replaying':
        this.state = 'replaying';
        this.replayElapsed = message.elapsed_seconds ?? 0;
        this.replayTotal = message.total_seconds ?? 0;
        if (previousState !== 'replaying') {
          this.notifyReplayStateChange(true);
          this.startReplayTimer();
        }
        break;
    }

    this.updateUI();

    // Request updated episode list after recording completes
    if (previousState === 'recording' && this.state === 'idle') {
      this.requestEpisodeList();
    }
  }

  // ─── Private: User Actions ──────────────────────────────────────────────

  private handleStartRecording(): void {
    if (this.state !== 'idle') return;

    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'start_recording',
    };
    this.connectionManager.send(message);
  }

  private handleStopSave(): void {
    if (this.state !== 'recording') return;

    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'stop_recording',
    };
    this.connectionManager.send(message);
  }

  private handleDiscard(): void {
    if (this.state !== 'recording') return;

    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'discard_recording',
    };
    this.connectionManager.send(message);
  }

  private handleReplayEpisode(episodeId: string): void {
    if (this.state !== 'idle') return;

    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'replay_episode',
      episode_id: episodeId,
    };
    this.connectionManager.send(message);
  }

  private handleStopReplay(): void {
    if (this.state !== 'replaying') return;

    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'stop_replay',
    };
    this.connectionManager.send(message);
  }

  // ─── Private: Timer Management ─────────────────────────────────────────

  private startElapsedTimer(): void {
    this.clearElapsedTimer();
    this.elapsedTimer = setInterval(() => {
      if (this.state === 'recording') {
        const elapsed = (Date.now() - this.recordingStartTime) / 1000;
        this.updateRecordingElapsed(elapsed);
      }
    }, TIMER_INTERVAL_MS);
  }

  private startReplayTimer(): void {
    this.clearElapsedTimer();
    this.elapsedTimer = setInterval(() => {
      if (this.state === 'replaying') {
        this.replayElapsed += 1;
        this.updateReplayProgress();
      }
    }, TIMER_INTERVAL_MS);
  }

  private clearElapsedTimer(): void {
    if (this.elapsedTimer !== null) {
      clearInterval(this.elapsedTimer);
      this.elapsedTimer = null;
    }
  }

  private clearTimers(): void {
    this.clearElapsedTimer();
    if (this.errorTimer !== null) {
      clearTimeout(this.errorTimer);
      this.errorTimer = null;
    }
  }

  // ─── Private: Notifications ─────────────────────────────────────────────

  private notifyReplayStateChange(replaying: boolean): void {
    if (this.onReplayStateChange) {
      this.onReplayStateChange(replaying);
    }
  }

  private requestEpisodeList(): void {
    const message: EpisodeControlMessage = {
      type: 'episode_control',
      command: 'list_episodes',
    };
    this.connectionManager.send(message);
  }

  // ─── Private: Error Display ─────────────────────────────────────────────

  private showError(message: string): void {
    this.errorMessage = message;
    this.renderError();

    // Clear any existing error timer
    if (this.errorTimer !== null) {
      clearTimeout(this.errorTimer);
    }

    // Auto-clear error after minimum display duration
    this.errorTimer = setTimeout(() => {
      this.errorMessage = null;
      this.errorTimer = null;
      this.renderError();
    }, ERROR_DISPLAY_DURATION_MS);
  }

  // ─── Private: UI Rendering ─────────────────────────────────────────────

  private updateUI(): void {
    this.updateButtonStates();
    this.renderRecordingIndicator();
    this.renderReplayControls();
    this.renderUnavailableState();
    this.renderEpisodeList();
  }

  private updateButtonStates(): void {
    if (!this.startButton || !this.stopSaveButton || !this.discardButton) return;

    const isUnavailable = this.state === 'unavailable';
    const isIdle = this.state === 'idle';
    const isRecording = this.state === 'recording';
    const isReplaying = this.state === 'replaying';

    // Start button: enabled only when idle and available
    this.startButton.disabled = !isIdle || isUnavailable;

    // Stop & Save: enabled only when recording
    this.stopSaveButton.disabled = !isRecording;

    // Discard: enabled only when recording
    this.discardButton.disabled = !isRecording;

    // Disable all during replay
    if (isReplaying) {
      this.startButton.disabled = true;
      this.stopSaveButton.disabled = true;
      this.discardButton.disabled = true;
    }
  }

  private renderRecordingIndicator(): void {
    if (!this.recordingIndicator) return;

    if (this.state === 'recording') {
      this.recordingIndicator.style.display = 'flex';
    } else {
      this.recordingIndicator.style.display = 'none';
    }
  }

  private updateRecordingElapsed(seconds: number): void {
    if (!this.recordingIndicator) return;
    const elapsedSpan = this.recordingIndicator.querySelector('.episode-elapsed-time');
    if (elapsedSpan) {
      elapsedSpan.textContent = formatElapsedTime(seconds);
    }
  }

  private renderReplayControls(): void {
    if (!this.replayProgressElement || !this.stopReplayButton) return;

    if (this.state === 'replaying') {
      this.replayProgressElement.style.display = 'block';
      this.stopReplayButton.style.display = 'inline-block';
      this.updateReplayProgress();
    } else {
      this.replayProgressElement.style.display = 'none';
      this.stopReplayButton.style.display = 'none';
    }
  }

  private updateReplayProgress(): void {
    if (!this.replayProgressElement) return;
    const elapsedStr = formatElapsedTime(this.replayElapsed);
    const totalStr = formatElapsedTime(this.replayTotal);
    this.replayProgressElement.textContent = `Replaying: ${elapsedStr} / ${totalStr}`;
  }

  private renderUnavailableState(): void {
    if (!this.unavailableMessage) return;

    if (this.state === 'unavailable') {
      this.unavailableMessage.style.display = 'block';
    } else {
      this.unavailableMessage.style.display = 'none';
    }
  }

  private renderError(): void {
    if (!this.errorDisplay) return;

    if (this.errorMessage) {
      this.errorDisplay.textContent = this.errorMessage;
      this.errorDisplay.style.display = 'block';
    } else {
      this.errorDisplay.textContent = '';
      this.errorDisplay.style.display = 'none';
    }
  }

  private renderEpisodeList(): void {
    if (!this.episodeListElement) return;

    this.episodeListElement.innerHTML = '';

    if (this.episodes.length === 0) {
      const emptyLi = document.createElement('li');
      emptyLi.classList.add('episode-list-empty');
      emptyLi.textContent = 'No episodes recorded yet.';
      this.episodeListElement.appendChild(emptyLi);
      return;
    }

    for (const episode of this.episodes) {
      const li = document.createElement('li');
      li.classList.add('episode-item');
      li.dataset.episodeId = episode.id;

      const nameSpan = document.createElement('span');
      nameSpan.classList.add('episode-name');
      nameSpan.textContent = episode.name;
      li.appendChild(nameSpan);

      const timestampSpan = document.createElement('span');
      timestampSpan.classList.add('episode-timestamp');
      timestampSpan.textContent = formatTimestamp(episode.timestamp);
      li.appendChild(timestampSpan);

      const durationSpan = document.createElement('span');
      durationSpan.classList.add('episode-duration');
      durationSpan.textContent = formatElapsedTime(episode.duration_seconds);
      li.appendChild(durationSpan);

      const replayBtn = document.createElement('button');
      replayBtn.classList.add('episode-replay-button');
      replayBtn.textContent = 'Replay';
      replayBtn.disabled = this.state !== 'idle';
      replayBtn.addEventListener('click', () => this.handleReplayEpisode(episode.id));
      li.appendChild(replayBtn);

      this.episodeListElement.appendChild(li);
    }
  }
}
