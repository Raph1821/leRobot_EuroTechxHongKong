/**
 * SceneSetup — Three.js 3D scene with camera, ground plane, lighting, and orbit controls.
 *
 * Creates the full 3D scene that hosts the robot model, providing:
 * - Perspective camera with configurable position
 * - OrbitControls for rotate, pan, and zoom interaction
 * - Ground plane grid matching robot coordinate frame
 * - X/Y/Z axis indicators
 * - Ambient + directional lighting for clear mesh visibility
 * - WebGL 2.0 renderer targeting ≥30 FPS at 1280×720
 *
 * Validates: Requirements 7.3, 7.4, 7.5
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

/** Configuration for the scene setup */
export interface SceneConfig {
  /** Container element to attach the renderer to */
  container: HTMLElement;
  /** Initial camera position [x, y, z] */
  cameraPosition?: [number, number, number];
  /** Camera field of view in degrees */
  fov?: number;
  /** Grid size (total extent in meters) */
  gridSize?: number;
  /** Grid divisions (number of cells per side) */
  gridDivisions?: number;
  /** Axis helper length in meters */
  axisLength?: number;
  /** Background color */
  backgroundColor?: number;
  /** Whether to enable antialiasing */
  antialias?: boolean;
}

/** Default configuration values */
const DEFAULTS: Required<Omit<SceneConfig, 'container'>> = {
  cameraPosition: [0.4, -0.4, 0.3],
  fov: 50,
  gridSize: 1,
  gridDivisions: 20,
  axisLength: 0.3,
  backgroundColor: 0x1a1a2e,
  antialias: true,
};

/**
 * SceneSetup manages the Three.js scene, renderer, camera, controls, and
 * visual helpers (grid, axes, lighting). It provides an animation loop
 * that renders at the display's refresh rate (≥30 FPS target).
 */
export class SceneSetup {
  /** The Three.js scene */
  public readonly scene: THREE.Scene;

  /** The perspective camera */
  public readonly camera: THREE.PerspectiveCamera;

  /** The WebGL renderer */
  public readonly renderer: THREE.WebGLRenderer;

  /** Orbit controls for camera interaction */
  public readonly controls: OrbitControls;

  /** The container element */
  private readonly container: HTMLElement;

  /** Animation frame request ID for cleanup */
  private animationFrameId: number | null = null;

  /** Whether the scene is currently animating */
  private _running = false;

  constructor(config: SceneConfig) {
    const opts = { ...DEFAULTS, ...config };
    this.container = config.container;

    // Create scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(opts.backgroundColor);

    // Create perspective camera
    const aspect = this.container.clientWidth / this.container.clientHeight || 16 / 9;
    this.camera = new THREE.PerspectiveCamera(opts.fov, aspect, 0.01, 100);
    this.camera.up.set(0, 0, 1); // Z-up (ROS convention)
    this.camera.position.set(
      opts.cameraPosition[0],
      opts.cameraPosition[1],
      opts.cameraPosition[2]
    );
    this.camera.lookAt(0, 0, 0.1);

    // Create WebGL 2.0 renderer
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2', { antialias: opts.antialias });
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      context: context ?? undefined,
      antialias: opts.antialias,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // Create orbit controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.1;
    this.controls.target.set(0, 0, 0.1);
    this.controls.minDistance = 0.1;
    this.controls.maxDistance = 5;
    this.controls.update();

    // Add lighting
    this.setupLighting();

    // Add ground plane grid
    this.setupGroundPlane(opts.gridSize, opts.gridDivisions);

    // Add axis indicators
    this.setupAxisIndicators(opts.axisLength);

    // Handle window resize
    this.onResize = this.onResize.bind(this);
    window.addEventListener('resize', this.onResize);

    // Also observe the container for resize
    if (typeof ResizeObserver !== 'undefined') {
      const resizeObserver = new ResizeObserver(() => this.onResize());
      resizeObserver.observe(this.container);
    }
  }

  /** Whether the animation loop is currently running */
  get running(): boolean {
    return this._running;
  }

  /**
   * Adds lighting to the scene: ambient light for base illumination
   * and a directional light for shadows and depth perception.
   */
  private setupLighting(): void {
    // Ambient light for overall illumination
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    ambientLight.name = 'ambient_light';
    this.scene.add(ambientLight);

    // Main directional light (simulates sunlight from above in Z-up frame)
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.name = 'directional_light';
    directionalLight.position.set(1, -1.5, 2);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 1024;
    directionalLight.shadow.mapSize.height = 1024;
    directionalLight.shadow.camera.near = 0.1;
    directionalLight.shadow.camera.far = 10;
    this.scene.add(directionalLight);

    // Fill light from opposite side to reduce harsh shadows
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.name = 'fill_light';
    fillLight.position.set(-1, 0.5, 1);
    this.scene.add(fillLight);
  }

  /**
   * Creates a ground plane grid matching the robot coordinate frame.
   * The grid lies in the XY plane (horizontal), with Z pointing up (ROS convention).
   */
  private setupGroundPlane(size: number, divisions: number): void {
    // GridHelper lies in XZ by default (Y-up). Rotate it to XY plane (Z-up).
    const gridHelper = new THREE.GridHelper(size, divisions, 0x444444, 0x333333);
    gridHelper.name = 'ground_grid';
    gridHelper.rotation.x = Math.PI / 2; // Rotate grid from XZ to XY plane
    this.scene.add(gridHelper);

    // Semi-transparent ground plane for shadow receiving (in XY plane, Z-up)
    const planeGeometry = new THREE.PlaneGeometry(size, size);
    const planeMaterial = new THREE.MeshStandardMaterial({
      color: 0x222233,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
    });
    const groundPlane = new THREE.Mesh(planeGeometry, planeMaterial);
    groundPlane.name = 'ground_plane';
    // PlaneGeometry is in XY by default — no rotation needed for Z-up
    groundPlane.position.z = -0.001; // Slightly below grid to avoid z-fighting
    groundPlane.receiveShadow = true;
    this.scene.add(groundPlane);
  }

  /**
   * Creates X/Y/Z axis indicators matching the ROS robot coordinate frame:
   * - X axis: Red (forward)
   * - Y axis: Green (left)
   * - Z axis: Blue (up)
   */
  private setupAxisIndicators(length: number): void {
    // Three.js AxesHelper draws X=red, Y=green, Z=blue
    const axesHelper = new THREE.AxesHelper(length);
    axesHelper.name = 'axis_indicators';
    this.scene.add(axesHelper);

    // Add axis labels using small spheres at the tips for visibility
    const labelSize = length * 0.05;

    // X axis label (red — forward)
    const xLabel = new THREE.Mesh(
      new THREE.SphereGeometry(labelSize, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0xff0000 })
    );
    xLabel.name = 'axis_label_x';
    xLabel.position.set(length, 0, 0);
    this.scene.add(xLabel);

    // Y axis label (green — left)
    const yLabel = new THREE.Mesh(
      new THREE.SphereGeometry(labelSize, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x00ff00 })
    );
    yLabel.name = 'axis_label_y';
    yLabel.position.set(0, length, 0);
    this.scene.add(yLabel);

    // Z axis label (blue — up)
    const zLabel = new THREE.Mesh(
      new THREE.SphereGeometry(labelSize, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x0000ff })
    );
    zLabel.name = 'axis_label_z';
    zLabel.position.set(0, 0, length);
    this.scene.add(zLabel);
  }

  /**
   * Starts the animation loop. Renders the scene and updates controls
   * at the display's refresh rate (typically 60 FPS, minimum target 30 FPS).
   */
  start(): void {
    if (this._running) return;
    this._running = true;
    this.animate();
  }

  /**
   * Stops the animation loop and cancels the pending frame.
   */
  stop(): void {
    this._running = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  /**
   * The animation loop. Called via requestAnimationFrame for smooth rendering.
   */
  private animate = (): void => {
    if (!this._running) return;
    this.animationFrameId = requestAnimationFrame(this.animate);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };

  /**
   * Handles container/window resize events by updating camera aspect ratio
   * and renderer size.
   */
  private onResize(): void {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    if (width === 0 || height === 0) return;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  /**
   * Adds a Three.js object (e.g., robot model root) to the scene.
   */
  add(object: THREE.Object3D): void {
    this.scene.add(object);
  }

  /**
   * Removes a Three.js object from the scene.
   */
  remove(object: THREE.Object3D): void {
    this.scene.remove(object);
  }

  /**
   * Disposes of all scene resources: stops animation, removes event listeners,
   * disposes renderer, controls, and all scene objects.
   */
  dispose(): void {
    this.stop();
    window.removeEventListener('resize', this.onResize);
    this.controls.dispose();

    // Dispose all scene objects
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        if (obj.material instanceof THREE.Material) {
          obj.material.dispose();
        }
      }
    });

    this.renderer.dispose();

    // Remove canvas from DOM
    if (this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
  }
}
