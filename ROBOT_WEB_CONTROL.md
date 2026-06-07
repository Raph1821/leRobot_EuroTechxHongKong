# Robot Web Control System

Complete backend and frontend implementation for controlling the SO-100/SO-101 robotic arm through a web interface.

## Overview

This system provides comprehensive robot control through a WebSocket-based architecture:
- **Backend**: ROS2 WebSocket bridge (`so_arm_100_web_bridge`)
- **Frontend**: Next.js web application with multiple control modes
- **Real-time Communication**: 30Hz joint state updates, 20Hz teleop commands

## Architecture

```
┌─────────────────┐         WebSocket          ┌──────────────────┐
│   Web Browser   │ ◄─────────────────────────► │  ROS2 Bridge     │
│   (Next.js)     │     ws://localhost:9090     │  (Python)        │
└─────────────────┘                             └──────────────────┘
        │                                                │
        │                                                │
        ▼                                                ▼
┌─────────────────┐                             ┌──────────────────┐
│  Control Modes: │                             │  ROS2 Topics:    │
│  - Keyboard     │                             │  - joint_states  │
│  - Cartesian    │                             │  - trajectories  │
│  - Manual       │                             │  - camera feed   │
│  - Recorder     │                             │  - IK service    │
└─────────────────┘                             └──────────────────┘
```

## Features Implemented

### Frontend Components

#### 1. **Keyboard Control** (`webapp/components/KeyboardControl.tsx`)
Real-time velocity-based teleoperation using keyboard input.

**Controls:**
- **W/↑, S/↓**: Forward/Backward (X-axis)
- **A/←, D/→**: Left/Right (Y-axis)
- **Q, E**: Up/Down (Z-axis)
- **J, L**: Yaw rotation
- **I, K**: Pitch rotation
- **U, O**: Roll rotation

**Features:**
- Adjustable velocity scale (0.01-0.2 m/s or rad/s)
- 20Hz command rate when active
- Zero-velocity on key release (safety)
- Visual feedback of active keys

#### 2. **Cartesian Control** (`webapp/components/CartesianControl.tsx`)
Move the end-effector to specific positions in 3D space using inverse kinematics.

**Features:**
- Position sliders (X, Y, Z) with workspace bounds
- Optional quaternion orientation control
- Adjustable movement duration (0.5-10 seconds)
- Real-time trajectory status feedback
- Workspace validation (-0.3 to 0.3m X/Y, 0.0 to 0.5m Z)

#### 3. **Manual Control** (`webapp/components/ControlPanel.tsx`)
Direct joint position control with sliders.

**Features:**
- Individual joint sliders for all 6 DOF + gripper
- Real-time joint limits from URDF
- 3D visualization feedback
- Home position button

#### 4. **Episode Recorder** (`webapp/components/EpisodeRecorder.tsx`)
Record and replay robot movements for dataset creation.

**Features:**
- Start/Stop/Discard recording
- List saved episodes
- Replay episodes
- rosbag2 MCAP format storage

### Backend (Already Implemented)

The backend is fully functional and supports:

#### Message Types

**Client → Server:**
- `teleop_mode`: Enable/disable velocity control
- `teleop_velocity`: Send Cartesian velocity commands
- `joint_command`: Set individual joint positions
- `gripper_command`: Control gripper position
- `cartesian_goal`: IK-based position control
- `trajectory_goal`: Multi-waypoint trajectories
- `episode_control`: Recording/replay commands
- `camera_stream_control`: Toggle camera feed
- `select_robot`: Multi-robot namespace switching

**Server → Client:**
- `joint_state`: 30Hz robot state updates
- `trajectory_status`: Execution feedback
- `recording_status`: Recording state
- `episode_list`: Available recordings
- `camera_frame`: JPEG camera stream
- `error`: Error messages with codes

## Setup Instructions

### 1. Start the ROS2 Backend

```bash
# Terminal 1: Launch the robot (simulation or hardware)
cd leRobot_EuroTechxHongKong
ros2 launch so_arm_100_bringup sim.launch.py

# Terminal 2: Launch the WebSocket bridge
ros2 launch so_arm_100_bringup web_control.launch.py
```

**Bridge Configuration:**
- WebSocket URL: `ws://0.0.0.0:9090`
- Broadcast rate: 30 Hz
- Camera topic: `/viewport_camera/image_raw`
- Episode storage: `/tmp/episode_recorder`

### 2. Start the Web Frontend

```bash
# Terminal 3: Start the Next.js development server
cd webapp
npm install  # First time only
npm run dev
```

The web interface will be available at `http://localhost:3000`

### 3. Access the Control Interface

1. Navigate to `http://localhost:3000`
2. Login (if required) as **Nurse** or **Doctor** role
3. Go to **Control** page from the sidebar
4. Click the **Teleop** tab

## Usage Guide

### Keyboard Teleoperation

1. Click the **Teleop** tab
2. Select **Keyboard** mode
3. Adjust the velocity scale slider (recommended: 0.05)
4. Click **Start** button
5. Use keyboard controls (see Controls section above)
6. Click **Stop** when done (or release all keys for safety)

**Safety Notes:**
- Robot stops immediately when all keys are released
- Velocity scale limits maximum speed
- Backend enforces joint velocity limits (2.0 rad/s max)

### Cartesian Control

1. Select **Cartesian** mode
2. Adjust target position sliders (X, Y, Z)
3. Optionally enable custom orientation
4. Set movement duration
5. Click **Send Goal**
6. Monitor trajectory status (executing → succeeded/aborted)

**Workspace Bounds:**
- X: -0.3 to 0.3 meters
- Y: -0.3 to 0.3 meters
- Z: 0.0 to 0.5 meters

### Episode Recording

1. Select **Recorder** mode
2. Click **Start Recording**
3. Control the robot using any method (keyboard, manual, etc.)
4. Click **Save Recording** (or **Discard** to cancel)
5. Episodes appear in the list below
6. Click **Replay** on any episode to playback

**Storage Location:** `/tmp/episode_recorder/`

**Format:** rosbag2 MCAP files

## Code Structure

### Frontend Files

```
webapp/
├── components/
│   ├── ManualControl.tsx          # Main control page with tabs
│   ├── TeleopPanel.tsx            # Advanced control modes container
│   ├── KeyboardControl.tsx        # ⭐ NEW: Keyboard teleoperation
│   ├── CartesianControl.tsx       # ⭐ NEW: Cartesian control UI
│   ├── EpisodeRecorder.tsx        # ⭐ NEW: Recording interface
│   ├── ControlPanel.tsx           # Manual joint sliders
│   ├── SimulatorPanel.tsx         # Gazebo diagnostics
│   └── RobotViewer.tsx            # 3D robot visualization
│
└── lib/
    ├── jointStore.tsx             # ⭐ UPDATED: WebSocket state management
    └── joints.ts                  # Joint definitions & limits
```

### Backend Files (Already Implemented)

```
so_arm_100_web_bridge/
└── so_arm_100_web_bridge/
    ├── websocket_bridge_node.py   # Main WebSocket server
    ├── teleop_handler.py          # Velocity teleoperation
    ├── cartesian_controller.py    # IK integration
    ├── episode_handler.py         # Recording/replay
    ├── message_schemas.py         # Protocol validation
    ├── joint_validator.py         # Joint limits
    └── namespace_router.py        # Multi-robot support
```

## WebSocket Protocol

### Example: Enable Keyboard Teleoperation

**Enable:**
```json
{
  "type": "teleop_mode",
  "enabled": true,
  "velocity_scale": 0.05
}
```

**Send Velocity:**
```json
{
  "type": "teleop_velocity",
  "linear": [0.05, 0.0, 0.0],
  "angular": [0.0, 0.0, 0.0]
}
```

**Disable:**
```json
{
  "type": "teleop_mode",
  "enabled": false
}
```

### Example: Cartesian Goal

```json
{
  "type": "cartesian_goal",
  "position": { "x": 0.2, "y": 0.0, "z": 0.3 },
  "orientation": { "x": 0, "y": 0, "z": 0, "w": 1 },
  "duration_sec": 2.0
}
```

### Example: Episode Recording

**Start:**
```json
{
  "type": "episode_control",
  "command": "start_recording"
}
```

**Stop:**
```json
{
  "type": "episode_control",
  "command": "stop_recording"
}
```

**List:**
```json
{
  "type": "episode_control",
  "command": "list_episodes"
}
```

**Replay:**
```json
{
  "type": "episode_control",
  "command": "replay_episode",
  "episode_name": "episode_2024_01_01_12_00_00"
}
```

## Testing

### Test WebSocket Connection

```python
import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:9090") as ws:
        # Send teleop command
        await ws.send(json.dumps({
            "type": "teleop_mode",
            "enabled": True,
            "velocity_scale": 0.05
        }))
        
        # Receive joint states
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test())
```

### Check ROS2 Topics

```bash
# Monitor joint states
ros2 topic echo /joint_states

# Monitor trajectory commands
ros2 topic echo /arm_controller/joint_trajectory

# Check bridge logs
ros2 run so_arm_100_web_bridge websocket_bridge --ros-args --log-level debug
```

## Troubleshooting

### WebSocket Connection Failed
- Check that `web_control.launch.py` is running
- Verify port 9090 is not blocked
- Check browser console for errors

### Robot Not Moving
- Verify ROS2 controllers are active: `ros2 control list_controllers`
- Check joint limits in `joint_validator.py`
- Monitor for error messages in WebSocket responses

### Keyboard Control Not Working
- Ensure teleop mode is enabled (click Start button)
- Check that browser window has focus
- Verify velocity scale is not too low

### IK Solver Fails
- Position may be outside workspace bounds
- Check that IK service is running: `ros2 service list | grep compute_ik`
- Reduce target distance from current position

## Performance Metrics

- **Joint State Broadcast**: 30 Hz
- **Teleop Command Rate**: 20 Hz
- **WebSocket Latency**: < 10ms (local)
- **IK Computation**: < 500ms
- **Camera Stream**: ~10 fps @ 75% JPEG quality

## Safety Features

1. **Velocity Limits**: 2.0 rad/s max per joint
2. **Workspace Bounds**: Cartesian limits enforced
3. **Zero-Velocity on Stop**: Automatic safety stop
4. **Joint Limits**: URDF-based validation
5. **Connection Monitoring**: Auto-reconnect on disconnect

## Future Enhancements

- [ ] Virtual joystick for mobile devices
- [ ] Multi-robot control switching
- [ ] Force/torque feedback display
- [ ] Trajectory visualization in 3D
- [ ] Collision detection warnings
- [ ] Custom waypoint planner

## Credits

- **Backend**: `so_arm_100_web_bridge` ROS2 package
- **Frontend**: Next.js + React + TailwindCSS
- **3D Rendering**: Three.js + React Three Fiber
- **Robot Model**: SO-100/SO-101 URDF

## License

See LICENSE file in repository root.
