# 🚀 Run These Commands in WSL Ubuntu

## Current Status
- ✅ Ubuntu 22.04.5 LTS installed
- ❌ ROS2 Humble NOT installed (only old Foxy)
- ⚠️ Only 5 packages built (with Foxy, not complete)

## You Need To Do (3 Simple Steps)

### Step 1: Open WSL Ubuntu Terminal

From Windows:
```batch
wsl -d Ubuntu
```

Or click "Ubuntu" in Start Menu.

---

### Step 2: Navigate to Workspace

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
```

---

### Step 3: Run the Scripts (In Order)

#### A) Install ROS2 Humble (10-15 minutes)

```bash
./install_humble.sh
```

**What it does:**
- Adds ROS2 repository
- Installs ROS2 Humble Desktop
- Installs all required packages (xacro, MoveIt, Gazebo, ros2_control, etc.)
- Configures environment

**You'll need to enter your password once at the start.**

---

#### B) Verify Installation

```bash
source ~/.bashrc
./verify_setup.sh
```

**Should show:**
- ✓ ROS2 Humble - INSTALLED

---

#### C) Build ALL Packages (10-20 minutes)

```bash
./complete_build.sh
```

**What it does:**
- Cleans old Foxy build artifacts
- Installs workspace dependencies
- Builds ALL 15 packages with ROS2 Humble
- No packages skipped!

---

#### D) Verify Build

```bash
./verify_setup.sh
```

**Should show all packages:**
- so101_description
- so101_bringup
- so101_kinematics
- so101_kinematics_msgs
- so101_moveit_config
- so101_teleop
- so101_inference
- so101_camera_calibration
- so_arm_100_description
- so_arm_100_bringup
- so_arm_100_moveit_config
- so_arm_100_isaac_sim
- so_arm_100_web_bridge
- episode_recorder
- so_arm_100 (meta package)

---

### Step 4: Test Launch Files

```bash
# Source the workspace
source ~/.bashrc
source install/setup.bash

# Test SO-101 follower (mock mode, no hardware)
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

**Press Ctrl+C to stop.**

Try other launch files:

```bash
# Teleoperation (mock, no cameras)
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false

# URDF display
ros2 launch so101_description display.launch.py

# MoveIt demo
ros2 launch so101_moveit_config demo.launch.py

# SO-ARM-100 fake hardware
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=false

# SO-ARM-100 MoveIt
ros2 launch so_arm_100_moveit_config demo.launch.py
```

---

## Quick Copy-Paste (All Commands)

If you want to run everything at once:

```bash
# Open WSL and run:
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"

# Step 1: Install ROS2 Humble
./install_humble.sh

# Step 2: Verify
source ~/.bashrc
./verify_setup.sh

# Step 3: Build workspace
./complete_build.sh

# Step 4: Verify build
./verify_setup.sh

# Step 5: Test
source install/setup.bash
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

---

## Troubleshooting

### If install_humble.sh fails:

Check internet connection and try again:
```bash
sudo apt update
./install_humble.sh
```

### If complete_build.sh fails:

Check the error message. Common issues:

**Missing dependencies:**
```bash
source /opt/ros/humble/setup.bash
rosdep update
rosdep install --from-paths . --ignore-src -r -y
./complete_build.sh
```

**CMake errors:**
```bash
rm -rf build install log
./complete_build.sh
```

### If packages are missing after build:

```bash
./verify_setup.sh
# Lists what's built

source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 pkg list | grep -E "^(so101|so_arm)"
# Shows all workspace packages
```

---

## Expected Timeline

| Step | Time |
|------|------|
| Install ROS2 Humble | 10-15 min |
| Build workspace | 10-20 min |
| **Total** | **20-35 min** |

---

## Files Created

All scripts are in your workspace:

| Script | Purpose |
|--------|---------|
| `install_humble.sh` | Install ROS2 Humble |
| `complete_build.sh` | Build all packages |
| `verify_setup.sh` | Check status |
| `RUN_THESE_COMMANDS.md` | This file |

---

## After Success

You'll have:
- ✅ Ubuntu 22.04 LTS
- ✅ ROS2 Humble Desktop
- ✅ **ALL 15 packages built**
- ✅ All 42 launch files working
- ✅ No packages skipped
- ✅ Full mock/simulation support

---

## Ready?

**Just run these 3 commands in WSL:**

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
./install_humble.sh
./complete_build.sh
```

That's it! 🎉
