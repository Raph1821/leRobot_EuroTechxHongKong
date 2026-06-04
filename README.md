# SO-100 Robot Arm ROS2 Package

This package provides ROS2 support for the SO-100 robot arm, available in 5-DOF configuration. It is based on the open-source 3D printable [SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) project by The Robot Studio. This implementation includes URDF models, Gazebo simulation support, and MoveIt2 integration.

The original ROS1 implementation can be found at: https://github.com/TheRobotStudio/SO-ARM100

## Features

- Robot arm URDF models
  - 5-DOF configuration with gripper
- Gazebo Harmonic simulation support
- ROS2 Control integration
  - Joint trajectory controller
  - Gripper action controller
- MoveIt2 motion planning capabilities (In Progress)
  - Basic configuration generated
  - Integration with Gazebo pending
  - Motion planning testing pending

## Prerequisites

### Docker (Recommended)

The easiest way to run the full stack (simulation + web interface) is with Docker:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Linux containers enabled
- NVIDIA GPU with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (for Isaac Sim)
- GPU compute capability ≥ 7.0

### ROS2 and Dependencies

- ROS2 Humble
- Gazebo Garden
- MoveIt2
- ros2_control
- gz_ros2_control

### Hardware Requirements

For using the physical robot:

- SO-ARM-100 robot arm (5-DOF)
- Feetech SMS/STS series servos
- USB-to-Serial converter (CH340 chip)
- so_arm_100_hardware package installed:

  ```bash
  cd ~/ros2_ws/src
  git clone git@github.com:brukg/so_arm_100_hardware.git
  cd ~/ros2_ws
  colcon build --packages-select so_arm_100_hardware
  source install/setup.bash
  ```

## Installation

### Create a ROS2 workspace (if you don't have one)

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
```

### Clone the repository

```bash
git clone git@github.com:brukg/SO-100-arm.git
```

### Install dependencies

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
```

### Build the package

```bash
colcon build --packages-select so_arm_100
source install/setup.bash
```

## Usage

### Docker — Build & Run

#### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Linux containers enabled
- At least **20 GB free disk space** (the base image is ~3 GB, build artifacts add more)
- The `so101-ros-physical-ai-main` repo as a sibling directory (for SO-101 packages)

#### Build the Docker Image

**Linux/macOS:**

```bash
# From the SO-100-arm-main project root:
./scripts/docker-build.sh
```

**Windows (PowerShell):**

```powershell
# 1. Copy SO-101 packages into the build context
$packages = @("so101_description", "so101_bringup", "so101_teleop", "so101_moveit_config",
              "so101_kinematics", "so101_kinematics_msgs", "so101_camera_calibration",
              "so101_inference", "episode_recorder", "rosbag_to_lerobot", "policy_server")
$src = "..\so101-ros-physical-ai-main\so101-ros-physical-ai-main"
foreach ($pkg in $packages) {
    if (Test-Path "$src\$pkg") {
        Copy-Item -Path "$src\$pkg" -Destination ".\$pkg" -Recurse -Force
        Write-Host "Copied $pkg"
    }
}

# 2. Build the image
docker build -t so100-all-in-one .

# 3. Clean up copied packages (they stay in .dockerignore for git)
foreach ($pkg in $packages) { Remove-Item -Recurse -Force ".\$pkg" -ErrorAction SilentlyContinue }
```

#### Troubleshooting Build Errors

| Error | Fix |
|-------|-----|
| `failed to Lchown ... read-only file system` | Docker Desktop disk full. Run `docker system prune -a` then restart Docker Desktop. |
| `SO-101 source directory not found` | Set `SO101_SRC_DIR` env var to the path of the so101 repo root. |
| `COPY so101_* ... not found` | You forgot to copy SO-101 packages into the build context first. |
| Timeout during image pull | The base image (`osrf/ros:jazzy-desktop`) is ~1.2 GB. Retry on a stable connection. |

#### Run the Container

```bash
# Start with docker-compose (simulation + web UI auto-start)
docker compose up

# Or use the run script (Linux/macOS)
./scripts/docker-run.sh --auto

# Or run manually
docker run --rm -it --gpus all --network host --ipc host \
  -e AUTO_START=1 \
  -v $(pwd):/workspace:rw \
  --name so100-dev \
  so100-all-in-one
```

**Access points:**

| Service | URL |
|---------|-----|
| Web interface | http://localhost:8080 |
| WebSocket bridge | ws://localhost:9090 |

**Profiles:**

```bash
# Without hardware (default — simulation only)
docker compose up

# With USB hardware connected (feetech servos)
docker compose --profile hardware up
```

#### Manual Commands Inside the Container

```bash
# Drop into the container shell
docker exec -it so100-dev bash

# Source the workspace (if not auto-sourced)
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

# Rebuild the workspace (after code changes)
cd /workspace && colcon build --symlink-install

# Launch Isaac Sim simulation
ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=isaac_sim

# Start WebSocket bridge manually
ros2 run so_arm_100_web_bridge websocket_bridge

# Serve web interface manually
python3 -m http.server 8080 --directory /workspace/web_static

# Run all tests
cd /workspace && colcon test && colcon test-result --verbose
```

#### Common Runtime Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Package 'so_arm_100_web_bridge' not found` | Workspace not built or not sourced | Run `source /workspace/install/setup.bash` or rebuild with `colcon build` |
| `No such file or directory: .../dist` | Web interface not built | Use `/workspace/web_static` (built during Docker image creation) or run `cd /workspace/web_interface && npm ci && npx vite build` |
| `ros2: command not found` | ROS2 not sourced | Run `source /opt/ros/jazzy/setup.bash` |
| Isaac Sim fails to start | No GPU or NVIDIA driver issue | Ensure `--gpus all` is passed and `nvidia-smi` works inside the container |

### Launch the Hardware Interface

```bash
## Launch the hardware interface
ros2 launch so_arm_100 hardware.launch.py
```

### Test Servo Communication

To verify servo connections and read their status:

```bash
# Build the test program
cd ~/ros2_ws
colcon build --packages-select so_arm_100_hardware
source install/setup.bash

# Set USB permissions
sudo chmod 666 /dev/ttyUSB0

# Run the servo test
ros2 run so_arm_100_hardware test_servo
```

This will:

- Test communication with each servo (ID 1-6)
- Read current position, voltage, temperature
- Verify position control mode
- Show any communication errors

Example output for working servos:

```

Testing servo 1...
  Servo 1 responded to ping
  Set to position control mode
  Position: 1963
  Voltage: 7.4V
  Temperature: 29°C
  Load: -24
```

### Test Hardware Interface

Send a test trajectory to move the physical arm:

```bash
ros2 action send_goal /arm_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{
  trajectory: {
    joint_names: [Shoulder_Rotation, Shoulder_Pitch, Elbow, Wrist_Pitch, Wrist_Roll],
    points: [
      {
        positions: [-0.5, -1.0, 0.5, 0.0, 0.0],
        velocities: [0.0, 0.0, 0.0, 0.0, 0.0],
        time_from_start: {sec: 2, nanosec: 0}
      },
      {
        positions: [-0.5, 0.50, 0.0, 0.0, 0.0],
        velocities: [0.0, 0.0, 0.0, 0.0, 0.0],
        time_from_start: {sec: 4, nanosec: 0}
      }
    ]
  }
}"
```

This will move the arm through two positions:

- First point (2 sec): Shoulder down with elbow bent
- Second point (4 sec): Shoulder up with arm extended

Note: Ensure the arm has clear space to move before sending commands.

### Launch the robot in Gazebo

```bash
ros2 launch so_arm_100 gz.launch.py dof:5
```

### Launch the robot in RVIZ

```bash
ros2 launch so_arm_100 rviz.launch.py
```

### Launch MoveIt2 Demo

```bash
ros2 launch so_arm_100 demo.launch.py
```

### Test Joint Movement


#### Send a test position command for 5dof arm

```bash
ros2 topic pub /arm_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory '{joint_names: ["Shoulder_Rotation", "Shoulder_Pitch", "Elbow", "Wrist_Roll", "Wrist_Pitch"], points: [{positions: [1.0, 1.0, 1.0, 1.0, 1.0], velocities: [], accelerations: [], effort: [], time_from_start: {sec: 1, nanosec: 0}}]}'
```

### Test Gripper Control

The gripper can be controlled using ROS2 actions:

```bash
# Open gripper (full open position)
ros2 action send_goal /gripper_controller/gripper_cmd control_msgs/action/GripperCommand "{command: {position: 1.57, max_effort: 50.0}}"

# Close gripper
ros2 action send_goal /gripper_controller/gripper_cmd control_msgs/action/GripperCommand "{command: {position: 0.0, max_effort: 50.0}}"

# Half-open position
ros2 action send_goal /gripper_controller/gripper_cmd control_msgs/action/GripperCommand "{command: {position: 0.5, max_effort: 50.0}}"
```

Monitor gripper state:

```bash
ros2 topic echo /gripper_controller/state
```

Note: The gripper position ranges from 0.0 (closed) to 0.085 (fully open). The max_effort parameter controls the gripping force.

## Demonstrations

### Gazebo Simulation

[![SO-100 Robot Arm Simulation](https://img.youtube.com/vi/ATuS6rOhYvI/0.jpg)](https://youtu.be/ATuS6rOhYvI?si=T6bOiCdqgBmSoSCu)

The video above shows the SO-100 robot arm in Gazebo Harmonic simulation:

- Joint trajectory execution
- Position control
- Dynamic simulation with gravity

## Package Structure

```bash
so_arm_100/
├── CMakeLists.txt                      # Build system configuration
├── config/  
│   ├── controllers_5dof.yaml           # 5DOF joint controller configuration
│   ├── initial_positions.yaml          # Default joint positions
│   ├── joint_limits.yaml               # Joint velocity and position limits
│   ├── kinematics.yaml                 # MoveIt kinematics configuration
│   ├── moveit_controllers.yaml         # MoveIt controller settings
│   ├── moveit.rviz                     # RViz configuration for MoveIt
│   ├── pilz_cartesian_limits.yaml      # Cartesian planning limits
│   ├── ros2_controllers.yaml           # ROS2 controller settings
│   ├── sensors_3d.yaml                 # Sensor configuration
│   ├── so_arm_100.ros2_control.xacro   # ROS2 Control macro
│   ├── so_arm_100.srdf                 # Semantic robot description
│   ├── so_arm_100.urdf.xacro           # Main robot description macro
│   └── urdf.rviz                       # RViz configuration for URDF
├── launch/  
│   ├── demo.launch.py                  # MoveIt demo with RViz
│   ├── gz.launch.py                    # Gazebo simulation launch
│   ├── move_group.launch.py            # MoveIt move_group launch
│   ├── moveit_rviz.launch.py           # RViz with MoveIt plugin
│   ├── rsp.launch.py                   # Robot state publisher
│   ├── rviz.launch.py                  # Basic RViz visualization
│   ├── setup_assistant.launch.py       # MoveIt Setup Assistant
│   ├── spawn_controllers.launch.py     # Controller spawning
│   ├── static_virtual_joint_tfs.launch.py
│   └── warehouse_db.launch.py          # MoveIt warehouse database
├── LICENSE
├── models/
│   ├── so_arm_100_5dof/                # 5DOF robot assets
│   │   ├── meshes/                     # STL files for visualization
│   │   └── model.config                # Model metadata
├── package.xml                         # Package metadata and dependencies
├── README.md                           # This documentation
└── urdf/
    ├── so_arm_100_5dof.csv             # Joint configuration data
    ├── so_arm_100_5dof.urdf            # 5DOF robot description

```

## Joint Configuration

### 5-DOF Configuration

1. Shoulder Rotation (-3.14 to 3.14 rad)
2. Shoulder Pitch    (-3.14 to 3.14 rad)
3. Elbow            (-3.14 to 3.14 rad)
4. Wrist Pitch      (-3.14 to 3.14 rad)
5. Wrist Roll       (-3.14 to 3.14 rad)

Note: The 5-DOF configuration uses continuous rotation joints with full range of motion (±π radians).

## Known Issues

- The MoveIt2 configuration is still in development
- Some joint limits may need fine-tuning
- Collision checking needs optimization

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License - see the LICENSE file for details

## Authors

Bruk G.

## Acknowledgments

- Based on the SO-ARM100 project by The Robot Studio
