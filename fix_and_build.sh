#!/bin/bash
# Fix compatibility issues and build workspace for ROS2 Foxy
# This installs all missing dependencies and builds all packages

set -e

echo "========================================="
echo "Installing Missing Dependencies & Building"
echo "========================================="
echo ""

# Source ROS2
source /opt/ros/foxy/setup.bash

# Navigate to workspace
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"

# Install missing ROS2 packages
echo "Installing missing ROS2 packages..."
sudo apt update
sudo apt install -y \
    ros-foxy-control-msgs \
    ros-foxy-moveit-msgs \
    ros-foxy-moveit-ros-planning \
    ros-foxy-moveit-ros-planning-interface \
    ros-foxy-moveit-servo \
    ros-foxy-pilz-industrial-motion-planner \
    ros-foxy-warehouse-ros \
    ros-foxy-rqt-joint-trajectory-controller \
    ros-foxy-rqt-controller-manager \
    python3-pytest-rerunfailures

# Use rosdep to install all dependencies
echo ""
echo "Installing workspace dependencies with rosdep..."
rosdep update
rosdep install --from-paths . --ignore-src -r -y || true

# Clean old build
echo ""
echo "Cleaning old build artifacts..."
rm -rf build install log

# Build workspace
echo ""
echo "Building workspace (this may take 10-20 minutes)..."
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release --event-handlers console_direct+

echo ""
echo "========================================="
echo "Build Complete!"
echo "========================================="
echo ""
echo "Source the workspace:"
echo "  source install/setup.bash"
echo ""
echo "Test with:"
echo "  ros2 launch so101_bringup follower.launch.py hardware_type:=mock"
echo ""
