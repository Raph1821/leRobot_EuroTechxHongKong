/**
 * SO-100 Robot Arm Web Control Interface — Application Entry Point
 *
 * Wires all components together into a single-page application:
 * - ConnectionManager: shared WebSocket lifecycle for all components
 * - SceneSetup: Three.js scene with camera, grid, lighting, orbit controls
 * - RobotModel3D: kinematic chain with STL meshes
 * - MultiRobotModel3D: multi-robot rendering with namespace isolation
 * - RobotViewer: bridges ConnectionManager messages to the 3D model
 * - JointControlPanel: 5 arm joint sliders
 * - GripperControl: gripper slider + open/close buttons
 * - HomeButton: commands all joints to 0.0 rad
 * - PoseManager: save/list/delete/select poses + trajectory playback
 * - StatusDisplay: connection indicator + sim status + error notifications
 * - CameraStreamPanel: live camera viewport from Isaac Sim
 * - SpawnPanel: interactive object spawning in simulation
 * - CartesianControlPanel: end-effector Cartesian control via IK
 * - EpisodePanel: episode recording and replay controls
 * - TeleopPanel: keyboard/gamepad teleoperation mode
 * - RobotSelector: multi-robot namespace selection
 * - TeleopController: velocity command generation from input devices
 *
 * Requirements: 1.5, 2.4, 3.4, 4.2, 5.4, 6.3, 7.1, 8.1, 10.1
 */

import { ConnectionManager } from './services/ConnectionManager';
import { TeleopController } from './services/TeleopController';
import { SceneSetup } from './components/SceneSetup';
import { RobotModel3D } from './components/RobotModel3D';
import { MultiRobotModel3D } from './components/MultiRobotModel3D';
import { RobotViewer } from './components/RobotViewer';
import { JointControlPanel } from './components/JointControlPanel';
import { GripperControl } from './components/GripperControl';
import { HomeButton } from './components/HomeButton';
import { PoseManager } from './components/PoseManager';
import { StatusDisplay } from './components/StatusDisplay';
import { CameraStreamPanel } from './components/CameraStreamPanel';
import { SpawnPanel } from './components/SpawnPanel';
import { CartesianControlPanel } from './components/CartesianControlPanel';
import { EpisodePanel } from './components/EpisodePanel';
import { TeleopPanel } from './components/TeleopPanel';
import { RobotSelector } from './components/RobotSelector';
import { JOINT_CONFIGS } from './types';
import type { JointCommandMessage, GripperCommandMessage, TeleopVelocityMessage } from './types';

// ─── Configuration ──────────────────────────────────────────────────────────

/** WebSocket URL — defaults to ws://localhost:9090 (ROS2 bridge default) */
const WS_URL = `ws://${window.location.hostname || 'localhost'}:9090`;

// ─── Application Bootstrap ──────────────────────────────────────────────────

function initApp(): void {
  // 1. Create the shared ConnectionManager instance
  const connectionManager = new ConnectionManager({
    url: WS_URL,
    messageTimeoutMs: 3000,
    reconnectIntervalMs: 2000,
    maxReconnectAttempts: 10,
  });

  // 2. Set up the 3D viewer
  const viewerContainer = document.getElementById('viewer-container');
  if (!viewerContainer) {
    console.error('Could not find #viewer-container element');
    return;
  }

  const sceneSetup = new SceneSetup({ container: viewerContainer });
  const robotModel = new RobotModel3D('/meshes');

  // Multi-robot model for rendering all configured robots simultaneously
  const multiRobotModel = new MultiRobotModel3D('/meshes');

  // Add single robot model to the scene (backward compat for single-robot mode)
  robotModel.loadPromise
    .then(() => {
      sceneSetup.add(robotModel.root);
    })
    .catch((err) => {
      console.error('Failed to load robot model:', err);
    });

  // Wire ConnectionManager to RobotModel3D for live joint state updates
  // RobotViewer self-registers as a listener on the ConnectionManager
  new RobotViewer(connectionManager, robotModel);

  // Local joint model update: when a joint command is sent (slider moved),
  // immediately update the 3D model for visual feedback even without a
  // running simulation. This is overridden by real joint_state messages
  // when the simulation is connected.
  const localPositions = [0, 0, 0, 0, 0, 0];
  const originalSend = connectionManager.send.bind(connectionManager);
  connectionManager.send = (message) => {
    const result = originalSend(message);
    // Apply local model update for immediate visual feedback
    if (message.type === 'joint_command') {
      for (const joint of (message as JointCommandMessage).joints) {
        const idx = JOINT_CONFIGS.findIndex(c => c.name === joint.name);
        if (idx !== -1) {
          localPositions[idx] = joint.position;
        }
      }
      robotModel.updateJointAngles(localPositions);
    } else if (message.type === 'gripper_command') {
      localPositions[5] = (message as GripperCommandMessage).position;
      robotModel.updateJointAngles(localPositions);
    }
    return result;
  };

  // Start the render loop
  sceneSetup.start();

  // 3. Set up the Joint Control Panel
  let jointControlPanel: JointControlPanel | null = null;
  const jointControlsContainer = document.getElementById('joint-controls');
  if (jointControlsContainer) {
    jointControlPanel = new JointControlPanel(connectionManager);
    jointControlPanel.mount(jointControlsContainer);
  }

  // 4. Set up the Gripper Control
  const gripperControlContainer = document.getElementById('gripper-control');
  if (gripperControlContainer) {
    new GripperControl({
      connectionManager,
      container: gripperControlContainer,
    });
  }

  // 5. Set up the Home Button
  const homeSection = document.getElementById('home-section');
  if (homeSection) {
    new HomeButton({
      connectionManager,
      container: homeSection,
    });
  }

  // 6. Set up the Pose Manager
  const poseManagerContainer = document.getElementById('pose-manager');
  if (poseManagerContainer) {
    const poseManager = new PoseManager(connectionManager);
    poseManager.mount(poseManagerContainer);
  }

  // 7. Set up the Status Display
  const statusDisplayContainer = document.getElementById('status-display');
  if (statusDisplayContainer) {
    const statusDisplay = new StatusDisplay(connectionManager);
    statusDisplay.mount(statusDisplayContainer);
  }

  // ─── New Components ─────────────────────────────────────────────────────

  // 8. Camera Stream Panel (Req 1.5)
  const cameraStreamContainer = document.getElementById('camera-stream-panel');
  let cameraStreamPanel: CameraStreamPanel | null = null;
  if (cameraStreamContainer) {
    cameraStreamPanel = new CameraStreamPanel(connectionManager);
    cameraStreamPanel.mount(cameraStreamContainer);
  }

  // 9. Spawn Panel (Req 2.4)
  const spawnPanelContainer = document.getElementById('spawn-panel');
  let spawnPanel: SpawnPanel | null = null;
  if (spawnPanelContainer) {
    spawnPanel = new SpawnPanel(connectionManager);
    spawnPanel.mount(spawnPanelContainer);
  }

  // 10. Cartesian Control Panel (Req 3.4)
  const cartesianContainer = document.getElementById('cartesian-control-panel');
  let cartesianPanel: CartesianControlPanel | null = null;
  if (cartesianContainer) {
    cartesianPanel = new CartesianControlPanel(connectionManager, sceneSetup);
    cartesianPanel.mount(cartesianContainer);
  }

  // 11. Episode Panel (Req 4.2)
  const episodeContainer = document.getElementById('episode-panel');
  let episodePanel: EpisodePanel | null = null;
  if (episodeContainer) {
    episodePanel = new EpisodePanel(connectionManager);
    episodePanel.mount(episodeContainer);
  }

  // 12. Teleop Panel (Req 5.4)
  const teleopContainer = document.getElementById('teleop-panel');
  let teleopPanel: TeleopPanel | null = null;
  if (teleopContainer) {
    teleopPanel = new TeleopPanel({ connectionManager });
    teleopPanel.mount(teleopContainer);
  }

  // 13. TeleopController — wired to ConnectionManager for sending velocity commands (Req 5.4)
  const teleopController = new TeleopController(
    (message: TeleopVelocityMessage) => {
      connectionManager.send(message);
    }
  );

  // 14. Robot Selector (Req 6.3)
  const robotSelectorContainer = document.getElementById('robot-selector');
  let robotSelector: RobotSelector | null = null;
  if (robotSelectorContainer) {
    robotSelector = new RobotSelector({ connectionManager });
    robotSelector.mount(robotSelectorContainer);
  }

  // ─── Cross-Component Wiring ─────────────────────────────────────────────

  // Wire RobotSelector to all control panels — when a new robot is selected,
  // update the namespace routing and synchronize controls (Req 6.3, 6.4)
  if (robotSelector) {
    robotSelector.onRobotSelected = (robotId: string) => {
      // Update multi-robot model highlight
      multiRobotModel.setActiveRobot(robotId);

      // Send select_robot command to the bridge for namespace routing
      connectionManager.send({ type: 'select_robot', robot_id: robotId });
    };
  }

  // Wire EpisodePanel replay state to disable/enable manual controls (Req 4.7, 4.9)
  if (episodePanel) {
    episodePanel.setOnReplayStateChange((replaying: boolean) => {
      // Disable/enable joint sliders during replay
      if (jointControlPanel) {
        jointControlPanel.setDisabled(replaying);
      }

      // Disable/enable Cartesian control panel during replay
      if (cartesianPanel) {
        cartesianPanel.setDisabled(replaying);
      }

      // Disable/enable teleop during replay
      if (replaying) {
        teleopController.disable();
        // If the teleop panel is showing as enabled, the mode message is sent internally
      } else {
        // Re-enable is left to the user to toggle on again via the UI
      }
    });
  }

  // Wire ConnectionManager message events to new components that need manual routing
  connectionManager.on('message', (message) => {
    // Route spawn messages to SpawnPanel
    if (spawnPanel) {
      if (
        message.type === 'spawn_confirm' ||
        message.type === 'delete_confirm' ||
        message.type === 'error'
      ) {
        spawnPanel.handleMessage(message);
      }
    }

    // Route robot list, status changes, and joint states to RobotSelector
    if (robotSelector) {
      if (
        message.type === 'robot_list' ||
        message.type === 'robot_status_change' ||
        message.type === 'joint_state'
      ) {
        robotSelector.handleMessage(message);
      }
    }

    // Route joint states to MultiRobotModel3D for multi-robot rendering
    if (message.type === 'joint_state' && 'robot_id' in message) {
      const robotId = (message as { robot_id: string }).robot_id;
      const positions = (message as { joints: { positions: number[] } }).joints.positions;
      // Ensure the robot instance exists
      if (!multiRobotModel.getRobot(robotId)) {
        multiRobotModel.addRobot(robotId);
        sceneSetup.add(multiRobotModel.root);
      }
      multiRobotModel.updateJointAngles(robotId, positions);
    }

    // Route teleop-related errors to TeleopPanel for unreachable indicator
    if (teleopPanel && message.type === 'error') {
      const errorMsg = message as { type: 'error'; code: string; message: string };
      if (errorMsg.code === 'IK_NO_SOLUTION' || errorMsg.code === 'IK_TIMEOUT') {
        teleopPanel.showUnreachableIndicator();
      }
    }
  });

  // Wire connection loss to TeleopController — deactivate teleop on disconnect (Req 5.8)
  connectionManager.on('controlsDisabled', () => {
    teleopController.disable();
  });

  // 15. Start the WebSocket connection
  connectionManager.connect();

  console.log('SO-100 Web Control Interface initialized (expanded)');
}

// ─── Entry Point ────────────────────────────────────────────────────────────

// Wait for DOM to be ready before bootstrapping
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
