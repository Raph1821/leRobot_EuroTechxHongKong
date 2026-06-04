#!/bin/bash
# =============================================================================
# GPU Compute Capability Check (Requirement 2.5)
#
# Verifies that the host machine has an NVIDIA GPU with compute capability ≥ 7.0.
# Exits with non-zero code and descriptive error message within 10 seconds
# if the requirement is not met.
# =============================================================================

set -e

MINIMUM_COMPUTE_CAPABILITY="7.0"
TIMEOUT_SECONDS=10

check_gpu() {
    # Check if nvidia-smi is available
    if ! command -v nvidia-smi &> /dev/null; then
        echo "ERROR: nvidia-smi not found. NVIDIA GPU drivers are not installed or not accessible."
        echo "       The SO-100 Isaac Sim development environment requires an NVIDIA GPU"
        echo "       with compute capability >= ${MINIMUM_COMPUTE_CAPABILITY}."
        exit 1
    fi

    # Query GPU compute capability using nvidia-smi
    # Format: compute_cap returns "major.minor" (e.g., "8.6")
    local gpu_info
    gpu_info=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits 2>/dev/null)

    if [ -z "$gpu_info" ]; then
        echo "ERROR: No NVIDIA GPU detected."
        echo "       The SO-100 Isaac Sim development environment requires an NVIDIA GPU"
        echo "       with compute capability >= ${MINIMUM_COMPUTE_CAPABILITY}."
        exit 1
    fi

    # Check each GPU (in case of multi-GPU systems)
    local found_valid_gpu=false
    while IFS= read -r compute_cap; do
        # Remove any whitespace
        compute_cap=$(echo "$compute_cap" | tr -d '[:space:]')

        if [ -z "$compute_cap" ]; then
            continue
        fi

        # Extract major and minor version
        local major minor
        major=$(echo "$compute_cap" | cut -d'.' -f1)
        minor=$(echo "$compute_cap" | cut -d'.' -f2)

        # Compare: need >= 7.0
        local min_major min_minor
        min_major=$(echo "$MINIMUM_COMPUTE_CAPABILITY" | cut -d'.' -f1)
        min_minor=$(echo "$MINIMUM_COMPUTE_CAPABILITY" | cut -d'.' -f2)

        if [ "$major" -gt "$min_major" ] || \
           ([ "$major" -eq "$min_major" ] && [ "$minor" -ge "$min_minor" ]); then
            found_valid_gpu=true
            echo "GPU check passed: compute capability ${compute_cap} >= ${MINIMUM_COMPUTE_CAPABILITY}"
            break
        fi
    done <<< "$gpu_info"

    if [ "$found_valid_gpu" = false ]; then
        echo "ERROR: No NVIDIA GPU with sufficient compute capability found."
        echo "       Detected GPU compute capability: ${gpu_info}"
        echo "       Minimum required compute capability: ${MINIMUM_COMPUTE_CAPABILITY}"
        echo ""
        echo "       Isaac Sim requires an NVIDIA GPU with compute capability >= 7.0"
        echo "       (e.g., RTX 2000 series or newer, Quadro RTX, Tesla V100 or newer)."
        exit 1
    fi
}

# Run the check with a timeout to ensure we exit within 10 seconds (Req 2.5)
export -f check_gpu
export MINIMUM_COMPUTE_CAPABILITY

if command -v timeout &> /dev/null; then
    timeout ${TIMEOUT_SECONDS} bash -c 'check_gpu'
    exit_code=$?
    if [ $exit_code -eq 124 ]; then
        echo "ERROR: GPU check timed out after ${TIMEOUT_SECONDS} seconds."
        exit 1
    fi
    exit $exit_code
else
    # Fallback if timeout command is not available
    check_gpu
fi
