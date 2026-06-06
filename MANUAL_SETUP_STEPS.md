# Manual ROS2 Setup in WSL2 - Step by Step

Since the automated setup may have issues with interactive prompts, follow these manual steps.

## Step 1: Open WSL Ubuntu Terminal

From Windows Command Prompt or PowerShell:
```batch
wsl -d Ubuntu
```

Or click "Ubuntu" from the Start Menu.

---

## Step 2: Navigate to Workspace

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
```

---

## Step 3: Run the Installation Script

```bash
chmod +x install_ros2_manual.sh
./install_ros2_manual.sh
```

**This will take 20-30 minutes.** It will:
- Install ROS2 Foxy
- Install all dependencies
- Build the workspace

**You'll be asked for your Ubuntu password at the beginning.**

---

## Step 4: After Installation, Reload Your Shell

```bash
source ~/.bashrc
```

Or close and reopen the Ubuntu terminal.

---

## Step 5: Verify Installation

```bash
chmod +x test_ros2_packages.sh
./test_ros2_packages.sh
```

This will test all packages and show you what's working.

---

## Step 6: Test Launch Files (Mock Mode)

Once verification passes, try these commands:

### SO-101 Tests

```bash
# Single follower arm (mock hardware)
ros2 launch so101_bringup follower.launch.py hardware_type:=mock

# Press Ctrl+C to stop, then try:

# Teleoperation (no cameras)
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false

# URDF visualization
ros2 launch so101_description display.launch.py

# MoveIt demo
ros2 launch so101_moveit_config demo.launch.py
```

### SO-ARM-100 Tests

```bash
# Fake hardware
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=false

# Interactive joint control
ros2 launch so_arm_100_description joint_state_pub_gui.launch.py

# MoveIt demo
ros2 launch so_arm_100_moveit_config demo.launch.py
```

---

## Troubleshooting

### If ROS2 installation fails:

```bash
# Update package lists
sudo apt update

# Try installing ROS2 manually
sudo apt install -y ros-foxy-desktop

# Install build tools
sudo apt install -y python3-colcon-common-extensions python3-rosdep
```

### If workspace build fails:

```bash
# Clean previous build
rm -rf build install log

# Install dependencies
source /opt/ros/foxy/setup.bash
rosdep update
rosdep install --from-paths . --ignore-src -r -y

# Rebuild
colcon build --symlink-install
```

### If packages are not found:

```bash
# Make sure ROS2 and workspace are sourced
source /opt/ros/foxy/setup.bash
source install/setup.bash

# Verify packages
ros2 pkg list | grep so101
```

### If launch file fails:

```bash
# Check if package is built
ros2 pkg prefix so101_bringup

# List available launch files
ros2 launch so101_bringup <TAB><TAB>

# Check for error messages and missing dependencies
```

---

## Expected Success Output

When `test_ros2_packages.sh` runs successfully, you should see:

```
✓ ROS2 Foxy sourced
✓ Workspace sourced

--- Core ROS2 Tests ---
✓ ROS2 CLI available
✓ ros2 node command
✓ ros2 topic command
✓ ros2 launch command

--- ROS2 Package Tests ---
✓ xacro installed
✓ robot_state_publisher
✓ joint_state_publisher
✓ rviz2 installed
✓ gazebo_ros installed
✓ controller_manager
✓ moveit installed

--- Workspace Package Tests ---
✓ so101_description
✓ so101_bringup
✓ so101_moveit_config
... (all packages pass)

Passed: 25
Failed: 0

All tests passed! ✓
```

---

## Quick Commands Reference

### Essential Commands

```bash
# Source ROS2 (if not automatic)
source /opt/ros/foxy/setup.bash

# Source workspace
source install/setup.bash

# List all ROS2 packages
ros2 pkg list

# Find workspace packages
ros2 pkg list | grep -E "so101|so_arm|episode"

# Check package location
ros2 pkg prefix so101_bringup

# List launch files in a package
ros2 launch so101_bringup <TAB><TAB>
```

### Build Commands

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

### Debugging Commands

```bash
# Check running nodes
ros2 node list

# Check active topics
ros2 topic list

# Echo a topic
ros2 topic echo /joint_states

# Get node info
ros2 node info /robot_state_publisher

# Check service list
ros2 service list
```

---

## What to Do If Something Fails

1. **Read the error message carefully** - it usually tells you what's missing

2. **Check if ROS2 is sourced:**
   ```bash
   echo $ROS_DISTRO
   # Should output: foxy
   ```

3. **Check if workspace is sourced:**
   ```bash
   ros2 pkg list | grep so101
   # Should show so101_* packages
   ```

4. **Rebuild if needed:**
   ```bash
   source /opt/ros/foxy/setup.bash
   colcon build --symlink-install
   source install/setup.bash
   ```

5. **Check the test script:**
   ```bash
   ./test_ros2_packages.sh
   ```

---

## Next Steps After Successful Setup

1. ✅ Test all mock launch files
2. ✅ Explore the codebase
3. ✅ Run Python AI modules (work in both WSL and Windows)
4. ✅ Set up X server (VcXsrv) for RViz/Gazebo GUI if needed
5. ✅ Connect real hardware when ready

---

## Files Reference

- `install_ros2_manual.sh` - Installation script
- `test_ros2_packages.sh` - Verification script  
- `MANUAL_SETUP_STEPS.md` - This guide
- `WSL_ROS2_GUIDE.md` - Comprehensive reference

---

## Quick Start (TL;DR)

```bash
wsl -d Ubuntu
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
chmod +x install_ros2_manual.sh test_ros2_packages.sh
./install_ros2_manual.sh
source ~/.bashrc
./test_ros2_packages.sh
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

Good luck! 🚀
