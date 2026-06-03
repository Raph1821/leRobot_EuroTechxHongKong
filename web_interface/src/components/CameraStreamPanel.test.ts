/**
 * Unit tests for CameraStreamPanel component.
 *
 * Tests cover:
 * - Toggle defaults to disabled (Req 1.5)
 * - Panel shows placeholder when streaming disabled (Req 1.6)
 * - Overlay appears for camera unavailable notification (Req 1.7)
 * - Overlay appears within 3s of WebSocket loss (Req 1.8)
 * - Panel minimum size enforced at 320×240 (Req 1.4)
 * - Frame rendering (Req 1.3)
 * - Mount and unmount lifecycle
 *
 * Validates: Requirements 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
 *
 * @vitest-environment happy-dom
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { CameraStreamPanel } from './CameraStreamPanel';
import type { ConnectionManager } from '../services/ConnectionManager';
import type { ConnectionState, ServerMessage, CameraFrameMessage } from '../types';

// ─── Mock ConnectionManager ─────────────────────────────────────────────────

function createMockConnectionManager(initialState: ConnectionState = 'connected') {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {
    stateChange: [],
    message: [],
    controlsEnabled: [],
    controlsDisabled: [],
  };

  const mock = {
    getState: vi.fn(() => initialState),
    on: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      listeners[event]?.push(listener);
    }),
    off: vi.fn((event: string, listener: (...args: unknown[]) => void) => {
      const list = listeners[event];
      if (list) {
        const idx = list.indexOf(listener);
        if (idx !== -1) list.splice(idx, 1);
      }
    }),
    send: vi.fn(() => true),
    connect: vi.fn(),
    disconnect: vi.fn(),
    removeAllListeners: vi.fn(),
    _emit(event: string, ...args: unknown[]) {
      for (const listener of listeners[event] ?? []) {
        listener(...args);
      }
    },
  };

  return mock as unknown as ConnectionManager & { _emit: (event: string, ...args: unknown[]) => void };
}

function createCameraFrame(data = 'dGVzdA=='): CameraFrameMessage {
  return {
    type: 'camera_frame',
    timestamp: Date.now(),
    width: 640,
    height: 480,
    encoding: 'jpeg',
    quality: 75,
    data,
  };
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('CameraStreamPanel', () => {
  let container: HTMLElement;
  let connectionManager: ReturnType<typeof createMockConnectionManager>;
  let panel: CameraStreamPanel;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement('div');
    connectionManager = createMockConnectionManager('connected');
    panel = new CameraStreamPanel(connectionManager);
    panel.mount(container);
  });

  afterEach(() => {
    panel.unmount();
    vi.useRealTimers();
  });

  describe('toggle defaults to disabled (Req 1.5)', () => {
    it('streaming is disabled by default', () => {
      expect(panel.isStreamingEnabled()).toBe(false);
    });

    it('toggle button shows "Enable" when streaming disabled', () => {
      const button = container.querySelector('.camera-stream-panel__toggle');
      expect(button?.textContent).toBe('Enable');
    });

    it('toggle button shows "Disable" after enabling', () => {
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      expect(panel.isStreamingEnabled()).toBe(true);
      expect(button.textContent).toBe('Disable');
    });

    it('sends camera_stream_control message when toggled on', () => {
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      expect(connectionManager.send).toHaveBeenCalledWith({
        type: 'camera_stream_control',
        enabled: true,
      });
    });

    it('sends camera_stream_control message when toggled off', () => {
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click(); // enable
      button.click(); // disable

      expect(connectionManager.send).toHaveBeenLastCalledWith({
        type: 'camera_stream_control',
        enabled: false,
      });
    });
  });

  describe('placeholder when streaming disabled (Req 1.6)', () => {
    it('shows placeholder when streaming is disabled', () => {
      const placeholder = container.querySelector('.camera-stream-panel__placeholder') as HTMLElement;
      expect(placeholder.style.display).toBe('flex');
      expect(placeholder.textContent).toBe('Streaming paused');
    });

    it('hides image element when streaming is disabled', () => {
      const img = container.querySelector('.camera-stream-panel__image') as HTMLElement;
      expect(img.style.display).toBe('none');
    });

    it('hides placeholder and shows image when streaming enabled', () => {
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      const placeholder = container.querySelector('.camera-stream-panel__placeholder') as HTMLElement;
      const img = container.querySelector('.camera-stream-panel__image') as HTMLElement;
      expect(placeholder.style.display).toBe('none');
      expect(img.style.display).toBe('block');
    });
  });

  describe('camera unavailable overlay (Req 1.7)', () => {
    it('shows "Camera feed unavailable" overlay when notified', () => {
      panel.setCameraUnavailable();

      expect(panel.getOverlayState()).toBe('unavailable');
      const overlay = container.querySelector('.camera-stream-panel__overlay') as HTMLElement;
      expect(overlay.style.display).toBe('flex');
      expect(overlay.textContent).toBe('Camera feed unavailable');
    });

    it('clears unavailable overlay when frames resume', () => {
      panel.setCameraUnavailable();
      panel.setCameraAvailable();

      expect(panel.getOverlayState()).toBe('none');
      const overlay = container.querySelector('.camera-stream-panel__overlay') as HTMLElement;
      expect(overlay.style.display).toBe('none');
    });

    it('clears unavailable overlay when a camera frame is received while streaming', () => {
      // Enable streaming first
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      panel.setCameraUnavailable();
      expect(panel.getOverlayState()).toBe('unavailable');

      // Receive a frame
      const frame = createCameraFrame();
      connectionManager._emit('message', frame);

      expect(panel.getOverlayState()).toBe('none');
    });
  });

  describe('connection lost overlay (Req 1.8)', () => {
    it('shows "Connection lost" overlay within 3s of WebSocket disconnection', () => {
      // Enable streaming
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      // Simulate disconnection
      connectionManager._emit('stateChange', 'disconnected');

      // Before 3s, no overlay
      vi.advanceTimersByTime(2999);
      expect(panel.getOverlayState()).not.toBe('connection_lost');

      // At 3s, overlay appears
      vi.advanceTimersByTime(1);
      expect(panel.getOverlayState()).toBe('connection_lost');
      const overlay = container.querySelector('.camera-stream-panel__overlay') as HTMLElement;
      expect(overlay.textContent).toBe('Connection lost');
    });

    it('does not show connection lost overlay if streaming is disabled', () => {
      // Streaming is disabled by default
      connectionManager._emit('stateChange', 'disconnected');

      vi.advanceTimersByTime(5000);
      expect(panel.getOverlayState()).not.toBe('connection_lost');
    });

    it('clears connection lost overlay when connection is restored', () => {
      // Enable streaming
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      // Disconnect
      connectionManager._emit('stateChange', 'disconnected');
      vi.advanceTimersByTime(3000);
      expect(panel.getOverlayState()).toBe('connection_lost');

      // Reconnect
      connectionManager._emit('stateChange', 'connected');
      expect(panel.getOverlayState()).toBe('none');
    });

    it('cancels connection lost timer if reconnected before 3s', () => {
      // Enable streaming
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      // Disconnect
      connectionManager._emit('stateChange', 'disconnected');
      vi.advanceTimersByTime(2000);

      // Reconnect before timer fires
      connectionManager._emit('stateChange', 'connected');
      vi.advanceTimersByTime(5000);

      expect(panel.getOverlayState()).toBe('none');
    });
  });

  describe('minimum panel size (Req 1.4)', () => {
    it('sets minimum width to 320px', () => {
      const panelEl = container.querySelector('.camera-stream-panel') as HTMLElement;
      expect(panelEl.style.minWidth).toBe('320px');
    });

    it('sets minimum height to 240px', () => {
      const panelEl = container.querySelector('.camera-stream-panel') as HTMLElement;
      expect(panelEl.style.minHeight).toBe('240px');
    });

    it('panel is resizable', () => {
      const panelEl = container.querySelector('.camera-stream-panel') as HTMLElement;
      expect(panelEl.style.resize).toBe('both');
    });
  });

  describe('frame rendering (Req 1.3)', () => {
    it('renders frame data to image element when streaming enabled', () => {
      // Enable streaming
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      const frame = createCameraFrame('aW1hZ2VkYXRh');
      connectionManager._emit('message', frame);

      const img = container.querySelector('.camera-stream-panel__image') as HTMLImageElement;
      expect(img.src).toBe('data:image/jpeg;base64,aW1hZ2VkYXRh');
    });

    it('does not render frame when streaming is disabled', () => {
      const frame = createCameraFrame('aW1hZ2VkYXRh');
      connectionManager._emit('message', frame);

      const img = container.querySelector('.camera-stream-panel__image') as HTMLImageElement;
      expect(img.src).toBe('');
    });

    it('ignores non-camera messages', () => {
      // Enable streaming
      const button = container.querySelector('.camera-stream-panel__toggle') as HTMLButtonElement;
      button.click();

      const message: ServerMessage = {
        type: 'joint_state',
        timestamp: 123,
        joints: { names: [], positions: [], velocities: [], efforts: [] },
      };
      connectionManager._emit('message', message);

      const img = container.querySelector('.camera-stream-panel__image') as HTMLImageElement;
      expect(img.src).toBe('');
    });
  });

  describe('mount and unmount', () => {
    it('creates panel structure on mount', () => {
      expect(container.querySelector('.camera-stream-panel')).not.toBeNull();
      expect(container.querySelector('.camera-stream-panel__header')).not.toBeNull();
      expect(container.querySelector('.camera-stream-panel__toggle')).not.toBeNull();
      expect(container.querySelector('.camera-stream-panel__image')).not.toBeNull();
      expect(container.querySelector('.camera-stream-panel__placeholder')).not.toBeNull();
      expect(container.querySelector('.camera-stream-panel__overlay')).not.toBeNull();
    });

    it('cleans up DOM on unmount', () => {
      panel.unmount();
      expect(container.innerHTML).toBe('');
    });

    it('unsubscribes from connection manager on unmount', () => {
      panel.unmount();
      expect(connectionManager.off).toHaveBeenCalled();
    });

    it('stops responding to events after unmount', () => {
      panel.unmount();

      // These should not throw
      connectionManager._emit('stateChange', 'disconnected');
      connectionManager._emit('message', createCameraFrame());
    });
  });

  describe('accessibility', () => {
    it('panel has region role and aria-label', () => {
      const panelEl = container.querySelector('.camera-stream-panel');
      expect(panelEl?.getAttribute('role')).toBe('region');
      expect(panelEl?.getAttribute('aria-label')).toBe('Camera stream');
    });

    it('toggle button has aria-label and aria-pressed', () => {
      const button = container.querySelector('.camera-stream-panel__toggle');
      expect(button?.getAttribute('aria-label')).toBe('Toggle camera streaming');
      expect(button?.getAttribute('aria-pressed')).toBe('false');
    });

    it('overlay has alert role and aria-live assertive', () => {
      const overlay = container.querySelector('.camera-stream-panel__overlay');
      expect(overlay?.getAttribute('role')).toBe('alert');
      expect(overlay?.getAttribute('aria-live')).toBe('assertive');
    });

    it('image has alt text', () => {
      const img = container.querySelector('.camera-stream-panel__image');
      expect(img?.getAttribute('alt')).toBe('Camera feed');
    });
  });
});
