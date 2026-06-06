#!/bin/bash
# =============================================================================
# Run the SO-100/SO-101 all-in-one Docker container
#
# Usage:
#   ./scripts/docker-run.sh              # Interactive bash shell
#   ./scripts/docker-run.sh --auto       # Auto-start web interface + bridge
#   ./scripts/docker-run.sh --no-gpu     # Without GPU (no Isaac Sim)
#
# Flags:
#   --auto      : Auto-start WebSocket bridge + web interface on ports 9090/8080
#   --no-gpu    : Skip GPU passthrough (for systems without NVIDIA GPU)
#   --device X  : Pass additional device (e.g., --device /dev/ttyACM0)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="so100-all-in-one"
CONTAINER_NAME="so100-dev"

# Default flags
GPU_FLAGS="--gpus all"
ENV_FLAGS=""
DEVICE_FLAGS=""
AUTO_START="0"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --auto)
            AUTO_START="1"
            shift
            ;;
        --no-gpu)
            GPU_FLAGS=""
            ENV_FLAGS="${ENV_FLAGS} -e SKIP_GPU_CHECK=1"
            shift
            ;;
        --device)
            if [ ! -e "$2" ]; then
                echo "ERROR: Device path '$2' does not exist on the host." >&2
                exit 1
            fi
            DEVICE_FLAGS="${DEVICE_FLAGS} --device $2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# Auto-detect USB serial devices for feetech servos
if [ -e /dev/ttyUSB0 ]; then
    DEVICE_FLAGS="${DEVICE_FLAGS} --device /dev/ttyUSB0"
fi
if [ -e /dev/ttyACM0 ]; then
    DEVICE_FLAGS="${DEVICE_FLAGS} --device /dev/ttyACM0"
fi

echo "=== Running ${IMAGE_NAME} ==="
echo "  GPU: ${GPU_FLAGS:-disabled}"
echo "  Auto-start: ${AUTO_START}"
echo "  Devices: ${DEVICE_FLAGS:-none}"
echo ""

# --network host and --ipc host are mandatory for ROS2 DDS discovery and shared
# memory transport. They are placed first (after run flags) so that no user
# arguments can override or omit them (Requirements 7.1, 7.5).
docker run --rm -it \
    --network host \
    --ipc host \
    ${GPU_FLAGS} \
    ${DEVICE_FLAGS} \
    -e DISPLAY="${DISPLAY:-:0}" \
    -e AUTO_START="${AUTO_START}" \
    ${ENV_FLAGS} \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "${PROJECT_ROOT}:/workspace:rw" \
    --name "${CONTAINER_NAME}" \
    "${IMAGE_NAME}" \
    "$@"
