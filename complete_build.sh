#!/bin/bash
# Complete build script for ROS2 Humble workspace
# Run this after ROS2 Humble is installed

set -e

echo "========================================="
echo "Building ROS2 Workspace with ALL Packages"
echo "========================================="
echo ""

# Check if ROS2 Humble is installed
if [ ! -d /opt/ros/humble ]; then
    echo "ERROR: ROS2 Humble not installed!"
    echo "Please run: ./install_humble.sh first"
    exit 1
fi

# Source ROS2 Humble
echo "Sourcing ROS2 Humble..."
source /opt/ros/humble/setup.bash

# Navigate to workspace
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"

# Clean old build artifacts
echo ""
echo "Cleaning old build artifacts..."
rm -rf build install log

# Install workspace dependencies
echo ""
echo "Installing workspace dependencies..."
rosdep update
rosdep install --from-paths . --ignore-src -r -y

# Build workspace with all packages
echo ""
echo "Building workspace (10-20 minutes)..."
echo "Building with Release mode for better performance..."
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Verify build
echo ""
echo "========================================="
echo "Build Complete!"
echo "========================================="
echo ""
echo "Verifying packages..."
source install/setup.bash

# Count built packages
PACKAGE_COUNT=$(ros2 pkg list | grep -E "^(so101|so_arm_100|episode)" | wc -l)
echo "Built $PACKAGE_COUNT workspace packages"

echo ""
echo "Package list:"
ros2 pkg list | grep -E "^(so101|so_arm_100|episode)" | sort

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "To use the workspace, run:"
echo "  source ~/.bashrc"
echo "  source install/setup.bash"
echo ""
echo "Test commands:"
echo "  ros2 launch so101_bringup follower.launch.py hardware_type:=mock"
echo "  ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false"
echo "  ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true"
echo ""
