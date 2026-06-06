# Complete ROS2 Setup - Manual Steps (No Package Skipping)

## Current Situation

- Ubuntu 20.04 is installed in WSL
- ROS2 Foxy is installed
- Some packages are failing due to missing dependencies and API differences

## Best Solution: Upgrade to Ubuntu 22.04 + ROS2 Humble

ROS2 Humble has all the features your packages need. Here's how to upgrade:

---

## OPTION 1: Upgrade to Ubuntu 22.04 (Recommended)

### Step 1: Open WSL Ubuntu Terminal

```batch
wsl -d Ubuntu
```

### Step 2: Upgrade Ubuntu 20.04 → 22.04

```bash
# Update current packages
sudo apt update
sudo apt upgrade -y
sudo apt dist-upgrade -y

# Install upgrade tool
sudo apt install -y update-manager-core

# Configure for LTS upgrades
sudo sed -i 's/Prompt=.*/Prompt=lts/' /etc/update-manager/release-upgrades

# Start upgrade (this takes 30-60 minutes)
sudo do-release-upgrade
```

**Follow the prompts:**
- Press Enter to accept defaults
- Say "y" to continue
- Reboot when asked

### Step 3: After Upgrade, Verify

```bash
lsb_release -a
# Should show: Ubuntu 22.04
```

### Step 4: Install ROS2 Humble

```bash
# Add ROS2 repository
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble Desktop
sudo apt update
sudo apt install -y ros-humble-desktop

# Install development tools
sudo apt install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    ros-humble-xacro \
    ros-humble-joint-state-publisher \
    ros-humble-joint-state-publisher-gui \
    ros-humble-robot-state-publisher \
    ros-humble-rviz2 \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-controller-manager \
    ros-humble-moveit \
    ros-humble-moveit-ros-planning-interface \
    ros-humble-control-msgs

# Initialize rosdep
sudo rosdep init
rosdep update

# Setup environment
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### Step 5: Build Workspace

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"

# Clean old build
rm -rf build install log

# Install dependencies
rosdep install --from-paths . --ignore-src -r -y

# Build
colcon build --symlink-install
```

### Step 6: Source and Test

```bash
source install/setup.bash

# Test
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

---

## OPTION 2: Fix Foxy Issues (More Complex)

If you can't upgrade Ubuntu, here's how to fix the issues:

### Step 1: Install Missing Packages

```bash
sudo apt update
sudo apt install -y \
    ros-foxy-control-msgs \
    ros-foxy-moveit \
    ros-foxy-moveit-ros-planning-interface
```

### Step 2: Fix episode_recorder

The `episode_recorder` package uses `generic_subscription` which doesn't exist in Foxy.

Edit: `episode_recorder/include/episode_recorder/episode_recorder.hpp`

Change:
```cpp
#include "rclcpp/generic_subscription.hpp"
```

To:
```cpp
#include "rclcpp/subscription.hpp"
```

Then modify the code to use regular subscriptions instead of generic ones.

### Step 3: Fix so101_teleop

Make sure control_msgs is installed:
```bash
sudo apt install -y ros-foxy-control-msgs
```

### Step 4: Build

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
rm -rf build install log
source /opt/ros/foxy/setup.bash
colcon build --symlink-install
```

---

## OPTION 3: Use Fresh Ubuntu 22.04 WSL Instance

### Step 1: Check Available Instances

```batch
wsl --list
```

### Step 2: Use the New Ubuntu (if installed)

The latest `wsl --install Ubuntu` should have created Ubuntu 22.04 or 24.04.

```batch
wsl -d Ubuntu-22.04
```

Or check the exact name:
```batch
wsl --list --verbose
```

### Step 3: Set as Default

```batch
wsl --set-default Ubuntu-22.04
```

### Step 4: Install ROS2 Humble

Follow "Option 1, Step 4" above.

---

## Recommended Approach

**I strongly recommend OPTION 1** (Upgrade to Ubuntu 22.04 + ROS2 Humble) because:

✅ All your packages are designed for ROS2 Humble  
✅ No code modifications needed  
✅ Better long-term support  
✅ More features and bug fixes  
✅ Easier to maintain  

The upgrade takes 30-60 minutes but saves you from compatibility headaches.

---

## After Successful Build

Test all launch files:

```bash
# Source workspace
source /opt/ros/humble/setup.bash  # or /opt/ros/foxy/setup.bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
source install/setup.bash

# SO-101 tests
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false
ros2 launch so101_description display.launch.py
ros2 launch so101_moveit_config demo.launch.py

# SO-ARM-100 tests
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=false
ros2 launch so_arm_100_description joint_state_pub_gui.launch.py
ros2 launch so_arm_100_moveit_config demo.launch.py
```

---

## Quick Commands for Option 1 (Copy-Paste)

```bash
# In WSL Ubuntu terminal:

# 1. Upgrade to Ubuntu 22.04
sudo apt update && sudo apt upgrade -y && sudo apt dist-upgrade -y
sudo apt install -y update-manager-core
sudo sed -i 's/Prompt=.*/Prompt=lts/' /etc/update-manager/release-upgrades
sudo do-release-upgrade

# 2. After reboot, install ROS2 Humble
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep ros-humble-xacro ros-humble-joint-state-publisher ros-humble-robot-state-publisher ros-humble-rviz2 ros-humble-gazebo-ros-pkgs ros-humble-ros2-control ros-humble-ros2-controllers ros-humble-moveit ros-humble-control-msgs
sudo rosdep init
rosdep update
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 3. Build workspace
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
rm -rf build install log
rosdep install --from-paths . --ignore-src -r -y
colcon build --symlink-install

# 4. Test
source install/setup.bash
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

---

## What I Recommend You Do NOW

1. **Upgrade to Ubuntu 22.04** - This solves all compatibility issues
2. **Install ROS2 Humble** - Has all the features you need
3. **Build the workspace** - Everything should work out of the box

The entire process takes about 1 hour but you'll have a fully working system with no package skipping.

**Ready to upgrade?** Run the commands in "Option 1" above!
