#!/bin/bash
# Setup script for the Humble overlay workspace.
# Sources the ROS2 Humble distribution setup before building or sourcing this workspace.
#
# Usage:
#   source workspaces/humble_ws/setup_overlay.bash
#
# This script:
# 1. Sources the ROS2 Humble distribution setup file
# 2. Sources the local workspace install (if it exists)

set -e

# Source ROS2 Humble base distribution
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
else
    echo "ERROR: ROS2 Humble not found at /opt/ros/humble/setup.bash"
    echo "Please install ROS2 Humble or adjust the path."
    return 1 2>/dev/null || exit 1
fi

# Source the local overlay workspace install if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/install/setup.bash" ]; then
    source "${SCRIPT_DIR}/install/setup.bash"
    echo "Humble overlay workspace sourced: ${SCRIPT_DIR}/install/setup.bash"
else
    echo "Humble overlay workspace not yet built. Run 'colcon build' in ${SCRIPT_DIR} first."
fi
