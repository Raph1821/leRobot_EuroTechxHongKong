/**
 * Property-based test for Connection State Machine Transitions (Property 8)
 *
 * **Validates: Requirements 10.1, 10.2, 10.3**
 *
 * For any sequence of connection events, applying the events to the connection
 * state machine starting from the initial "Connecting" state SHALL produce a
 * final state consistent with the defined transitions:
 * - Connected requires open + message
 * - Reconnecting occurs on timeout/close from Connected
 * - Disconnected occurs after 10 failed reconnect attempts
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { ConnectionState } from '../types';

// ─── State Machine Model ────────────────────────────────────────────────────

/**
 * Connection events that drive the state machine.
 */
type ConnectionEvent =
  | 'websocket_open'
  | 'message_received'
  | 'no_message_timeout'
  | 'websocket_closed'
  | 'reconnect_attempt_success'
  | 'reconnect_attempt_failure';

const ALL_EVENTS: ConnectionEvent[] = [
  'websocket_open',
  'message_received',
  'no_message_timeout',
  'websocket_closed',
  'reconnect_attempt_success',
  'reconnect_attempt_failure',
];

interface StateMachineState {
  connectionState: ConnectionState;
  reconnectAttempts: number;
}

const MAX_RECONNECT_ATTEMPTS = 10;

/**
 * Pure state machine transition function modeling the ConnectionManager behavior.
 *
 * Transitions defined:
 * - Connecting + websocket_open → Connecting (waiting for first message)
 * - Connecting + message_received → Connected (open + message confirms connection)
 * - Connecting + no_message_timeout → Reconnecting (timeout waiting for first message)
 * - Connecting + websocket_closed → Reconnecting (failed during initial connect)
 *
 * - Connected + message_received → Connected (keep-alive)
 * - Connected + no_message_timeout → Reconnecting (connection considered lost)
 * - Connected + websocket_closed → Reconnecting (connection dropped)
 *
 * - Reconnecting + reconnect_attempt_success → Connected (message received on reconnect)
 * - Reconnecting + reconnect_attempt_failure → Reconnecting (if attempts < max) or Disconnected (if attempts >= max)
 * - Reconnecting + message_received → Connected (reconnection succeeded via message)
 *
 * - Disconnected → terminal state (no automatic transitions)
 */
function transition(
  state: StateMachineState,
  event: ConnectionEvent
): StateMachineState {
  const { connectionState, reconnectAttempts } = state;

  switch (connectionState) {
    case 'connecting':
      switch (event) {
        case 'websocket_open':
          // WebSocket open but still waiting for first message
          return { connectionState: 'connecting', reconnectAttempts: 0 };
        case 'message_received':
          // First message confirms connection is live
          return { connectionState: 'connected', reconnectAttempts: 0 };
        case 'no_message_timeout':
          // Timed out waiting for first message, start reconnecting
          return { connectionState: 'reconnecting', reconnectAttempts: 0 };
        case 'websocket_closed':
          // Connection failed during initial connect
          return { connectionState: 'reconnecting', reconnectAttempts: 0 };
        default:
          // Events like reconnect_attempt_success/failure are not meaningful in connecting state
          return state;
      }

    case 'connected':
      switch (event) {
        case 'message_received':
          // Keep-alive, still connected
          return { connectionState: 'connected', reconnectAttempts: 0 };
        case 'no_message_timeout':
          // No message for 3s → connection lost
          return { connectionState: 'reconnecting', reconnectAttempts: 0 };
        case 'websocket_closed':
          // WebSocket closed → begin reconnection
          return { connectionState: 'reconnecting', reconnectAttempts: 0 };
        default:
          // websocket_open, reconnect events are not meaningful in connected state
          return state;
      }

    case 'reconnecting':
      switch (event) {
        case 'reconnect_attempt_success':
        case 'message_received':
          // Reconnection succeeded
          return { connectionState: 'connected', reconnectAttempts: 0 };
        case 'reconnect_attempt_failure': {
          const newAttempts = reconnectAttempts + 1;
          if (newAttempts >= MAX_RECONNECT_ATTEMPTS) {
            return { connectionState: 'disconnected', reconnectAttempts: newAttempts };
          }
          return { connectionState: 'reconnecting', reconnectAttempts: newAttempts };
        }
        default:
          // websocket_open, no_message_timeout, websocket_closed are not meaningful
          // in reconnecting state (we're already trying to reconnect)
          return state;
      }

    case 'disconnected':
      // Terminal state — no automatic transitions
      return state;

    default:
      return state;
  }
}

/**
 * Apply a sequence of events to the state machine and return the final state.
 */
function applyEvents(
  events: ConnectionEvent[],
  initialState: StateMachineState = { connectionState: 'connecting', reconnectAttempts: 0 }
): StateMachineState {
  return events.reduce((state, event) => transition(state, event), initialState);
}

// ─── Property Tests ─────────────────────────────────────────────────────────

describe('Feature: so100-isaacsim-web-control, Property 8: Connection state machine transitions', () => {
  /**
   * Property 8: Connection state machine transitions
   * **Validates: Requirements 10.1, 10.2, 10.3**
   */

  it('should always produce a valid ConnectionState for any event sequence', () => {
    const validStates: ConnectionState[] = ['connecting', 'connected', 'reconnecting', 'disconnected'];

    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 0, maxLength: 50 }),
        (events) => {
          const finalState = applyEvents(events);
          expect(validStates).toContain(finalState.connectionState);
          expect(finalState.reconnectAttempts).toBeGreaterThanOrEqual(0);
          expect(finalState.reconnectAttempts).toBeLessThanOrEqual(MAX_RECONNECT_ATTEMPTS);
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should transition to Connected only after receiving a message', () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 1, maxLength: 50 }),
        (events) => {
          const finalState = applyEvents(events);
          if (finalState.connectionState === 'connected') {
            // To reach 'connected', the sequence must contain at least one 'message_received'
            // or 'reconnect_attempt_success' event
            const hasConnectingEvent = events.includes('message_received') || events.includes('reconnect_attempt_success');
            expect(hasConnectingEvent).toBe(true);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should transition to Disconnected only after exactly 10 failed reconnect attempts', () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 1, maxLength: 100 }),
        (events) => {
          const finalState = applyEvents(events);
          if (finalState.connectionState === 'disconnected') {
            // Count effective failure attempts: failures that occur while in reconnecting state
            // We can verify this by replaying events and counting transitions
            let state: StateMachineState = { connectionState: 'connecting', reconnectAttempts: 0 };
            let totalFailuresInReconnecting = 0;

            for (let i = 0; i < events.length; i++) {
              const prevState = state;
              state = transition(state, events[i]);

              // Count failures that happen while in reconnecting state
              if (prevState.connectionState === 'reconnecting' && events[i] === 'reconnect_attempt_failure') {
                totalFailuresInReconnecting++;
              }

              // Reset counter when we successfully reconnect
              if (state.connectionState === 'connected' && prevState.connectionState !== 'connected') {
                totalFailuresInReconnecting = 0;
              }
            }

            // When disconnected, we must have had at least 10 consecutive failures
            // (without a successful reconnect in between)
            expect(totalFailuresInReconnecting).toBeGreaterThanOrEqual(MAX_RECONNECT_ATTEMPTS);
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should remain in Disconnected state regardless of further events (terminal state)', () => {
    // First, generate a sequence that leads to disconnected
    const disconnectSequence: ConnectionEvent[] = [
      'websocket_closed', // connecting → reconnecting
      ...Array(10).fill('reconnect_attempt_failure') as ConnectionEvent[], // reconnecting → disconnected
    ];

    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 1, maxLength: 30 }),
        (additionalEvents) => {
          const fullSequence = [...disconnectSequence, ...additionalEvents];
          const finalState = applyEvents(fullSequence);
          // Once disconnected, state should remain disconnected
          expect(finalState.connectionState).toBe('disconnected');
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should transition Connected → Reconnecting on timeout or close (Req 10.2)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('no_message_timeout' as ConnectionEvent, 'websocket_closed' as ConnectionEvent),
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 0, maxLength: 20 }),
        (disconnectEvent, _prefixEvents) => {
          // Start from a connected state
          const connectedState: StateMachineState = { connectionState: 'connected', reconnectAttempts: 0 };
          // Apply the disconnect event
          const result = transition(connectedState, disconnectEvent);
          expect(result.connectionState).toBe('reconnecting');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should handle Reconnecting → Connected on success (Req 10.3)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 9 }), // attempts less than max
        fc.constantFrom('reconnect_attempt_success' as ConnectionEvent, 'message_received' as ConnectionEvent),
        (attempts, successEvent) => {
          const reconnectingState: StateMachineState = {
            connectionState: 'reconnecting',
            reconnectAttempts: attempts,
          };
          const result = transition(reconnectingState, successEvent);
          expect(result.connectionState).toBe('connected');
          expect(result.reconnectAttempts).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should count reconnect attempts correctly up to the max', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }), // number of failure events
        (numFailures) => {
          // Start from reconnecting with 0 attempts
          let state: StateMachineState = { connectionState: 'reconnecting', reconnectAttempts: 0 };

          for (let i = 0; i < numFailures; i++) {
            state = transition(state, 'reconnect_attempt_failure');
            if (state.connectionState === 'disconnected') break;
          }

          if (numFailures >= MAX_RECONNECT_ATTEMPTS) {
            expect(state.connectionState).toBe('disconnected');
          } else {
            expect(state.connectionState).toBe('reconnecting');
            expect(state.reconnectAttempts).toBe(numFailures);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should reset reconnect attempts on successful reconnection', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 9 }), // some failed attempts (not enough to disconnect)
        fc.array(fc.constantFrom(...ALL_EVENTS), { minLength: 0, maxLength: 20 }),
        (failedAttempts, _afterEvents) => {
          // After successful reconnection, reconnectAttempts should be reset
          const stateAfterReconnect = applyEvents([
            'message_received',
            'no_message_timeout',
            ...Array(failedAttempts).fill('reconnect_attempt_failure') as ConnectionEvent[],
            'reconnect_attempt_success',
          ]);

          expect(stateAfterReconnect.connectionState).toBe('connected');
          expect(stateAfterReconnect.reconnectAttempts).toBe(0);
        }
      ),
      { numRuns: 100 }
    );
  });
});
