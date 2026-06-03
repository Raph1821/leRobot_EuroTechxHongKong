/**
 * @vitest-environment happy-dom
 */

/**
 * Unit tests for SceneSetup — 3D scene with camera, ground plane, lighting, and controls.
 *
 * Since Three.js WebGLRenderer requires a real GPU context that can't be simulated
 * in a test environment, we mock the WebGLRenderer entirely and test the scene
 * composition logic (lighting, grid, axes, controls, animation loop).
 *
 * Validates: Requirements 7.3, 7.4, 7.5
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as THREE from 'three';

// Mock WebGLRenderer before importing SceneSetup
vi.mock('three', async (importOriginal) => {
  const actual = await importOriginal<typeof import('three')>();
  class MockWebGLRenderer {
    domElement: HTMLCanvasElement;
    shadowMap = { enabled: false, type: 0 };
    private _size = { width: 0, height: 0 };

    constructor() {
      this.domElement = document.createElement('canvas');
    }
    setPixelRatio(_ratio: number) { /* no-op in test */ }
    setSize(w: number, h: number) { this._size = { width: w, height: h }; }
    getSize(target: THREE.Vector2) { return target.set(this._size.width, this._size.height); }
    render() {}
    dispose() {}
  }
  return {
    ...actual,
    WebGLRenderer: MockWebGLRenderer,
  };
});

// Mock OrbitControls
vi.mock('three/examples/jsm/controls/OrbitControls.js', () => {
  class MockOrbitControls {
    enableDamping = false;
    dampingFactor = 0.05;
    target = new THREE.Vector3();
    minDistance = 0;
    maxDistance = Infinity;
    camera: THREE.Camera;
    domElement: HTMLElement;
    dispose = vi.fn();
    update = vi.fn();

    constructor(camera: THREE.Camera, domElement: HTMLElement) {
      this.camera = camera;
      this.domElement = domElement;
    }
  }
  return { OrbitControls: MockOrbitControls };
});

import { SceneSetup } from './SceneSetup';

describe('SceneSetup', () => {
  let container: HTMLElement;
  let sceneSetup: SceneSetup | null = null;

  beforeEach(() => {
    container = document.createElement('div');
    Object.defineProperty(container, 'clientWidth', { value: 1280, configurable: true });
    Object.defineProperty(container, 'clientHeight', { value: 720, configurable: true });
    document.body.appendChild(container);

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 1);
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
  });

  afterEach(() => {
    if (sceneSetup) {
      sceneSetup.dispose();
      sceneSetup = null;
    }
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  describe('Scene creation', () => {
    it('should create a scene with background color', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.scene).toBeInstanceOf(THREE.Scene);
      expect(sceneSetup.scene.background).toBeInstanceOf(THREE.Color);
    });

    it('should create a perspective camera', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.camera).toBeInstanceOf(THREE.PerspectiveCamera);
      expect(sceneSetup.camera.fov).toBe(50);
    });

    it('should use custom camera position when provided', () => {
      sceneSetup = new SceneSetup({
        container,
        cameraPosition: [1, 2, 3],
      });
      expect(sceneSetup.camera.position.x).toBeCloseTo(1);
      expect(sceneSetup.camera.position.y).toBeCloseTo(2);
      expect(sceneSetup.camera.position.z).toBeCloseTo(3);
    });

    it('should create a renderer with a canvas element', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.renderer).toBeDefined();
      expect(sceneSetup.renderer.domElement).toBeInstanceOf(HTMLCanvasElement);
    });

    it('should set correct camera aspect ratio from container dimensions', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.camera.aspect).toBeCloseTo(1280 / 720);
    });

    it('should append canvas to the container', () => {
      sceneSetup = new SceneSetup({ container });
      const canvases = container.querySelectorAll('canvas');
      expect(canvases.length).toBe(1);
    });
  });

  describe('Orbit controls', () => {
    it('should create orbit controls attached to camera', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.controls).toBeDefined();
      // Controls are attached to the renderer's dom element
      expect(sceneSetup.controls.domElement).toBe(sceneSetup.renderer.domElement);
    });

    it('should enable damping on orbit controls', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.controls.enableDamping).toBe(true);
    });

    it('should set orbit target to slightly above origin (Z-up convention)', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.controls.target.z).toBeCloseTo(0.1);
    });
  });

  describe('Ground plane and grid', () => {
    it('should add a grid helper to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const grid = sceneSetup.scene.getObjectByName('ground_grid');
      expect(grid).toBeDefined();
      expect(grid).toBeInstanceOf(THREE.GridHelper);
    });

    it('should add a ground plane mesh to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const plane = sceneSetup.scene.getObjectByName('ground_plane');
      expect(plane).toBeDefined();
      expect(plane).toBeInstanceOf(THREE.Mesh);
    });

    it('should position ground plane in XY plane (Z-up, no rotation needed)', () => {
      sceneSetup = new SceneSetup({ container });
      const plane = sceneSetup.scene.getObjectByName('ground_plane') as THREE.Mesh;
      // PlaneGeometry is in XY by default — no rotation needed for Z-up convention
      expect(plane.rotation.x).toBeCloseTo(0);
    });
  });

  describe('Axis indicators', () => {
    it('should add axis helper to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const axes = sceneSetup.scene.getObjectByName('axis_indicators');
      expect(axes).toBeDefined();
      expect(axes).toBeInstanceOf(THREE.AxesHelper);
    });

    it('should add X axis label at positive X position', () => {
      sceneSetup = new SceneSetup({ container });
      const xLabel = sceneSetup.scene.getObjectByName('axis_label_x');
      expect(xLabel).toBeDefined();
      expect(xLabel!.position.x).toBeGreaterThan(0);
      expect(xLabel!.position.y).toBeCloseTo(0);
      expect(xLabel!.position.z).toBeCloseTo(0);
    });

    it('should add Y axis label at positive Y position', () => {
      sceneSetup = new SceneSetup({ container });
      const yLabel = sceneSetup.scene.getObjectByName('axis_label_y');
      expect(yLabel).toBeDefined();
      expect(yLabel!.position.x).toBeCloseTo(0);
      expect(yLabel!.position.y).toBeGreaterThan(0);
      expect(yLabel!.position.z).toBeCloseTo(0);
    });

    it('should add Z axis label at positive Z position', () => {
      sceneSetup = new SceneSetup({ container });
      const zLabel = sceneSetup.scene.getObjectByName('axis_label_z');
      expect(zLabel).toBeDefined();
      expect(zLabel!.position.x).toBeCloseTo(0);
      expect(zLabel!.position.y).toBeCloseTo(0);
      expect(zLabel!.position.z).toBeGreaterThan(0);
    });

    it('should use custom axis length', () => {
      sceneSetup = new SceneSetup({ container, axisLength: 0.5 });
      const xLabel = sceneSetup.scene.getObjectByName('axis_label_x');
      expect(xLabel!.position.x).toBeCloseTo(0.5);
    });
  });

  describe('Lighting', () => {
    it('should add ambient light to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const ambient = sceneSetup.scene.getObjectByName('ambient_light');
      expect(ambient).toBeDefined();
      expect(ambient).toBeInstanceOf(THREE.AmbientLight);
    });

    it('should add directional light to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const directional = sceneSetup.scene.getObjectByName('directional_light');
      expect(directional).toBeDefined();
      expect(directional).toBeInstanceOf(THREE.DirectionalLight);
    });

    it('should add fill light to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const fill = sceneSetup.scene.getObjectByName('fill_light');
      expect(fill).toBeDefined();
      expect(fill).toBeInstanceOf(THREE.DirectionalLight);
    });

    it('should enable shadows on the directional light', () => {
      sceneSetup = new SceneSetup({ container });
      const directional = sceneSetup.scene.getObjectByName(
        'directional_light'
      ) as THREE.DirectionalLight;
      expect(directional.castShadow).toBe(true);
    });
  });

  describe('Animation loop', () => {
    it('should not be running initially', () => {
      sceneSetup = new SceneSetup({ container });
      expect(sceneSetup.running).toBe(false);
    });

    it('should start the animation loop', () => {
      sceneSetup = new SceneSetup({ container });
      sceneSetup.start();
      expect(sceneSetup.running).toBe(true);
      expect(window.requestAnimationFrame).toHaveBeenCalled();
    });

    it('should stop the animation loop', () => {
      sceneSetup = new SceneSetup({ container });
      sceneSetup.start();
      sceneSetup.stop();
      expect(sceneSetup.running).toBe(false);
      expect(window.cancelAnimationFrame).toHaveBeenCalled();
    });

    it('should not start multiple loops if start() called twice', () => {
      sceneSetup = new SceneSetup({ container });
      sceneSetup.start();
      sceneSetup.start();
      expect(window.requestAnimationFrame).toHaveBeenCalledTimes(1);
    });
  });

  describe('Scene management', () => {
    it('should add objects to the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const group = new THREE.Group();
      group.name = 'test_object';
      sceneSetup.add(group);
      expect(sceneSetup.scene.getObjectByName('test_object')).toBe(group);
    });

    it('should remove objects from the scene', () => {
      sceneSetup = new SceneSetup({ container });
      const group = new THREE.Group();
      group.name = 'test_object';
      sceneSetup.add(group);
      sceneSetup.remove(group);
      expect(sceneSetup.scene.getObjectByName('test_object')).toBeUndefined();
    });
  });

  describe('Disposal', () => {
    it('should stop animation on dispose', () => {
      sceneSetup = new SceneSetup({ container });
      sceneSetup.start();
      sceneSetup.dispose();
      expect(sceneSetup.running).toBe(false);
      sceneSetup = null;
    });

    it('should dispose orbit controls', () => {
      sceneSetup = new SceneSetup({ container });
      const disposeSpy = vi.spyOn(sceneSetup.controls, 'dispose');
      sceneSetup.dispose();
      expect(disposeSpy).toHaveBeenCalled();
      sceneSetup = null;
    });

    it('should dispose the renderer', () => {
      sceneSetup = new SceneSetup({ container });
      const disposeSpy = vi.spyOn(sceneSetup.renderer, 'dispose');
      sceneSetup.dispose();
      expect(disposeSpy).toHaveBeenCalled();
      sceneSetup = null;
    });
  });

  describe('Configuration', () => {
    it('should use default background color', () => {
      sceneSetup = new SceneSetup({ container });
      const bg = sceneSetup.scene.background as THREE.Color;
      expect(bg.getHex()).toBe(0x1a1a2e);
    });

    it('should accept custom background color', () => {
      sceneSetup = new SceneSetup({ container, backgroundColor: 0xffffff });
      const bg = sceneSetup.scene.background as THREE.Color;
      expect(bg.getHex()).toBe(0xffffff);
    });

    it('should accept custom FOV', () => {
      sceneSetup = new SceneSetup({ container, fov: 75 });
      expect(sceneSetup.camera.fov).toBe(75);
    });
  });
});
