#!/bin/bash
# Setup script for the Jazzy overlay workspace.
# Sources the ROS2 Jazzy distribution setup before building or sourcing this workspace.
#
# Usage:
#   source workspaces/jazzy_ws/setup_overlay.bash
#
# This script:
# 1. Sources the ROS2 Jazzy distribution setup file
# 2. Sources the Humble overlay workspace (to allow cross-workspace package discovery)
# 3. Sources the local Jazzy workspace install (if it exists)

set -e

# Source ROS2 Jazzy base distribution
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
else
    echo "ERROR: ROS2 Jazzy not found at /opt/ros/jazzy/setup.bash"
    echo "Please install ROS2 Jazzy or adjust the path."
    return 1 2>/dev/null || exit 1
fi

# Source the Humble overlay as an underlay (for cross-workspace package resolution)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUMBLE_WS_INSTALL="${SCRIPT_DIR}/../humble_ws/install/setup.bash"
if [ -f "${HUMBLE_WS_INSTALL}" ]; then
    source "${HUMBLE_WS_INSTALL}"
fi

# Source the local overlay workspace install if available
if [ -f "${SCRIPT_DIR}/install/setup.bash" ]; then
    source "${SCRIPT_DIR}/install/setup.bash"
    echo "Jazzy overlay workspace sourced: ${SCRIPT_DIR}/install/setup.bash"
else
    echo "Jazzy overlay workspace not yet built. Run 'colcon build' in ${SCRIPT_DIR} first."
fi
