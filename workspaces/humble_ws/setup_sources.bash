#!/bin/bash
# Creates symlinks from the SO-100-arm packages at the repository root
# into this workspace's src/ directory.
#
# Usage:
#   cd workspaces/humble_ws
#   bash setup_sources.bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
REPO_ROOT="${SCRIPT_DIR}/../.."

mkdir -p "${SRC_DIR}"

# SO-100-arm packages to symlink
PACKAGES=(
    "so_arm_100"
    "so_arm_100_bringup"
    "so_arm_100_description"
    "so_arm_100_moveit_config"
    "so_arm_100_isaac_sim"
    "so_arm_100_web_bridge"
)

for pkg in "${PACKAGES[@]}"; do
    if [ ! -e "${SRC_DIR}/${pkg}" ]; then
        ln -s "${REPO_ROOT}/${pkg}" "${SRC_DIR}/${pkg}"
        echo "Linked: ${pkg} -> ${REPO_ROOT}/${pkg}"
    else
        echo "Already exists: ${SRC_DIR}/${pkg}"
    fi
done

echo ""
echo "Humble workspace sources configured."
echo "To build: source setup_overlay.bash && colcon build --symlink-install"
