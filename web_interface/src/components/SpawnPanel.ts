/**
 * SpawnPanel — interactive object spawning panel for the SO-100 web interface.
 *
 * Features:
 * - Dropdown for object type (box, sphere, cylinder)
 * - Dynamic dimension inputs that change based on selected type
 * - Numeric inputs for position (x, y, z) constrained to [-10.0, 10.0]
 * - Dimension inputs constrained to [0.01, 2.0], mass input constrained to [0.01, 50.0]
 * - Color picker for RGBA
 * - "Spawn" button that sends spawn request
 * - Object list showing spawned objects with ID, type, position
 * - "Delete" button per object in the list
 * - Display error notifications from spawn/delete operations
 *
 * Requirements: 2.3, 2.4, 2.5, 2.6, 2.7
 */

import type { ConnectionManager } from '../services/ConnectionManager';
import type {
  SpawnObjectMessage,
  SpawnConfirmMessage,
  DeleteObjectMessage,
  DeleteConfirmMessage,
  ErrorMessage,
} from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

/** Position coordinate bounds */
const POSITION_MIN = -10.0;
const POSITION_MAX = 10.0;

/** Dimension bounds */
const DIMENSION_MIN = 0.01;
const DIMENSION_MAX = 2.0;

/** Mass bounds */
const MASS_MIN = 0.01;
const MASS_MAX = 50.0;

/** Color channel bounds */
const COLOR_MIN = 0.0;
const COLOR_MAX = 1.0;

/** Default orientation (unused in UI but sent in message) */
const DEFAULT_ORIENTATION: [number, number, number] = [0, 0, 0];

/** Error notification display duration (ms) */
const ERROR_DISPLAY_MS = 5000;

// ─── Types ──────────────────────────────────────────────────────────────────

type ObjectType = 'box' | 'sphere' | 'cylinder';

interface SpawnedObject {
  object_id: string;
  object_type: ObjectType;
  position: [number, number, number];
}

interface DimensionField {
  label: string;
  key: string;
  defaultValue: number;
}

// ─── Dimension Configurations ───────────────────────────────────────────────

const DIMENSION_CONFIGS: Record<ObjectType, DimensionField[]> = {
  box: [
    { label: 'Length', key: 'length', defaultValue: 0.1 },
    { label: 'Width', key: 'width', defaultValue: 0.1 },
    { label: 'Height', key: 'height', defaultValue: 0.1 },
  ],
  sphere: [
    { label: 'Radius', key: 'radius', defaultValue: 0.05 },
  ],
  cylinder: [
    { label: 'Radius', key: 'radius', defaultValue: 0.05 },
    { label: 'Height', key: 'height', defaultValue: 0.1 },
  ],
};

// ─── Validation ─────────────────────────────────────────────────────────────

/**
 * Validate a spawn request's numeric fields.
 * Returns an error message if invalid, or null if valid.
 */
export function validateSpawnRequest(
  objectType: ObjectType,
  dimensions: number[],
  position: [number, number, number],
  color: [number, number, number, number],
  mass: number
): string | null {
  // Validate dimension array length
  const expectedLength = DIMENSION_CONFIGS[objectType].length;
  if (dimensions.length !== expectedLength) {
    return `Expected ${expectedLength} dimension(s) for ${objectType}, got ${dimensions.length}.`;
  }

  // Validate dimension values
  for (let i = 0; i < dimensions.length; i++) {
    const val = dimensions[i];
    if (val < DIMENSION_MIN || val > DIMENSION_MAX) {
      return `Dimension values must be between ${DIMENSION_MIN} and ${DIMENSION_MAX}.`;
    }
  }

  // Validate position
  for (let i = 0; i < 3; i++) {
    const val = position[i];
    if (val < POSITION_MIN || val > POSITION_MAX) {
      return `Position values must be between ${POSITION_MIN} and ${POSITION_MAX}.`;
    }
  }

  // Validate color
  for (let i = 0; i < 4; i++) {
    const val = color[i];
    if (val < COLOR_MIN || val > COLOR_MAX) {
      return `Color values must be between ${COLOR_MIN} and ${COLOR_MAX}.`;
    }
  }

  // Validate mass
  if (mass < MASS_MIN || mass > MASS_MAX) {
    return `Mass must be between ${MASS_MIN} and ${MASS_MAX}.`;
  }

  return null;
}

// ─── SpawnPanel ─────────────────────────────────────────────────────────────

export class SpawnPanel {
  private readonly connectionManager: ConnectionManager;
  private spawnedObjects: SpawnedObject[] = [];

  // DOM elements
  private container: HTMLElement | null = null;
  private typeSelect: HTMLSelectElement | null = null;
  private dimensionContainer: HTMLDivElement | null = null;
  private dimensionInputs: Map<string, HTMLInputElement> = new Map();
  private positionInputs: { x: HTMLInputElement | null; y: HTMLInputElement | null; z: HTMLInputElement | null } = { x: null, y: null, z: null };
  private massInput: HTMLInputElement | null = null;
  private colorInputs: { r: HTMLInputElement | null; g: HTMLInputElement | null; b: HTMLInputElement | null; a: HTMLInputElement | null } = { r: null, g: null, b: null, a: null };
  private spawnButton: HTMLButtonElement | null = null;
  private objectListElement: HTMLUListElement | null = null;
  private emptyMessage: HTMLParagraphElement | null = null;
  private errorNotification: HTMLDivElement | null = null;
  private errorTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;
    this.connectionManager.on('message', this.handleMessage.bind(this));
  }

  // ─── Public API ─────────────────────────────────────────────────────────

  /**
   * Mount the spawn panel into a DOM container element.
   */
  mount(container: HTMLElement): void {
    this.container = container;
    this.container.classList.add('spawn-panel');

    const heading = document.createElement('h3');
    heading.textContent = 'Object Spawner';
    this.container.appendChild(heading);

    // Error notification area
    this.errorNotification = document.createElement('div');
    this.errorNotification.classList.add('spawn-error-notification');
    this.errorNotification.style.display = 'none';
    this.container.appendChild(this.errorNotification);

    // Form section
    const form = document.createElement('div');
    form.classList.add('spawn-form');
    this.container.appendChild(form);

    // Object type selector
    this.buildTypeSelector(form);

    // Dynamic dimension inputs
    this.dimensionContainer = document.createElement('div');
    this.dimensionContainer.classList.add('spawn-dimensions');
    form.appendChild(this.dimensionContainer);
    this.buildDimensionInputs('box');

    // Position inputs
    this.buildPositionInputs(form);

    // Mass input
    this.buildMassInput(form);

    // Color inputs
    this.buildColorInputs(form);

    // Spawn button
    this.spawnButton = document.createElement('button');
    this.spawnButton.textContent = 'Spawn';
    this.spawnButton.classList.add('spawn-button');
    this.spawnButton.addEventListener('click', this.handleSpawn.bind(this));
    form.appendChild(this.spawnButton);

    // Object list section
    const listHeading = document.createElement('h4');
    listHeading.textContent = 'Spawned Objects';
    this.container.appendChild(listHeading);

    this.emptyMessage = document.createElement('p');
    this.emptyMessage.classList.add('spawn-empty-message');
    this.emptyMessage.textContent = 'No objects spawned yet.';
    this.container.appendChild(this.emptyMessage);

    this.objectListElement = document.createElement('ul');
    this.objectListElement.classList.add('spawn-object-list');
    this.container.appendChild(this.objectListElement);

    this.renderObjectList();
  }

  /**
   * Remove the component from the DOM and clean up.
   */
  unmount(): void {
    if (this.errorTimeout) {
      clearTimeout(this.errorTimeout);
      this.errorTimeout = null;
    }
    if (this.container) {
      this.container.innerHTML = '';
      this.container.classList.remove('spawn-panel');
    }
    this.dimensionInputs.clear();
    this.positionInputs = { x: null, y: null, z: null };
    this.colorInputs = { r: null, g: null, b: null, a: null };
    this.massInput = null;
    this.typeSelect = null;
    this.dimensionContainer = null;
    this.spawnButton = null;
    this.objectListElement = null;
    this.emptyMessage = null;
    this.errorNotification = null;
    this.container = null;
  }

  /**
   * Handle incoming WebSocket messages relevant to spawning.
   */
  handleMessage(message: { type: string }): void {
    switch (message.type) {
      case 'spawn_confirm':
        this.handleSpawnConfirm(message as SpawnConfirmMessage);
        break;
      case 'delete_confirm':
        this.handleDeleteConfirm(message as DeleteConfirmMessage);
        break;
      case 'error':
        this.handleError(message as ErrorMessage);
        break;
    }
  }

  /**
   * Get the list of spawned objects (for testing/external access).
   */
  getSpawnedObjects(): SpawnedObject[] {
    return [...this.spawnedObjects];
  }

  /**
   * Get the currently selected object type.
   */
  getSelectedType(): ObjectType {
    return (this.typeSelect?.value as ObjectType) ?? 'box';
  }

  // ─── Private: DOM Builders ──────────────────────────────────────────────

  private buildTypeSelector(parent: HTMLElement): void {
    const group = document.createElement('div');
    group.classList.add('spawn-field-group');

    const label = document.createElement('label');
    label.textContent = 'Type';
    label.classList.add('spawn-label');
    group.appendChild(label);

    this.typeSelect = document.createElement('select');
    this.typeSelect.classList.add('spawn-type-select');

    const types: ObjectType[] = ['box', 'sphere', 'cylinder'];
    for (const t of types) {
      const option = document.createElement('option');
      option.value = t;
      option.textContent = t.charAt(0).toUpperCase() + t.slice(1);
      this.typeSelect.appendChild(option);
    }

    this.typeSelect.addEventListener('change', () => {
      this.buildDimensionInputs(this.typeSelect!.value as ObjectType);
    });

    group.appendChild(this.typeSelect);
    parent.appendChild(group);
  }

  private buildDimensionInputs(objectType: ObjectType): void {
    if (!this.dimensionContainer) return;

    this.dimensionContainer.innerHTML = '';
    this.dimensionInputs.clear();

    const fields = DIMENSION_CONFIGS[objectType];
    for (const field of fields) {
      const group = document.createElement('div');
      group.classList.add('spawn-field-group');

      const label = document.createElement('label');
      label.textContent = field.label;
      label.classList.add('spawn-label');
      group.appendChild(label);

      const input = document.createElement('input');
      input.type = 'number';
      input.min = String(DIMENSION_MIN);
      input.max = String(DIMENSION_MAX);
      input.step = '0.01';
      input.value = String(field.defaultValue);
      input.classList.add('spawn-dimension-input');
      input.dataset.key = field.key;
      group.appendChild(input);

      this.dimensionInputs.set(field.key, input);
      this.dimensionContainer.appendChild(group);
    }
  }

  private buildPositionInputs(parent: HTMLElement): void {
    const group = document.createElement('div');
    group.classList.add('spawn-field-group', 'spawn-position-group');

    const label = document.createElement('label');
    label.textContent = 'Position (x, y, z)';
    label.classList.add('spawn-label');
    group.appendChild(label);

    const axes: Array<'x' | 'y' | 'z'> = ['x', 'y', 'z'];
    for (const axis of axes) {
      const input = document.createElement('input');
      input.type = 'number';
      input.min = String(POSITION_MIN);
      input.max = String(POSITION_MAX);
      input.step = '0.1';
      input.value = '0';
      input.classList.add('spawn-position-input');
      input.dataset.axis = axis;
      input.placeholder = axis;
      group.appendChild(input);
      this.positionInputs[axis] = input;
    }

    parent.appendChild(group);
  }

  private buildMassInput(parent: HTMLElement): void {
    const group = document.createElement('div');
    group.classList.add('spawn-field-group');

    const label = document.createElement('label');
    label.textContent = 'Mass (kg)';
    label.classList.add('spawn-label');
    group.appendChild(label);

    this.massInput = document.createElement('input');
    this.massInput.type = 'number';
    this.massInput.min = String(MASS_MIN);
    this.massInput.max = String(MASS_MAX);
    this.massInput.step = '0.01';
    this.massInput.value = '1.0';
    this.massInput.classList.add('spawn-mass-input');
    group.appendChild(this.massInput);

    parent.appendChild(group);
  }

  private buildColorInputs(parent: HTMLElement): void {
    const group = document.createElement('div');
    group.classList.add('spawn-field-group', 'spawn-color-group');

    const label = document.createElement('label');
    label.textContent = 'Color (RGBA)';
    label.classList.add('spawn-label');
    group.appendChild(label);

    const channels: Array<'r' | 'g' | 'b' | 'a'> = ['r', 'g', 'b', 'a'];
    const defaults: Record<string, string> = { r: '0.5', g: '0.5', b: '0.5', a: '1.0' };

    for (const ch of channels) {
      const input = document.createElement('input');
      input.type = 'number';
      input.min = String(COLOR_MIN);
      input.max = String(COLOR_MAX);
      input.step = '0.1';
      input.value = defaults[ch];
      input.classList.add('spawn-color-input');
      input.dataset.channel = ch;
      input.placeholder = ch.toUpperCase();
      group.appendChild(input);
      this.colorInputs[ch] = input;
    }

    parent.appendChild(group);
  }

  // ─── Private: Event Handlers ────────────────────────────────────────────

  private handleSpawn(): void {
    const objectType = this.getSelectedType();
    const dimensions = this.getDimensionValues();
    const position = this.getPositionValues();
    const color = this.getColorValues();
    const mass = this.getMassValue();

    // Client-side validation
    const error = validateSpawnRequest(objectType, dimensions, position, color, mass);
    if (error) {
      this.showError(error);
      return;
    }

    const message: SpawnObjectMessage = {
      type: 'spawn_object',
      object_type: objectType,
      dimensions,
      position,
      orientation: DEFAULT_ORIENTATION,
      color,
      mass,
    };

    const sent = this.connectionManager.send(message);
    if (!sent) {
      this.showError('Failed to send spawn request. Check connection.');
    }
  }

  private handleDelete(objectId: string): void {
    const message: DeleteObjectMessage = {
      type: 'delete_object',
      object_id: objectId,
    };

    const sent = this.connectionManager.send(message);
    if (!sent) {
      this.showError('Failed to send delete request. Check connection.');
    }
  }

  private handleSpawnConfirm(msg: SpawnConfirmMessage): void {
    this.spawnedObjects.push({
      object_id: msg.object_id,
      object_type: msg.object_type,
      position: msg.position,
    });
    this.renderObjectList();
  }

  private handleDeleteConfirm(msg: DeleteConfirmMessage): void {
    this.spawnedObjects = this.spawnedObjects.filter(
      (obj) => obj.object_id !== msg.object_id
    );
    this.renderObjectList();
  }

  private handleError(msg: ErrorMessage): void {
    this.showError(msg.message);
  }

  // ─── Private: Value Readers ─────────────────────────────────────────────

  private getDimensionValues(): number[] {
    const objectType = this.getSelectedType();
    const fields = DIMENSION_CONFIGS[objectType];
    return fields.map((field) => {
      const input = this.dimensionInputs.get(field.key);
      return input ? parseFloat(input.value) || field.defaultValue : field.defaultValue;
    });
  }

  private getPositionValues(): [number, number, number] {
    const x = this.positionInputs.x ? parseFloat(this.positionInputs.x.value) || 0 : 0;
    const y = this.positionInputs.y ? parseFloat(this.positionInputs.y.value) || 0 : 0;
    const z = this.positionInputs.z ? parseFloat(this.positionInputs.z.value) || 0 : 0;
    return [x, y, z];
  }

  private getColorValues(): [number, number, number, number] {
    const r = this.colorInputs.r ? parseFloat(this.colorInputs.r.value) || 0.5 : 0.5;
    const g = this.colorInputs.g ? parseFloat(this.colorInputs.g.value) || 0.5 : 0.5;
    const b = this.colorInputs.b ? parseFloat(this.colorInputs.b.value) || 0.5 : 0.5;
    const a = this.colorInputs.a ? parseFloat(this.colorInputs.a.value) || 1.0 : 1.0;
    return [r, g, b, a];
  }

  private getMassValue(): number {
    return this.massInput ? parseFloat(this.massInput.value) || 1.0 : 1.0;
  }

  // ─── Private: Rendering ─────────────────────────────────────────────────

  private renderObjectList(): void {
    if (!this.objectListElement || !this.emptyMessage) return;

    this.objectListElement.innerHTML = '';

    if (this.spawnedObjects.length === 0) {
      this.emptyMessage.style.display = 'block';
      this.objectListElement.style.display = 'none';
      return;
    }

    this.emptyMessage.style.display = 'none';
    this.objectListElement.style.display = 'block';

    for (const obj of this.spawnedObjects) {
      const li = document.createElement('li');
      li.classList.add('spawn-object-item');
      li.dataset.objectId = obj.object_id;

      const info = document.createElement('span');
      info.classList.add('spawn-object-info');
      const posStr = `(${obj.position[0].toFixed(2)}, ${obj.position[1].toFixed(2)}, ${obj.position[2].toFixed(2)})`;
      info.textContent = `${obj.object_id} — ${obj.object_type} @ ${posStr}`;

      const deleteBtn = document.createElement('button');
      deleteBtn.classList.add('spawn-delete-button');
      deleteBtn.textContent = 'Delete';
      deleteBtn.title = 'Delete this object';
      deleteBtn.addEventListener('click', () => this.handleDelete(obj.object_id));

      li.appendChild(info);
      li.appendChild(deleteBtn);
      this.objectListElement.appendChild(li);
    }
  }

  private showError(message: string): void {
    if (!this.errorNotification) return;

    // Clear previous timeout
    if (this.errorTimeout) {
      clearTimeout(this.errorTimeout);
    }

    this.errorNotification.textContent = message;
    this.errorNotification.style.display = 'block';

    // Auto-dismiss after ERROR_DISPLAY_MS
    this.errorTimeout = setTimeout(() => {
      this.dismissError();
    }, ERROR_DISPLAY_MS);
  }

  /**
   * Dismiss the current error notification.
   */
  dismissError(): void {
    if (this.errorNotification) {
      this.errorNotification.style.display = 'none';
      this.errorNotification.textContent = '';
    }
    if (this.errorTimeout) {
      clearTimeout(this.errorTimeout);
      this.errorTimeout = null;
    }
  }
}
