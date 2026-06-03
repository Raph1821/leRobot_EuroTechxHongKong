/**
 * PoseManager — save, list, delete, and select poses for the SO-100 robot arm.
 *
 * Features:
 * - "Save Pose" button: prompts for name (1–64 chars), stores current joint state
 * - Max 50 poses per session
 * - Displays saved pose list with name, select-to-command and delete
 * - Stores poses in browser session storage
 * - Selecting a pose sends a trajectory_goal message via WebSocket
 * - "Play Sequence" executes all saved poses as ordered waypoints
 * - Progress indicator during trajectory execution
 * - Error notification on trajectory failure/preemption
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  JointStateMessage,
  SavedPose,
  TrajectoryGoalMessage,
  TrajectoryStatusMessage,
} from '../types';
import { ARM_JOINT_NAMES } from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Maximum number of poses that can be saved per session */
const MAX_POSES = 50;

/** Minimum pose name length */
const MIN_NAME_LENGTH = 1;

/** Maximum pose name length */
const MAX_NAME_LENGTH = 64;

/** Session storage key for saved poses */
const STORAGE_KEY = 'so100_saved_poses';

/** Default time_from_start (seconds) when commanding a pose */
const DEFAULT_DURATION_SECONDS = 2.0;

/** Minimum interval for trajectory playback */
const MIN_INTERVAL_SECONDS = 0.5;

/** Maximum interval for trajectory playback */
const MAX_INTERVAL_SECONDS = 30.0;

/** Minimum number of poses required for sequence playback */
const MIN_POSES_FOR_SEQUENCE = 2;

// ─── Validation Helpers ─────────────────────────────────────────────────────

/**
 * Validate a pose name: must be 1–64 characters.
 * Returns an error message if invalid, or null if valid.
 */
export function validatePoseName(name: string): string | null {
  if (name.length < MIN_NAME_LENGTH) {
    return 'Pose name must be at least 1 character.';
  }
  if (name.length > MAX_NAME_LENGTH) {
    return `Pose name must be at most ${MAX_NAME_LENGTH} characters.`;
  }
  return null;
}

/**
 * Check whether the pose store can accept another pose.
 * Returns an error message if at capacity, or null if ok.
 */
export function validatePoseCapacity(currentCount: number): string | null {
  if (currentCount >= MAX_POSES) {
    return `Maximum of ${MAX_POSES} poses reached. Delete a pose before saving a new one.`;
  }
  return null;
}

/**
 * Build a trajectory goal message from an ordered list of poses.
 * Each waypoint's time_from_start = (index + 1) × intervalSeconds.
 *
 * @param poses - Non-empty array of saved poses with arm joint positions
 * @param intervalSeconds - Time between waypoints (0.5–30.0s)
 * @returns TrajectoryGoalMessage with waypoints matching pose count
 */
export function buildTrajectoryGoal(
  poses: SavedPose[],
  intervalSeconds: number
): TrajectoryGoalMessage {
  const clampedInterval = Math.max(
    MIN_INTERVAL_SECONDS,
    Math.min(MAX_INTERVAL_SECONDS, intervalSeconds)
  );

  const waypoints = poses.map((pose, index) => ({
    positions: { ...pose.positions },
    time_from_start: (index + 1) * clampedInterval,
  }));

  return {
    type: 'trajectory_goal',
    waypoints,
  };
}

// ─── PoseManager ────────────────────────────────────────────────────────────

export class PoseManager {
  private readonly connectionManager: ConnectionManager;
  private poses: SavedPose[] = [];
  private latestJointPositions: Record<string, number> = {};
  private durationSeconds: number = DEFAULT_DURATION_SECONDS;

  // Trajectory playback state
  private _isPlaying: boolean = false;
  private _lastTrajectoryError: string | null = null;

  // DOM elements (created on mount)
  private container: HTMLElement | null = null;
  private poseListElement: HTMLUListElement | null = null;
  private saveButton: HTMLButtonElement | null = null;
  private emptyMessage: HTMLParagraphElement | null = null;
  private playSequenceButton: HTMLButtonElement | null = null;
  private playSequenceMessage: HTMLParagraphElement | null = null;
  private progressIndicator: HTMLDivElement | null = null;
  private errorNotification: HTMLDivElement | null = null;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;

    // Load poses from session storage
    this.loadFromStorage();

    // Listen for joint state and trajectory status messages
    this.connectionManager.on('message', this.handleMessage.bind(this));
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the pose manager into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('pose-manager');

    const heading = document.createElement('h3');
    heading.textContent = 'Saved Poses';
    this.container.appendChild(heading);

    // Save Pose button
    this.saveButton = document.createElement('button');
    this.saveButton.textContent = 'Save Pose';
    this.saveButton.classList.add('pose-save-button');
    this.saveButton.addEventListener('click', this.handleSavePose.bind(this));
    this.container.appendChild(this.saveButton);

    // Play Sequence button
    this.playSequenceButton = document.createElement('button');
    this.playSequenceButton.textContent = 'Play Sequence';
    this.playSequenceButton.classList.add('pose-play-sequence-button');
    this.playSequenceButton.addEventListener('click', this.handlePlaySequence.bind(this));
    this.container.appendChild(this.playSequenceButton);

    // Play Sequence informative message (shown when <2 poses)
    this.playSequenceMessage = document.createElement('p');
    this.playSequenceMessage.classList.add('pose-play-sequence-message');
    this.playSequenceMessage.textContent = 'At least 2 poses are required to play a sequence.';
    this.container.appendChild(this.playSequenceMessage);

    // Progress indicator (shown during trajectory execution)
    this.progressIndicator = document.createElement('div');
    this.progressIndicator.classList.add('pose-progress-indicator');
    this.progressIndicator.textContent = 'Executing trajectory…';
    this.progressIndicator.style.display = 'none';
    this.container.appendChild(this.progressIndicator);

    // Error notification (shown on trajectory failure/preemption)
    this.errorNotification = document.createElement('div');
    this.errorNotification.classList.add('pose-error-notification');
    this.errorNotification.style.display = 'none';
    const dismissBtn = document.createElement('button');
    dismissBtn.textContent = '✕';
    dismissBtn.classList.add('pose-error-dismiss');
    dismissBtn.addEventListener('click', this.dismissError.bind(this));
    this.errorNotification.appendChild(dismissBtn);
    this.container.appendChild(this.errorNotification);

    // Empty state message
    this.emptyMessage = document.createElement('p');
    this.emptyMessage.classList.add('pose-empty-message');
    this.emptyMessage.textContent = 'No poses saved yet.';
    this.container.appendChild(this.emptyMessage);

    // Pose list
    this.poseListElement = document.createElement('ul');
    this.poseListElement.classList.add('pose-list');
    this.container.appendChild(this.poseListElement);

    this.renderPoseList();
    this.updatePlaySequenceState();
  }

  /**
   * Remove the component from the DOM and clean up.
   */
  unmount(): void {
    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('pose-manager');
    }
    this.poseListElement = null;
    this.saveButton = null;
    this.emptyMessage = null;
    this.playSequenceButton = null;
    this.playSequenceMessage = null;
    this.progressIndicator = null;
    this.errorNotification = null;
    this.container = null;
  }

  /**
   * Get all saved poses (for testing/external access).
   */
  getPoses(): SavedPose[] {
    return [...this.poses];
  }

  /**
   * Get the count of saved poses.
   */
  getPoseCount(): number {
    return this.poses.length;
  }

  /**
   * Save a pose with the given name and current joint positions.
   * Returns an error message if validation fails, or null on success.
   */
  savePose(name: string): string | null {
    // Validate name
    const nameError = validatePoseName(name);
    if (nameError) return nameError;

    // Validate capacity
    const capacityError = validatePoseCapacity(this.poses.length);
    if (capacityError) return capacityError;

    // Ensure we have joint positions
    if (Object.keys(this.latestJointPositions).length === 0) {
      return 'No joint state available. Wait for a connection to the robot.';
    }

    // Create the pose using only arm joint positions
    const positions: Record<string, number> = {};
    for (const jointName of ARM_JOINT_NAMES) {
      const pos = this.latestJointPositions[jointName];
      if (pos !== undefined) {
        positions[jointName] = pos;
      }
    }

    const pose: SavedPose = {
      name,
      positions,
      savedAt: Date.now(),
    };

    this.poses.push(pose);
    this.saveToStorage();
    this.renderPoseList();
    this.updatePlaySequenceState();

    return null;
  }

  /**
   * Delete a pose by index.
   */
  deletePose(index: number): void {
    if (index < 0 || index >= this.poses.length) return;
    this.poses.splice(index, 1);
    this.saveToStorage();
    this.renderPoseList();
    this.updatePlaySequenceState();
  }

  /**
   * Select a pose and send it as a trajectory goal via WebSocket.
   */
  selectPose(index: number): boolean {
    if (index < 0 || index >= this.poses.length) return false;
    if (this._isPlaying) return false;

    const pose = this.poses[index];

    if (this.connectionManager.getState() !== 'connected') {
      return false;
    }

    const message: TrajectoryGoalMessage = {
      type: 'trajectory_goal',
      waypoints: [
        {
          positions: { ...pose.positions },
          time_from_start: this.durationSeconds,
        },
      ],
    };

    const sent = this.connectionManager.send(message);
    if (sent) {
      // Clear any previous error when new command is issued (Req 9.5)
      this.clearError();
    }
    return sent;
  }

  /**
   * Set the duration (time_from_start) used when commanding a pose.
   */
  setDuration(seconds: number): void {
    this.durationSeconds = Math.max(0.5, Math.min(30.0, seconds));
  }

  /**
   * Get the current duration setting.
   */
  getDuration(): number {
    return this.durationSeconds;
  }

  /**
   * Update the latest joint positions from a joint state message.
   */
  updateFromJointState(jointState: JointStateMessage): void {
    const { names, positions } = jointState.joints;
    for (let i = 0; i < names.length; i++) {
      this.latestJointPositions[names[i]] = positions[i];
    }
  }

  /**
   * Play all saved poses as a trajectory sequence.
   * Uses the configured duration as the interval between waypoints.
   *
   * Returns true if the trajectory was sent, false otherwise.
   */
  playSequence(intervalSeconds?: number): boolean {
    if (this.poses.length < MIN_POSES_FOR_SEQUENCE) {
      return false;
    }

    if (this._isPlaying) {
      return false;
    }

    if (this.connectionManager.getState() !== 'connected') {
      return false;
    }

    const interval = intervalSeconds ?? this.durationSeconds;
    const message = buildTrajectoryGoal(this.poses, interval);
    const sent = this.connectionManager.send(message);

    if (sent) {
      this.setPlayingState(true);
      // Clear any previous error when new command is issued
      this.clearError();
    }

    return sent;
  }

  /**
   * Check whether a trajectory is currently being executed.
   */
  isPlaying(): boolean {
    return this._isPlaying;
  }

  /**
   * Check whether the Play Sequence function can be invoked.
   */
  canPlaySequence(): boolean {
    return this.poses.length >= MIN_POSES_FOR_SEQUENCE && !this._isPlaying;
  }

  /**
   * Get the last trajectory error message, or null if none.
   */
  getLastTrajectoryError(): string | null {
    return this._lastTrajectoryError;
  }

  /**
   * Dismiss the current error notification.
   */
  dismissError(): void {
    this._lastTrajectoryError = null;
    this.renderErrorNotification();
  }

  /**
   * Handle a trajectory status message from the server.
   */
  handleTrajectoryStatus(status: TrajectoryStatusMessage): void {
    switch (status.status) {
      case 'executing':
        // Trajectory is in progress — keep playing state
        break;
      case 'succeeded':
        this.setPlayingState(false);
        break;
      case 'aborted':
      case 'preempted':
        this.setPlayingState(false);
        this._lastTrajectoryError = `Trajectory ${status.status}: ${status.message}`;
        this.renderErrorNotification();
        break;
    }
  }

  // ─── Private Methods ────────────────────────────────────────────────────

  private handleMessage(message: { type: string }): void {
    if (message.type === 'joint_state') {
      this.updateFromJointState(message as JointStateMessage);
    } else if (message.type === 'trajectory_status') {
      this.handleTrajectoryStatus(message as TrajectoryStatusMessage);
    }
  }

  private handleSavePose(): void {
    // Prompt user for pose name
    const name = prompt('Enter pose name (1–64 characters):');
    if (name === null) return; // User cancelled

    const trimmed = name.trim();
    const error = this.savePose(trimmed);
    if (error) {
      alert(error);
    }
  }

  private handlePlaySequence(): void {
    this.playSequence();
  }

  private setPlayingState(playing: boolean): void {
    this._isPlaying = playing;
    this.updatePlaySequenceState();
    this.renderProgressIndicator();
    this.renderPoseList();
  }

  private clearError(): void {
    this._lastTrajectoryError = null;
    this.renderErrorNotification();
  }

  private updatePlaySequenceState(): void {
    if (!this.playSequenceButton || !this.playSequenceMessage) return;

    const canPlay = this.canPlaySequence();
    this.playSequenceButton.disabled = !canPlay;

    if (this.poses.length < MIN_POSES_FOR_SEQUENCE) {
      this.playSequenceMessage.style.display = 'block';
    } else {
      this.playSequenceMessage.style.display = 'none';
    }
  }

  private renderProgressIndicator(): void {
    if (!this.progressIndicator) return;
    this.progressIndicator.style.display = this._isPlaying ? 'block' : 'none';
  }

  private renderErrorNotification(): void {
    if (!this.errorNotification) return;

    if (this._lastTrajectoryError) {
      // Update the text content (keep dismiss button)
      const existingText = this.errorNotification.querySelector('.pose-error-text');
      if (existingText) {
        existingText.textContent = this._lastTrajectoryError;
      } else {
        const textSpan = document.createElement('span');
        textSpan.classList.add('pose-error-text');
        textSpan.textContent = this._lastTrajectoryError;
        this.errorNotification.insertBefore(textSpan, this.errorNotification.firstChild);
      }
      this.errorNotification.style.display = 'block';
    } else {
      this.errorNotification.style.display = 'none';
      const existingText = this.errorNotification.querySelector('.pose-error-text');
      if (existingText) {
        existingText.remove();
      }
    }
  }

  private renderPoseList(): void {
    if (!this.poseListElement || !this.emptyMessage) return;

    // Clear current list
    this.poseListElement.innerHTML = '';

    // Show/hide empty message
    if (this.poses.length === 0) {
      this.emptyMessage.style.display = 'block';
      this.poseListElement.style.display = 'none';
      this.updatePlaySequenceState();
      return;
    }

    this.emptyMessage.style.display = 'none';
    this.poseListElement.style.display = 'block';

    // Render each pose
    for (let i = 0; i < this.poses.length; i++) {
      const pose = this.poses[i];
      const li = document.createElement('li');
      li.classList.add('pose-item');
      li.dataset.index = String(i);

      // Pose name
      const nameSpan = document.createElement('span');
      nameSpan.classList.add('pose-name');
      nameSpan.textContent = pose.name;

      // Select button
      const selectBtn = document.createElement('button');
      selectBtn.classList.add('pose-select-button');
      selectBtn.textContent = 'Go';
      selectBtn.title = 'Move robot to this pose';
      selectBtn.disabled = this._isPlaying;
      selectBtn.addEventListener('click', () => this.selectPose(i));

      // Delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.classList.add('pose-delete-button');
      deleteBtn.textContent = '✕';
      deleteBtn.title = 'Delete this pose';
      deleteBtn.disabled = this._isPlaying;
      deleteBtn.addEventListener('click', () => this.deletePose(i));

      li.appendChild(nameSpan);
      li.appendChild(selectBtn);
      li.appendChild(deleteBtn);
      this.poseListElement.appendChild(li);
    }

    this.updatePlaySequenceState();
  }

  private saveToStorage(): void {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.poses));
    } catch {
      // Session storage unavailable or full — silently continue
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          // Validate each pose has required fields
          this.poses = parsed.filter(
            (p): p is SavedPose =>
              typeof p === 'object' &&
              p !== null &&
              typeof p.name === 'string' &&
              p.name.length >= MIN_NAME_LENGTH &&
              p.name.length <= MAX_NAME_LENGTH &&
              typeof p.positions === 'object' &&
              p.positions !== null &&
              typeof p.savedAt === 'number'
          );
          // Enforce max capacity on load
          if (this.poses.length > MAX_POSES) {
            this.poses = this.poses.slice(0, MAX_POSES);
          }
        }
      }
    } catch {
      // Session storage unavailable or data corrupted — start fresh
      this.poses = [];
    }
  }
}
