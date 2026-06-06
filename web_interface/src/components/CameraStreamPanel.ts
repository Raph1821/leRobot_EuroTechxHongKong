/**
 * CameraStreamPanel — displays a live camera feed from the Isaac Sim viewport.
 *
 * Features:
 * - Displays JPEG stream by decoding base64 data and rendering to an <img> element
 * - Renders frames within 100ms of receipt
 * - Resizable panel with minimum size 320×240, positioned alongside the 3D viewer
 * - Shows placeholder when streaming is disabled
 * - Shows overlay "Camera feed unavailable" when notified by bridge
 * - Shows overlay "Connection lost" within 3s of WebSocket disconnection
 * - Provides toggle button (default: disabled) to enable/disable streaming
 *
 * Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  ConnectionState,
  ServerMessage,
  CameraFrameMessage,
  CameraStreamControlMessage,
} from '../types';

// ─── Types ──────────────────────────────────────────────────────────────────

/** Overlay state for the camera panel */
export type CameraOverlayState = 'none' | 'unavailable' | 'connection_lost';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Minimum panel width in pixels */
const MIN_WIDTH = 320;

/** Minimum panel height in pixels */
const MIN_HEIGHT = 240;

/** Time in ms after WebSocket disconnection before showing connection lost overlay */
const CONNECTION_LOST_DELAY_MS = 3000;

// ─── CameraStreamPanel ──────────────────────────────────────────────────────

export class CameraStreamPanel {
  private readonly connectionManager: ConnectionManager;

  // State
  private streamingEnabled = false;
  private overlayState: CameraOverlayState = 'none';

  // DOM elements (created on mount)
  private container: HTMLElement | null = null;
  private panelElement: HTMLElement | null = null;
  private imageElement: HTMLImageElement | null = null;
  private placeholderElement: HTMLElement | null = null;
  private overlayElement: HTMLElement | null = null;
  private toggleButton: HTMLButtonElement | null = null;

  // Timers
  private connectionLostTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;

    // Listen for connection state changes and messages
    this.connectionManager.on('stateChange', this.handleStateChange);
    this.connectionManager.on('message', this.handleMessage);
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the camera stream panel into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.render();
    this.updateDisplay();
  }

  /**
   * Remove the camera stream panel from the DOM and clean up resources.
   */
  unmount(): void {
    this.connectionManager.off('stateChange', this.handleStateChange);
    this.connectionManager.off('message', this.handleMessage);

    this.clearConnectionLostTimer();

    if (this.container) {
      this.container.innerHTML = '';
    }

    this.container = null;
    this.panelElement = null;
    this.imageElement = null;
    this.placeholderElement = null;
    this.overlayElement = null;
    this.toggleButton = null;
  }

  /**
   * Check if streaming is currently enabled.
   */
  isStreamingEnabled(): boolean {
    return this.streamingEnabled;
  }

  /**
   * Get the current overlay state.
   */
  getOverlayState(): CameraOverlayState {
    return this.overlayState;
  }

  /**
   * Handle an incoming server message. Can be called externally for message routing.
   */
  handleServerMessage(message: ServerMessage): void {
    if (message.type === 'camera_frame') {
      this.handleCameraFrame(message as CameraFrameMessage);
    }
  }

  /**
   * Notify the panel that the camera feed is unavailable (called by bridge notification).
   */
  setCameraUnavailable(): void {
    this.overlayState = 'unavailable';
    this.updateOverlay();
  }

  /**
   * Notify the panel that the camera feed has resumed.
   */
  setCameraAvailable(): void {
    if (this.overlayState === 'unavailable') {
      this.overlayState = 'none';
      this.updateOverlay();
    }
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private render(): void {
    if (!this.container) return;

    // Panel wrapper (resizable)
    this.panelElement = document.createElement('div');
    this.panelElement.className = 'camera-stream-panel';
    this.panelElement.style.minWidth = `${MIN_WIDTH}px`;
    this.panelElement.style.minHeight = `${MIN_HEIGHT}px`;
    this.panelElement.style.resize = 'both';
    this.panelElement.style.overflow = 'hidden';
    this.panelElement.style.position = 'relative';
    this.panelElement.setAttribute('role', 'region');
    this.panelElement.setAttribute('aria-label', 'Camera stream');

    // Header with toggle button
    const header = document.createElement('div');
    header.className = 'camera-stream-panel__header';

    const title = document.createElement('span');
    title.className = 'camera-stream-panel__title';
    title.textContent = 'Camera Feed';
    header.appendChild(title);

    this.toggleButton = document.createElement('button');
    this.toggleButton.className = 'camera-stream-panel__toggle';
    this.toggleButton.setAttribute('aria-label', 'Toggle camera streaming');
    this.toggleButton.addEventListener('click', this.handleToggleClick);
    this.updateToggleButton();
    header.appendChild(this.toggleButton);

    this.panelElement.appendChild(header);

    // Content area
    const contentArea = document.createElement('div');
    contentArea.className = 'camera-stream-panel__content';
    contentArea.style.position = 'relative';
    contentArea.style.width = '100%';
    contentArea.style.height = 'calc(100% - 40px)';

    // Image element for camera frames
    this.imageElement = document.createElement('img');
    this.imageElement.className = 'camera-stream-panel__image';
    this.imageElement.style.width = '100%';
    this.imageElement.style.height = '100%';
    this.imageElement.style.objectFit = 'contain';
    this.imageElement.style.display = 'none';
    this.imageElement.alt = 'Camera feed';
    contentArea.appendChild(this.imageElement);

    // Placeholder (visible when streaming disabled)
    this.placeholderElement = document.createElement('div');
    this.placeholderElement.className = 'camera-stream-panel__placeholder';
    this.placeholderElement.textContent = 'Streaming paused';
    this.placeholderElement.style.display = 'flex';
    this.placeholderElement.style.alignItems = 'center';
    this.placeholderElement.style.justifyContent = 'center';
    this.placeholderElement.style.width = '100%';
    this.placeholderElement.style.height = '100%';
    contentArea.appendChild(this.placeholderElement);

    // Overlay element for status messages
    this.overlayElement = document.createElement('div');
    this.overlayElement.className = 'camera-stream-panel__overlay';
    this.overlayElement.style.position = 'absolute';
    this.overlayElement.style.top = '0';
    this.overlayElement.style.left = '0';
    this.overlayElement.style.width = '100%';
    this.overlayElement.style.height = '100%';
    this.overlayElement.style.display = 'none';
    this.overlayElement.style.alignItems = 'center';
    this.overlayElement.style.justifyContent = 'center';
    this.overlayElement.setAttribute('role', 'alert');
    this.overlayElement.setAttribute('aria-live', 'assertive');
    contentArea.appendChild(this.overlayElement);

    this.panelElement.appendChild(contentArea);
    this.container.appendChild(this.panelElement);
  }

  private updateDisplay(): void {
    this.updateToggleButton();
    this.updateImageVisibility();
    this.updateOverlay();
  }

  private updateToggleButton(): void {
    if (!this.toggleButton) return;
    this.toggleButton.textContent = this.streamingEnabled ? 'Disable' : 'Enable';
    this.toggleButton.setAttribute(
      'aria-pressed',
      String(this.streamingEnabled)
    );
  }

  private updateImageVisibility(): void {
    if (!this.imageElement || !this.placeholderElement) return;

    if (this.streamingEnabled) {
      this.imageElement.style.display = 'block';
      this.placeholderElement.style.display = 'none';
    } else {
      this.imageElement.style.display = 'none';
      this.placeholderElement.style.display = 'flex';
    }
  }

  private updateOverlay(): void {
    if (!this.overlayElement) return;

    switch (this.overlayState) {
      case 'unavailable':
        this.overlayElement.textContent = 'Camera feed unavailable';
        this.overlayElement.style.display = 'flex';
        break;
      case 'connection_lost':
        this.overlayElement.textContent = 'Connection lost';
        this.overlayElement.style.display = 'flex';
        break;
      case 'none':
      default:
        this.overlayElement.textContent = '';
        this.overlayElement.style.display = 'none';
        break;
    }
  }

  // ─── Private: Event Handlers ────────────────────────────────────────────

  private handleStateChange = (state: ConnectionState): void => {
    if (state === 'disconnected' || state === 'reconnecting') {
      // Start the connection lost timer if streaming was enabled
      if (this.streamingEnabled && this.overlayState !== 'connection_lost') {
        this.startConnectionLostTimer();
      }
    } else if (state === 'connected') {
      // Clear any pending connection lost timer and overlay
      this.clearConnectionLostTimer();
      if (this.overlayState === 'connection_lost') {
        this.overlayState = 'none';
        this.updateOverlay();
      }
    }
  };

  private handleMessage = (message: ServerMessage): void => {
    this.handleServerMessage(message);
  };

  private handleCameraFrame(message: CameraFrameMessage): void {
    if (!this.streamingEnabled || !this.imageElement) return;

    // Clear any "unavailable" overlay since we're receiving frames
    if (this.overlayState === 'unavailable') {
      this.overlayState = 'none';
      this.updateOverlay();
    }

    // Decode base64 JPEG and render to img element (within 100ms target)
    const dataUrl = `data:image/jpeg;base64,${message.data}`;
    this.imageElement.src = dataUrl;
  }

  private handleToggleClick = (): void => {
    this.streamingEnabled = !this.streamingEnabled;
    this.updateDisplay();

    // Send control message to bridge
    const controlMessage: CameraStreamControlMessage = {
      type: 'camera_stream_control',
      enabled: this.streamingEnabled,
    };
    this.connectionManager.send(controlMessage);

    // If disabling, reset overlay state
    if (!this.streamingEnabled) {
      this.overlayState = 'none';
      this.updateOverlay();
      this.clearConnectionLostTimer();
    }
  };

  // ─── Private: Timers ────────────────────────────────────────────────────

  private startConnectionLostTimer(): void {
    this.clearConnectionLostTimer();
    this.connectionLostTimer = setTimeout(() => {
      this.overlayState = 'connection_lost';
      this.updateOverlay();
    }, CONNECTION_LOST_DELAY_MS);
  }

  private clearConnectionLostTimer(): void {
    if (this.connectionLostTimer !== null) {
      clearTimeout(this.connectionLostTimer);
      this.connectionLostTimer = null;
    }
  }
}
