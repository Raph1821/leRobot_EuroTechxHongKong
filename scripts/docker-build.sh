#!/bin/bash
# =============================================================================
# Build the all-in-one Docker image
#
# This script copies the so101 packages into the build context (temporarily)
# then builds the Docker image. Run from the SO-100-arm-main root directory.
#
# Usage:
#   ./scripts/docker-build.sh
#
# The so101-ros-physical-ai-main directory must be at:
#   ../../../so101-ros-physical-ai-main/so101-ros-physical-ai-main/
# (relative to this script) — adjust SO101_SRC_DIR below if different.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SO101_DEFAULT_PATH="${PROJECT_ROOT}/../../so101-ros-physical-ai-main/so101-ros-physical-ai-main"
SO101_SRC_DIR="${SO101_SRC_DIR:-$(cd "${SO101_DEFAULT_PATH}" 2>/dev/null && pwd)}"

# SO-101 packages that get temporarily copied into the build context
SO101_PACKAGES=(
    so101_description
    so101_bringup
    so101_teleop
    so101_moveit_config
    so101_kinematics
    so101_kinematics_msgs
    so101_camera_calibration
    so101_inference
    episode_recorder
    rosbag_to_lerobot
    policy_server
)

# Build exit code: stored after docker build so the script can propagate it after cleanup
BUILD_EXIT_CODE=0

# Cleanup function: removes all temporarily copied SO-101 package directories
# Called via EXIT trap to guarantee cleanup regardless of how the script exits
# After cleanup, the script exits with BUILD_EXIT_CODE to propagate docker build failures
cleanup() {
    local exit_code="${BUILD_EXIT_CODE}"
    echo ""
    echo "--- Cleaning up temporary SO-101 packages ---"
    for pkg in "${SO101_PACKAGES[@]}"; do
        rm -rf "${PROJECT_ROOT}/${pkg}"
    done
    exit "${exit_code}"
}

# Register cleanup on EXIT (covers normal exit, set -e failures, SIGINT, SIGTERM)
trap cleanup EXIT

echo "=== Building SO-100/SO-101 All-in-One Docker Image ==="
echo "Project root: ${PROJECT_ROOT}"
echo "SO-101 source: ${SO101_SRC_DIR}"
echo ""

if [ -z "${SO101_SRC_DIR}" ] || [ ! -d "${SO101_SRC_DIR}" ]; then
    echo "ERROR: SO-101 source directory not found."
    echo ""
    echo "  Attempted path: ${SO101_SRC_DIR:-<not resolved>}"
    echo "  Default path:   ${SO101_DEFAULT_PATH}"
    echo ""
    echo "To fix this, set the SO101_SRC_DIR environment variable to the"
    echo "root of the so101-ros-physical-ai-main repository:"
    echo ""
    echo "  export SO101_SRC_DIR=/path/to/so101-ros-physical-ai-main"
    echo "  ./scripts/docker-build.sh"
    echo ""
    BUILD_EXIT_CODE=1
    exit 1
fi

# Copy so101 packages into the build context (Docker can't read outside context)
echo "--- Copying SO-101 packages into build context ---"

for pkg in "${SO101_PACKAGES[@]}"; do
    if [ -d "${SO101_SRC_DIR}/${pkg}" ]; then
        echo "  Copying ${pkg}..."
        rm -rf "${PROJECT_ROOT}/${pkg}"
        cp -r "${SO101_SRC_DIR}/${pkg}" "${PROJECT_ROOT}/${pkg}"
    else
        echo "  WARNING: ${pkg} not found in SO-101 source, skipping."
    fi
done

echo ""
echo "--- Building Docker image ---"
cd "${PROJECT_ROOT}"

# Temporarily disable set -e so we can capture the docker build exit code
# rather than having the shell exit immediately on failure
set +e
docker build -t so100-all-in-one .
BUILD_EXIT_CODE=$?
set -e

if [ "${BUILD_EXIT_CODE}" -ne 0 ]; then
    echo ""
    echo "ERROR: Docker build failed with exit code ${BUILD_EXIT_CODE}"
    exit "${BUILD_EXIT_CODE}"
fi

echo ""
echo "=== Build complete! ==="
echo ""
echo "Run the container with:"
echo "  docker run --rm -it --gpus all --network host \\"
echo "    --device /dev/ttyUSB0:/dev/ttyUSB0 \\"
echo "    -v \$(pwd):/workspace \\"
echo "    so100-all-in-one"
echo ""
echo "Or with auto-start (web interface + WebSocket bridge):"
echo "  docker run --rm -it --gpus all --network host \\"
echo "    --device /dev/ttyUSB0:/dev/ttyUSB0 \\"
echo "    -e AUTO_START=1 \\"
echo "    -v \$(pwd):/workspace \\"
echo "    so100-all-in-one"
