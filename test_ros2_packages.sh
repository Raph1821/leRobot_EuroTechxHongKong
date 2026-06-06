#!/bin/bash
# Test ROS2 Installation and Packages
# Run this after ROS2 is installed

echo "========================================="
echo "ROS2 Package Verification Test"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

test_command() {
    local description="$1"
    local command="$2"
    
    echo -n "Testing: $description... "
    if eval "$command" &> /dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((pass_count++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((fail_count++))
    fi
}

# Source ROS2
if [ -f /opt/ros/foxy/setup.bash ]; then
    source /opt/ros/foxy/setup.bash
    echo -e "${GREEN}✓ ROS2 Foxy sourced${NC}"
else
    echo -e "${RED}✗ ROS2 Foxy not installed${NC}"
    exit 1
fi

# Source workspace if built
WORKSPACE_PATH="/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
cd "$WORKSPACE_PATH"
if [ -f install/setup.bash ]; then
    source install/setup.bash
    echo -e "${GREEN}✓ Workspace sourced${NC}"
else
    echo -e "${YELLOW}⚠ Workspace not built yet${NC}"
fi

echo ""
echo "--- Core ROS2 Tests ---"
test_command "ROS2 CLI available" "ros2 --help"
test_command "ros2 node command" "ros2 node --help"
test_command "ros2 topic command" "ros2 topic --help"
test_command "ros2 launch command" "ros2 launch --help"

echo ""
echo "--- ROS2 Package Tests ---"
test_command "xacro installed" "ros2 pkg prefix xacro"
test_command "robot_state_publisher" "ros2 pkg prefix robot_state_publisher"
test_command "joint_state_publisher" "ros2 pkg prefix joint_state_publisher"
test_command "rviz2 installed" "ros2 pkg prefix rviz2"
test_command "gazebo_ros installed" "ros2 pkg prefix gazebo_ros"
test_command "controller_manager" "ros2 pkg prefix controller_manager"
test_command "moveit installed" "ros2 pkg prefix moveit"

echo ""
echo "--- Workspace Package Tests ---"
test_command "so101_description" "ros2 pkg prefix so101_description"
test_command "so101_bringup" "ros2 pkg prefix so101_bringup"
test_command "so101_moveit_config" "ros2 pkg prefix so101_moveit_config"
test_command "so101_kinematics" "ros2 pkg prefix so101_kinematics"
test_command "so101_kinematics_msgs" "ros2 pkg prefix so101_kinematics_msgs"
test_command "so101_teleop" "ros2 pkg prefix so101_teleop"
test_command "so101_inference" "ros2 pkg prefix so101_inference"
test_command "so_arm_100_description" "ros2 pkg prefix so_arm_100_description"
test_command "so_arm_100_bringup" "ros2 pkg prefix so_arm_100_bringup"
test_command "so_arm_100_moveit_config" "ros2 pkg prefix so_arm_100_moveit_config"
test_command "episode_recorder" "ros2 pkg prefix episode_recorder"

echo ""
echo "--- Launch File Tests ---"
test_command "follower.launch.py exists" "test -f \$(ros2 pkg prefix so101_bringup)/share/so101_bringup/launch/follower.launch.py"
test_command "teleop.launch.py exists" "test -f \$(ros2 pkg prefix so101_bringup)/share/so101_bringup/launch/teleop.launch.py"
test_command "hardware.launch.py exists" "test -f \$(ros2 pkg prefix so_arm_100_bringup)/share/so_arm_100_bringup/launch/hardware.launch.py"
test_command "display.launch.py exists" "test -f \$(ros2 pkg prefix so101_description)/share/so101_description/launch/display.launch.py"

echo ""
echo "--- Python Tools Tests ---"
test_command "colcon available" "which colcon"
test_command "rosdep available" "which rosdep"

echo ""
echo "========================================="
echo "Test Results"
echo "========================================="
echo -e "${GREEN}Passed: $pass_count${NC}"
echo -e "${RED}Failed: $fail_count${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    echo ""
    echo "You can now test launch files with:"
    echo "  ros2 launch so101_bringup follower.launch.py hardware_type:=mock"
    echo "  ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false"
    echo "  ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true"
    echo ""
else
    echo -e "${YELLOW}Some tests failed. Check the output above.${NC}"
    echo ""
    if [ ! -f install/setup.bash ]; then
        echo "Workspace needs to be built. Run:"
        echo "  cd \"$WORKSPACE_PATH\""
        echo "  colcon build --symlink-install"
    fi
fi

echo ""
