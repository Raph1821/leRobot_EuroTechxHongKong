#!/bin/bash
# Manual ROS2 Foxy Installation for Ubuntu 20.04
# Run this step-by-step in WSL Ubuntu terminal

set -e

echo "========================================="
echo "ROS2 Foxy Manual Installation"
echo "========================================="
echo ""

# Step 1: Update and install prerequisites
echo "Step 1/10: Installing prerequisites..."
sudo apt update
export DEBIAN_FRONTEND=noninteractive
sudo apt install -y software-properties-common curl gnupg2 lsb-release build-essential cmake git python3-pip

# Step 2: Add ROS2 repository
echo "Step 2/10: Adding ROS2 repository..."
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Step 3: Update after adding repo
echo "Step 3/10: Updating package list..."
sudo apt update

# Step 4: Install ROS2 Foxy Desktop
echo "Step 4/10: Installing ROS2 Foxy Desktop (this will take 10-15 minutes)..."
sudo apt install -y ros-foxy-desktop

# Step 5: Install development tools
echo "Step 5/10: Installing development tools..."
sudo apt install -y python3-colcon-common-extensions python3-rosdep python3-vcstool

# Step 6: Install additional ROS2 packages
echo "Step 6/10: Installing additional ROS2 packages..."
sudo apt install -y \
    ros-foxy-xacro \
    ros-foxy-joint-state-publisher \
    ros-foxy-joint-state-publisher-gui \
    ros-foxy-robot-state-publisher \
    ros-foxy-rviz2 \
    ros-foxy-gazebo-ros-pkgs \
    ros-foxy-ros2-control \
    ros-foxy-ros2-controllers \
    ros-foxy-controller-manager \
    ros-foxy-moveit \
    ros-foxy-moveit-ros-planning-interface \
    python3-pytest

# Step 7: Initialize rosdep
echo "Step 7/10: Initializing rosdep..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init
fi
rosdep update

# Step 8: Source ROS2
echo "Step 8/10: Sourcing ROS2..."
source /opt/ros/foxy/setup.bash

# Step 9: Navigate to workspace and install dependencies
echo "Step 9/10: Installing workspace dependencies..."
cd /mnt/c/Users/croqu/Downloads/git_minh/Nouveau\ dossier/leRobot_EuroTechxHongKong
rosdep install --from-paths . --ignore-src -r -y || true

# Step 10: Build workspace
echo "Step 10/10: Building workspace..."
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Add to bashrc
echo ""
echo "Adding ROS2 to ~/.bashrc..."
if ! grep -q "source /opt/ros/foxy/setup.bash" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ROS2 Foxy" >> ~/.bashrc
    echo "source /opt/ros/foxy/setup.bash" >> ~/.bashrc
    echo 'export ROS_DOMAIN_ID=0' >> ~/.bashrc
    echo 'export ROS_LOCALHOST_ONLY=1' >> ~/.bashrc
fi

WORKSPACE_PATH="/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
if ! grep -q "$WORKSPACE_PATH" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Workspace" >> ~/.bashrc
    echo "cd \"$WORKSPACE_PATH\"" >> ~/.bashrc
    echo "source install/setup.bash" >> ~/.bashrc
fi

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Run: source ~/.bashrc"
echo "Or close and reopen your terminal"
echo ""
echo "Test with: ros2 --version"
echo ""
