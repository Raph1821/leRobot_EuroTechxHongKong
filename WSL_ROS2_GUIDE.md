# WSL2 + ROS2 Setup Guide

## Quick Start

### Option 1: Automated Setup (Recommended)

Simply run the setup script:

```batch
setup_wsl.bat
```

This will automatically:
- Install ROS2 Foxy in WSL Ubuntu
- Install all dependencies (xacro, MoveIt, Gazebo, etc.)
- Build the entire workspace
- Configure your environment

**Time required:** 20-30 minutes (mostly automated)

### Option 2: Manual Setup

If you prefer to run commands manually:

1. **Open WSL Ubuntu:**
   ```batch
   wsl -d Ubuntu
   ```

2. **Navigate to the workspace:**
   ```bash
   cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
   ```

3. **Run the setup script:**
   ```bash
   chmod +x setup_wsl_ros2.sh
   ./setup_wsl_ros2.sh
   ```

---

## After Installation

### Opening WSL Terminal

From Windows:
```batch
wsl -d Ubuntu
```

Or open "Ubuntu" from the Start Menu.

### Testing ROS2

```bash
# Check ROS2 version
ros2 --version

# List available packages
ros2 pkg list | grep so101

# Test if workspace is sourced
ros2 pkg prefix so101_bringup
```

---

## Testing Launch Files (Mock Mode)

Once setup is complete, you can test all launch files without hardware:

### SO-101 Robot

```bash
# Single follower arm with mock hardware
ros2 launch so101_bringup follower.launch.py hardware_type:=mock

# Teleoperation (leader + follower) with mock hardware, no cameras
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false

# Just URDF visualization
ros2 launch so101_description display.launch.py

# Inference with mock hardware (no cameras)
ros2 launch so101_bringup inference.launch.py hardware_type:=mock use_inference:=false

# MoveIt demo
ros2 launch so101_moveit_config demo.launch.py
```

### SO-ARM-100 Robot

```bash
# Fake hardware with RViz
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=true

# Gazebo simulation
ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=gazebo

# Interactive joint control GUI
ros2 launch so_arm_100_description joint_state_pub_gui.launch.py

# MoveIt demo
ros2 launch so_arm_100_moveit_config demo.launch.py
```

---

## File Access

### Accessing Windows files from WSL:
Windows C:\ drive is mounted at `/mnt/c/`

Your workspace is at:
```
/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong
```

### Accessing WSL files from Windows:
In Windows Explorer, navigate to:
```
\\wsl$\Ubuntu\home\<your-username>\
```

---

## Useful Commands

### ROS2 Basics

```bash
# Source ROS2 (if not in .bashrc)
source /opt/ros/foxy/setup.bash

# Source workspace
source install/setup.bash

# List all nodes
ros2 node list

# List all topics
ros2 topic list

# Echo a topic
ros2 topic echo /joint_states

# Check node info
ros2 node info /robot_state_publisher
```

### Building & Development

```bash
# Build all packages
colcon build --symlink-install

# Build specific package
colcon build --packages-select so101_bringup

# Build with verbose output
colcon build --event-handlers console_direct+

# Clean build
rm -rf build install log
colcon build --symlink-install
```

### Workspace Management

```bash
# Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# Update rosdep
rosdep update

# Check for missing dependencies
rosdep check --from-paths src --ignore-src
```

---

## Viewing RViz & Gazebo (GUI)

To use graphical applications (RViz, Gazebo) from WSL, you need an X server on Windows.

### Option 1: VcXsrv (Recommended)

1. **Download and install VcXsrv:**
   https://sourceforge.net/projects/vcxsrv/

2. **Launch XLaunch:**
   - Display: 0
   - Multiple windows
   - Start no client
   - **Check:** Disable access control

3. **In WSL, set DISPLAY:**
   ```bash
   export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
   ```

4. **Add to ~/.bashrc for persistence:**
   ```bash
   echo 'export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '\''{print $2}'\''):0' >> ~/.bashrc
   ```

### Option 2: WSLg (Windows 11 only)

If you're on Windows 11 with WSLg, GUI apps should work out of the box.

---

## Troubleshooting

### "Package not found" errors
```bash
source /opt/ros/foxy/setup.bash
source install/setup.bash
```

### Build errors
```bash
# Clean and rebuild
rm -rf build install log
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

### Permission denied
```bash
chmod +x <script-name>
```

### Python import errors
```bash
pip3 install --upgrade <package-name>
```

---

## Comparison: WSL vs Windows Native ROS2

| Aspect | WSL2 + Ubuntu | Windows Native |
|--------|---------------|----------------|
| Setup complexity | Easy | Very difficult |
| Package availability | Excellent | Limited |
| Performance | Native-like | Native |
| Stability | Very stable | Can be unstable |
| Community support | Excellent | Limited |
| GUI support | Requires X server (or WSLg) | Native |

**Recommendation:** Use WSL2 for ROS2 development. It's much more reliable and has better package support.

---

## Next Steps

After successful setup:

1. Test the mock launch files
2. Explore the codebase
3. Run the AI modules (Python scripts work in both Windows and WSL)
4. Test the web interface

Good luck with your robotics project! 🤖
