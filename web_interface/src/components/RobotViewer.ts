/**
 * RobotViewer — Wires ConnectionManager to RobotModel3D for live joint state updates.
 *
 * Responsibilities:
 * - Listens for `joint_state` messages from ConnectionManager and updates the 3D model
 * - Validates incoming joint states (exactly 6 position values required)
 * - Retains last valid pose on connection loss
 * - Provides a connection status indicator element
 *
 * Validates: Requirements 7.2, 7.7
 */

import { ConnectionManager } from '../services/ConnectionManager';
import { RobotModel3D } from './RobotModel3D';
import type { ServerMessage, JointStateMessage, ConnectionState } from '../types';

/** Number of joints expected in a valid joint state message */
const EXPECTED_JOINT_COUNT = 6;

/** Connection status indicator visual states */
export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

/**
 * RobotViewer connects a ConnectionManager and RobotModel3D, handling:
 * - Joint state message validation (exactly 6 positions)
 * - Forwarding valid joint angles to the 3D model
 * - Tracking connection status for UI display
 * - Retaining the last valid pose on connection loss
 */
export class RobotViewer {
  private readonly connectionManager: ConnectionManager;
  private readonly robotModel: RobotModel3D;

  /** Last valid joint positions received (retained on connection loss) */
  private lastValidPositions: number[] | null = null;

  /** Current connection status for external consumption */
  private _connectionStatus: ConnectionStatus = 'disconnected';

  /** Listeners for connection status changes */
  private statusListeners: Array<(status: ConnectionStatus) => void> = [];

  /** Bound handlers for cleanup */
  private readonly handleMessage: (message: ServerMessage) => void;
  private readonly handleStateChange: (state: ConnectionState) => void;

  constructor(connectionManager: ConnectionManager, robotModel: RobotModel3D) {
    this.connectionManager = connectionManager;
    this.robotModel = robotModel;

    // Bind handlers for proper removal later
    this.handleMessage = this.onMessage.bind(this);
    this.handleStateChange = this.onStateChange.bind(this);

    // Subscribe to ConnectionManager events
    this.connectionManager.on('message', this.handleMessage);
    this.connectionManager.on('stateChange', this.handleStateChange);

    // Initialize status from current ConnectionManager state
    this.updateConnectionStatus(this.connectionManager.getState());
  }

  /** Current connection status */
  get connectionStatus(): ConnectionStatus {
    return this._connectionStatus;
  }

  /** Last valid joint positions received, or null if none received yet */
  get lastPositions(): number[] | null {
    return this.lastValidPositions;
  }

  /**
   * Register a listener for connection status changes.
   */
  onStatusChange(listener: (status: ConnectionStatus) => void): void {
    this.statusListeners.push(listener);
  }

  /**
   * Remove a status change listener.
   */
  offStatusChange(listener: (status: ConnectionStatus) => void): void {
    const index = this.statusListeners.indexOf(listener);
    if (index !== -1) {
      this.statusListeners.splice(index, 1);
    }
  }

  /**
   * Handles incoming server messages. Filters for joint_state messages,
   * validates the position array length, and updates the 3D model.
   */
  private onMessage(message: ServerMessage): void {
    if (message.type !== 'joint_state') {
      return;
    }

    const jointState = message as JointStateMessage;

    // Validate: must have exactly 6 position values
    if (!this.isValidJointState(jointState)) {
      return; // Ignore invalid messages — retain last valid pose
    }

    // Store valid positions and update model
    this.lastValidPositions = [...jointState.joints.positions];
    this.robotModel.updateJointAngles(jointState.joints.positions);
  }

  /**
   * Validates a joint state message has exactly 6 position values.
   */
  private isValidJointState(message: JointStateMessage): boolean {
    const positions = message.joints?.positions;
    if (!Array.isArray(positions)) {
      return false;
    }
    if (positions.length !== EXPECTED_JOINT_COUNT) {
      return false;
    }
    // Ensure all values are finite numbers
    for (const pos of positions) {
      if (typeof pos !== 'number' || !isFinite(pos)) {
        return false;
      }
    }
    return true;
  }

  /**
   * Handles connection state changes. Maps ConnectionManager states
   * to the simplified connection status indicator.
   */
  private onStateChange(state: ConnectionState): void {
    this.updateConnectionStatus(state);
  }

  /**
   * Maps a ConnectionState to a ConnectionStatus and notifies listeners.
   */
  private updateConnectionStatus(state: ConnectionState): void {
    const newStatus = this.mapStateToStatus(state);
    if (newStatus !== this._connectionStatus) {
      this._connectionStatus = newStatus;
      this.emitStatusChange(newStatus);
    }
  }

  /**
   * Maps ConnectionManager's state to the viewer's simplified status.
   */
  private mapStateToStatus(state: ConnectionState): ConnectionStatus {
    switch (state) {
      case 'connected':
        return 'connected';
      case 'connecting':
      case 'reconnecting':
        return 'reconnecting';
      case 'disconnected':
        return 'disconnected';
      default:
        return 'disconnected';
    }
  }

  /**
   * Emits the connection status change to all registered listeners.
   */
  private emitStatusChange(status: ConnectionStatus): void {
    for (const listener of this.statusListeners) {
      listener(status);
    }
  }

  /**
   * Disconnects event listeners and cleans up resources.
   * The last valid pose is retained in the 3D model.
   */
  dispose(): void {
    this.connectionManager.off('message', this.handleMessage);
    this.connectionManager.off('stateChange', this.handleStateChange);
    this.statusListeners = [];
  }
}
