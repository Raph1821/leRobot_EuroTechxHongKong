#!/bin/bash
# Top-level workspace setup script for the SO-100 Unified Project.
#
# This script prepares both colcon overlay workspaces:
# - Humble workspace: SO-100-arm packages (so_arm_100, so_arm_100_bringup, 
#   so_arm_100_description, so_arm_100_moveit_config, so_arm_100_isaac_sim,
#   so_arm_100_web_bridge)
# - Jazzy workspace: so101-ros-physical-ai packages
#
# Usage:
#   bash workspaces/setup_workspace.bash
#
# After setup, build each workspace:
#   source workspaces/humble_ws/setup_overlay.bash && cd workspaces/humble_ws && colcon build --symlink-install
#   source workspaces/jazzy_ws/setup_overlay.bash && cd workspaces/jazzy_ws && colcon build --symlink-install

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== SO-100 Unified Workspace Setup ==="
echo ""

# Set up Humble workspace sources
echo "--- Setting up Humble overlay workspace ---"
bash "${SCRIPT_DIR}/humble_ws/setup_sources.bash"
echo ""

# Set up Jazzy workspace sources
echo "--- Setting up Jazzy overlay workspace ---"
echo "Jazzy workspace at: ${SCRIPT_DIR}/jazzy_ws/src/"
echo "Note: Clone or symlink so101-ros-physical-ai packages into jazzy_ws/src/"
echo "See jazzy_ws/jazzy.repos for package list."
echo ""

echo "=== Workspace setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Build Humble overlay:"
echo "     source workspaces/humble_ws/setup_overlay.bash"
echo "     cd workspaces/humble_ws && colcon build --symlink-install"
echo ""
echo "  2. Build Jazzy overlay:"
echo "     source workspaces/jazzy_ws/setup_overlay.bash"
echo "     cd workspaces/jazzy_ws && colcon build --symlink-install"
echo ""
echo "  3. Source final overlay for development:"
echo "     source workspaces/jazzy_ws/setup_overlay.bash"
echo "     (This sources both Humble and Jazzy overlays)"
