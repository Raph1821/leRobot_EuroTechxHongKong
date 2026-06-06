#!/bin/bash
# ROS2 Foxy Setup Script for Ubuntu 20.04 in WSL2
# This script will install ROS2 Foxy and build the workspace

set -e  # Exit on error

echo "========================================="
echo "ROS2 Foxy Setup for Ubuntu 20.04 WSL2"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Step 1: Update system
print_step "Updating system packages..."
sudo apt update
sudo apt upgrade -y
print_success "System updated"

# Step 2: Install prerequisites
print_step "Installing prerequisites..."
sudo apt install -y \
    software-properties-common \
    curl \
    gnupg2 \
    lsb-release \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-rosdep \
    python3-colcon-common-extensions \
    python3-vcstool
print_success "Prerequisites installed"

# Step 3: Add ROS2 repository
print_step "Adding ROS2 repository..."
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
print_success "ROS2 repository added"

# Step 4: Install ROS2 Foxy Desktop
print_step "Installing ROS2 Foxy Desktop (this may take 10-15 minutes)..."
sudo apt install -y ros-foxy-desktop
print_success "ROS2 Foxy installed"

# Step 5: Install additional ROS2 packages
print_step "Installing additional ROS2 packages..."
sudo apt install -y \
    ros-foxy-xacro \
    ros-foxy-joint-state-publisher \
    ros-foxy-joint-state-publisher-gui \
    ros-foxy-robot-state-publisher \
    ros-foxy-rviz2 \
    ros-foxy-gazebo-ros-pkgs \
    ros-foxy-ros2-control \
    ros-foxy-ros2-controllers \
    ros-foxy-moveit \
    ros-foxy-moveit-resources \
    python3-pytest
print_success "Additional packages installed"

# Step 6: Initialize rosdep
print_step "Initializing rosdep..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init
fi
rosdep update
print_success "rosdep initialized"

# Step 7: Setup environment in bashrc
print_step "Setting up ROS2 environment in ~/.bashrc..."
if ! grep -q "source /opt/ros/foxy/setup.bash" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ROS2 Foxy setup" >> ~/.bashrc
    echo "source /opt/ros/foxy/setup.bash" >> ~/.bashrc
    echo 'export ROS_DOMAIN_ID=0' >> ~/.bashrc
    echo 'export ROS_LOCALHOST_ONLY=1' >> ~/.bashrc
fi
print_success "Environment configured"

# Step 8: Source ROS2 for current session
source /opt/ros/foxy/setup.bash

# Step 9: Navigate to workspace and install Python dependencies
print_step "Installing Python dependencies..."
cd /mnt/c/Users/croqu/Downloads/git_minh/Nouveau\ dossier/leRobot_EuroTechxHongKong

if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
    print_success "Python dependencies installed"
else
    echo "No requirements.txt found, skipping..."
fi

# Step 10: Install workspace dependencies with rosdep
print_step "Installing workspace dependencies..."
rosdep install --from-paths . --ignore-src -r -y || true
print_success "Workspace dependencies installed"

# Step 11: Build the workspace
print_step "Building ROS2 workspace (this may take 10-20 minutes)..."
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
print_success "Workspace built successfully!"

# Step 12: Setup workspace in bashrc
print_step "Adding workspace to ~/.bashrc..."
WORKSPACE_PATH="/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
if ! grep -q "source.*install/setup.bash" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Workspace setup" >> ~/.bashrc
    echo "cd \"$WORKSPACE_PATH\"" >> ~/.bashrc
    echo "source install/setup.bash" >> ~/.bashrc
fi
print_success "Workspace configured"

echo ""
echo "========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================="
echo ""
echo "To use ROS2, either:"
echo "  1. Close and reopen your WSL terminal"
echo "  2. Or run: source ~/.bashrc"
echo ""
echo "Test commands:"
echo "  ros2 --version"
echo "  ros2 launch so101_bringup follower.launch.py hardware_type:=mock"
echo "  ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false"
echo ""
