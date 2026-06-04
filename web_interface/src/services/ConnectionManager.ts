/**
 * ConnectionManager — WebSocket lifecycle and reconnection for the SO-100 web control interface.
 *
 * Implements the connection state machine:
 *   Connecting → Connected → Reconnecting → Disconnected
 *
 * Requirements: 10.1, 10.2, 10.3, 10.4
 */

import type {
  ConnectionState,
  ServerMessage,
  ClientMessage,
} from '../types';

// ─── Event Types ────────────────────────────────────────────────────────────

/** Events emitted by the ConnectionManager */
export interface ConnectionManagerEvents {
  /** Fired when the connection state changes */
  stateChange: (state: ConnectionState) => void;
  /** Fired when a valid server message is received */
  message: (message: ServerMessage) => void;
  /** Fired when controls should be enabled (on connection/reconnection) */
  controlsEnabled: () => void;
  /** Fired when controls should be disabled (on connection loss) */
  controlsDisabled: () => void;
}

export type ConnectionEventName = keyof ConnectionManagerEvents;

// ─── WebSocket Factory (for testability) ────────────────────────────────────

/**
 * Minimal WebSocket interface used by ConnectionManager.
 * This allows injecting a mock WebSocket for unit tests.
 */
export interface IWebSocket {
  readyState: number;
  onopen: ((ev: Event) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

export type WebSocketFactory = (url: string) => IWebSocket;

// WebSocket readyState constants
const WS_OPEN = 1;

// ─── Configuration ──────────────────────────────────────────────────────────

export interface ConnectionManagerConfig {
  /** WebSocket URL to connect to */
  url: string;
  /** Timeout in ms before considering connection lost (default: 3000) */
  messageTimeoutMs?: number;
  /** Interval in ms between reconnection attempts (default: 2000) */
  reconnectIntervalMs?: number;
  /** Maximum reconnection attempts before giving up (default: 10) */
  maxReconnectAttempts?: number;
  /** Optional WebSocket factory for testing */
  webSocketFactory?: WebSocketFactory;
}

// ─── ConnectionManager ──────────────────────────────────────────────────────

export class ConnectionManager {
  private readonly url: string;
  private readonly messageTimeoutMs: number;
  private readonly reconnectIntervalMs: number;
  private readonly maxReconnectAttempts: number;
  private readonly wsFactory: WebSocketFactory;

  private state: ConnectionState = 'disconnected';
  private ws: IWebSocket | null = null;
  private messageTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;

  // Event listener storage
  private listeners: {
    [K in ConnectionEventName]: Array<ConnectionManagerEvents[K]>;
  } = {
    stateChange: [],
    message: [],
    controlsEnabled: [],
    controlsDisabled: [],
  };

  constructor(config: ConnectionManagerConfig) {
    this.url = config.url;
    this.messageTimeoutMs = config.messageTimeoutMs ?? 3000;
    this.reconnectIntervalMs = config.reconnectIntervalMs ?? 2000;
    this.maxReconnectAttempts = config.maxReconnectAttempts ?? 10;
    this.wsFactory =
      config.webSocketFactory ?? ((url: string) => new WebSocket(url) as unknown as IWebSocket);
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /** Start the WebSocket connection */
  connect(): void {
    if (this.state === 'connecting' || this.state === 'connected') {
      return; // Already connecting or connected
    }
    this.reconnectAttempts = 0;
    this.transitionTo('connecting');
    this.createConnection();
  }

  /** Gracefully disconnect and stop all reconnection attempts */
  disconnect(): void {
    this.clearTimers();
    if (this.ws) {
      // Remove handlers before closing to prevent triggering reconnect logic
      this.ws.onopen = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }
    this.transitionTo('disconnected');
  }

  /** Send a client message over the WebSocket */
  send(message: ClientMessage): boolean {
    if (this.state !== 'connected' || !this.ws || this.ws.readyState !== WS_OPEN) {
      return false;
    }
    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch {
      return false;
    }
  }

  /** Get the current connection state */
  getState(): ConnectionState {
    return this.state;
  }

  // ─── Event Emitter ──────────────────────────────────────────────────────

  /** Subscribe to an event */
  on<K extends ConnectionEventName>(event: K, listener: ConnectionManagerEvents[K]): void {
    this.listeners[event].push(listener);
  }

  /** Unsubscribe from an event */
  off<K extends ConnectionEventName>(event: K, listener: ConnectionManagerEvents[K]): void {
    const list = this.listeners[event];
    const index = list.indexOf(listener);
    if (index !== -1) {
      list.splice(index, 1);
    }
  }

  /** Remove all listeners for an event, or all events if no event specified */
  removeAllListeners(event?: ConnectionEventName): void {
    if (event) {
      this.listeners[event] = [];
    } else {
      this.listeners = {
        stateChange: [],
        message: [],
        controlsEnabled: [],
        controlsDisabled: [],
      };
    }
  }

  // ─── Private Methods ────────────────────────────────────────────────────

  private emit<K extends ConnectionEventName>(
    event: K,
    ...args: Parameters<ConnectionManagerEvents[K]>
  ): void {
    const list = this.listeners[event] as Array<(...a: unknown[]) => void>;
    for (const listener of list) {
      listener(...args);
    }
  }

  private transitionTo(newState: ConnectionState): void {
    const previousState = this.state;
    if (previousState === newState) return;

    this.state = newState;
    this.emit('stateChange', newState);

    // Emit controls enabled/disabled events based on state transitions
    if (newState === 'connected') {
      this.emit('controlsEnabled');
    } else if (
      newState === 'reconnecting' ||
      newState === 'disconnected'
    ) {
      // Only emit controlsDisabled when transitioning FROM connected
      if (previousState === 'connected' || previousState === 'connecting') {
        this.emit('controlsDisabled');
      }
    }
  }

  private createConnection(): void {
    try {
      this.ws = this.wsFactory(this.url);
    } catch {
      this.handleConnectionFailure();
      return;
    }

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
  }

  private handleOpen(): void {
    // Connection is open but we wait for first message before transitioning to 'connected'
    // Start the message timeout - if no message arrives within the timeout, treat as failure
    this.resetMessageTimeout();
  }

  private handleClose(): void {
    this.ws = null;
    this.clearMessageTimeout();

    if (this.state === 'connected') {
      // Was connected, now lost — begin reconnection
      this.transitionTo('reconnecting');
      this.scheduleReconnect();
    } else if (this.state === 'connecting') {
      // Failed during initial connection
      this.handleConnectionFailure();
    } else if (this.state === 'reconnecting') {
      // A reconnection attempt failed
      this.scheduleReconnect();
    }
  }

  private handleError(): void {
    // The 'close' event will follow; error just means something went wrong.
    // We don't need to do much here — onclose handles state transitions.
  }

  private handleMessage(ev: MessageEvent): void {
    // Reset the message timeout on every message received
    this.resetMessageTimeout();

    // If we're in 'connecting' or 'reconnecting' state and receive a message,
    // transition to 'connected' (the first message confirms the connection is live)
    if (this.state === 'connecting' || this.state === 'reconnecting') {
      this.reconnectAttempts = 0;
      this.transitionTo('connected');
    }

    // Parse and emit the message
    try {
      const data: ServerMessage = JSON.parse(ev.data as string);
      this.emit('message', data);
    } catch {
      // Silently ignore messages that can't be parsed as valid ServerMessage JSON
    }
  }

  private handleConnectionFailure(): void {
    if (this.state === 'connecting') {
      // If this was the initial connect, go to reconnecting
      this.transitionTo('reconnecting');
      this.scheduleReconnect();
    }
  }

  private resetMessageTimeout(): void {
    this.clearMessageTimeout();
    this.messageTimeoutTimer = setTimeout(() => {
      this.onMessageTimeout();
    }, this.messageTimeoutMs);
  }

  private onMessageTimeout(): void {
    // No message received for messageTimeoutMs
    if (this.state === 'connected') {
      // Close the current socket to trigger reconnection
      if (this.ws) {
        this.ws.onopen = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.onmessage = null;
        this.ws.close();
        this.ws = null;
      }
      this.transitionTo('reconnecting');
      this.scheduleReconnect();
    } else if (this.state === 'connecting') {
      // Timed out waiting for first message on initial connect
      if (this.ws) {
        this.ws.onopen = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.onmessage = null;
        this.ws.close();
        this.ws = null;
      }
      this.transitionTo('reconnecting');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.transitionTo('disconnected');
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.createConnection();
    }, this.reconnectIntervalMs);
  }

  private clearTimers(): void {
    this.clearMessageTimeout();
    this.clearReconnectTimer();
  }

  private clearMessageTimeout(): void {
    if (this.messageTimeoutTimer !== null) {
      clearTimeout(this.messageTimeoutTimer);
      this.messageTimeoutTimer = null;
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
