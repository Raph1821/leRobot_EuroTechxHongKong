#!/bin/bash
# Verify ROS2 Humble installation and workspace build status

echo "========================================="
echo "ROS2 Setup Verification"
echo "========================================="
echo ""

# Check Ubuntu version
echo "Ubuntu Version:"
lsb_release -d
echo ""

# Check ROS2 installations
echo "ROS2 Installations:"
if [ -d /opt/ros/humble ]; then
    echo "  ✓ ROS2 Humble - INSTALLED"
else
    echo "  ✗ ROS2 Humble - NOT INSTALLED"
fi

if [ -d /opt/ros/foxy ]; then
    echo "  ✓ ROS2 Foxy - INSTALLED (old, can be removed)"
fi
echo ""

# Check workspace
WORKSPACE="/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
echo "Workspace: $WORKSPACE"

if [ -d "$WORKSPACE/install" ]; then
    echo "  ✓ Workspace BUILT"
    
    # Source and check packages
    source /opt/ros/humble/setup.bash 2>/dev/null || source /opt/ros/foxy/setup.bash 2>/dev/null
    source "$WORKSPACE/install/setup.bash" 2>/dev/null
    
    echo ""
    echo "Built packages:"
    ros2 pkg list 2>/dev/null | grep -E "^(so101|so_arm_100|episode)" | sort
else
    echo "  ✗ Workspace NOT BUILT"
fi

echo ""
echo "========================================="
echo "Next Steps:"
echo "========================================="

if [ ! -d /opt/ros/humble ]; then
    echo "1. Install ROS2 Humble:"
    echo "   ./install_humble.sh"
    echo ""
fi

if [ ! -d "$WORKSPACE/install" ]; then
    echo "2. Build workspace:"
    echo "   ./complete_build.sh"
    echo ""
fi

if [ -d /opt/ros/humble ] && [ -d "$WORKSPACE/install" ]; then
    echo "✓ All set! Test with:"
    echo "  source ~/.bashrc"
    echo "  source install/setup.bash"
    echo "  ros2 launch so101_bringup follower.launch.py hardware_type:=mock"
fi

echo ""
