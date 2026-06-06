#!/bin/bash
# =============================================================================
# Container Entrypoint — SO-100/SO-101 All-in-One Environment
#
# 1. Optionally checks GPU (skip with SKIP_GPU_CHECK=1)
# 2. Sources ROS2 Jazzy + workspace overlay
# 3. Starts the WebSocket bridge and web server in background (optional)
# 4. Executes the provided command (or drops into bash)
# =============================================================================

set -e

echo "=== SO-100/SO-101 All-in-One Development Environment ==="
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: GPU Check (optional — skip with SKIP_GPU_CHECK=1)
# ─────────────────────────────────────────────────────────────────────────────
if [ "${SKIP_GPU_CHECK:-0}" != "1" ]; then
    if command -v nvidia-smi &> /dev/null; then
        echo "--- Checking GPU ---"
        nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader 2>/dev/null || true
        echo ""
    else
        echo "--- No NVIDIA GPU detected (Isaac Sim will not work, but ROS2 + hardware control is fine) ---"
        echo ""
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Source ROS2 Jazzy + workspace overlay
# ─────────────────────────────────────────────────────────────────────────────
echo "--- Sourcing ROS2 Jazzy ---"
source /opt/ros/jazzy/setup.bash

if [ -f "/workspace/install/setup.bash" ]; then
    source /workspace/install/setup.bash
    echo "Workspace overlay sourced."
else
    echo "INFO: /workspace/install/setup.bash not found — workspace overlay was not sourced."
fi

echo "ROS_DISTRO=${ROS_DISTRO}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Auto-start services if AUTO_START=1
# Starts the WebSocket bridge + a simple HTTP server for the web interface
# ─────────────────────────────────────────────────────────────────────────────
if [ "${AUTO_START:-0}" = "1" ]; then
    echo "--- Auto-starting WebSocket bridge and web server ---"

    # Start WebSocket bridge node in background
    if ros2 pkg list 2>/dev/null | grep -q so_arm_100_web_bridge; then
        ros2 run so_arm_100_web_bridge websocket_bridge &
        echo "WebSocket bridge started on ws://0.0.0.0:9090"
    else
        echo "INFO: so_arm_100_web_bridge package not found in ROS2 workspace. Skipping WebSocket bridge startup."
    fi

    # Serve the web interface on port 8080
    # Check that /workspace/web_static exists and contains index.html
    if [ -d "/workspace/web_static" ] && [ -f "/workspace/web_static/index.html" ]; then
        python3 -m http.server 8080 --directory /workspace/web_static &
        echo "Web interface served on http://0.0.0.0:8080 (from /workspace/web_static)"
    else
        echo "INFO: /workspace/web_static directory not found or missing index.html. Skipping HTTP server startup."
    fi

    echo ""
fi

echo "=== Environment ready ==="
echo ""
echo "Available commands:"
echo "  ros2 launch so101_bringup <launch_file>   — Launch SO-101 arm"
echo "  ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=isaac_sim"
echo "  ros2 run so_arm_100_web_bridge websocket_bridge  — Start WebSocket bridge"
echo "  ros2 run so101_teleop teleop              — Run leader-follower teleop"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Execute the provided command
# ─────────────────────────────────────────────────────────────────────────────
exec "$@"
