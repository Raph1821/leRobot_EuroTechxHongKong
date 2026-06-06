#!/bin/bash
# Install ROS2 Humble on Ubuntu 22.04

set -e

echo "========================================="
echo "Installing ROS2 Humble on Ubuntu 22.04"
echo "========================================="
echo ""

# Add ROS2 repository
echo "Step 1/6: Adding ROS2 repository..."
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Update package list
echo "Step 2/6: Updating package list..."
sudo apt update

# Install ROS2 Humble Desktop
echo "Step 3/6: Installing ROS2 Humble Desktop (10-15 minutes)..."
sudo apt install -y ros-humble-desktop

# Install development tools
echo "Step 4/6: Installing build tools..."
sudo apt install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool

# Install additional ROS2 packages
echo "Step 5/6: Installing additional ROS2 packages..."
sudo apt install -y \
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
    ros-humble-control-msgs \
    ros-humble-moveit-msgs \
    ros-humble-warehouse-ros \
    ros-humble-pilz-industrial-motion-planner

# Initialize rosdep
echo "Step 6/6: Initializing rosdep..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init
fi
rosdep update

# Setup environment
echo ""
echo "Setting up environment in ~/.bashrc..."
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ROS2 Humble" >> ~/.bashrc
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi

echo ""
echo "========================================="
echo "ROS2 Humble Installation Complete!"
echo "========================================="
echo ""
echo "Run: source ~/.bashrc"
echo ""
