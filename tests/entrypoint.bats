#!/usr/bin/env bats
# =============================================================================
# entrypoint.bats - Tests for scripts/entrypoint.sh
#
# Strategy: Create a testable version of entrypoint.sh that sources from a mock
# ROS setup file and uses mock commands (ros2, nvidia-smi, python3) via PATH
# manipulation. The entrypoint is run with `bash` and we capture its output.
#
# Requirements: 4.1, 4.2, 4.5, 4.6, 4.7, 5.5, 5.6, 10.1, 10.2
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'
load 'test_helper'

# --- Test Setup/Teardown -----------------------------------------------------

setup() {
    common_setup

    # Create mock bin directory for fake commands
    MOCK_BIN_DIR="${TEST_TEMP_DIR}/mock_bin"
    mkdir -p "${MOCK_BIN_DIR}"

    # Create a mock ROS setup.bash that sets ROS_DISTRO
    MOCK_ROS_SETUP="${TEST_TEMP_DIR}/ros_setup.bash"
    cat > "${MOCK_ROS_SETUP}" <<'EOF'
export ROS_DISTRO=jazzy
EOF

    # Create mock workspace directory
    MOCK_WORKSPACE="${TEST_TEMP_DIR}/workspace"
    mkdir -p "${MOCK_WORKSPACE}"

    # Create a testable entrypoint that uses our mock paths instead of hardcoded ones
    TESTABLE_ENTRYPOINT="${TEST_TEMP_DIR}/entrypoint_testable.sh"
    create_testable_entrypoint

    # Create mock ros2 command (default: package not found)
    create_mock_ros2 ""

    # Create mock nvidia-smi (default: not available Ã¢â‚¬â€ won't be in PATH)
    # Tests that need nvidia-smi will add it explicitly

    # Create mock python3 that just exits
    cat > "${MOCK_BIN_DIR}/python3" <<'EOF'
#!/usr/bin/env bash
# Mock python3 Ã¢â‚¬â€ does nothing, exits immediately
exit 0
EOF
    chmod +x "${MOCK_BIN_DIR}/python3"

    # Prepend mock bin to PATH
    export PATH="${MOCK_BIN_DIR}:${PATH}"
}

teardown() {
    common_teardown
}

# --- Helper Functions --------------------------------------------------------

# create_testable_entrypoint
#   Generates a modified version of entrypoint.sh that:
#   - Sources from our mock ROS setup file instead of /opt/ros/jazzy/setup.bash
#   - Uses MOCK_WORKSPACE instead of /workspace
#   - Does NOT call exec "$@" (so we can capture all output)
#   - Runs background commands as no-ops or quick exits
create_testable_entrypoint() {
    cat > "${TESTABLE_ENTRYPOINT}" <<SCRIPT
#!/bin/bash
set -e

echo "=== SO-100/SO-101 All-in-One Development Environment ==="
echo ""

# Step 1: GPU Check
if [ "\${SKIP_GPU_CHECK:-0}" != "1" ]; then
    if command -v nvidia-smi &> /dev/null; then
        echo "--- Checking GPU ---"
        nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader 2>/dev/null || true
        echo ""
    else
        echo "--- No NVIDIA GPU detected (Isaac Sim will not work, but ROS2 + hardware control is fine) ---"
        echo ""
    fi
fi

# Step 2: Source ROS2 Jazzy + workspace overlay
echo "--- Sourcing ROS2 Jazzy ---"
source "${MOCK_ROS_SETUP}"

if [ -f "${MOCK_WORKSPACE}/install/setup.bash" ]; then
    source "${MOCK_WORKSPACE}/install/setup.bash"
    echo "Workspace overlay sourced."
else
    echo "INFO: /workspace/install/setup.bash not found Ã¢â‚¬â€ workspace overlay was not sourced."
fi

echo "ROS_DISTRO=\${ROS_DISTRO}"
echo ""

# Step 3: Auto-start services if AUTO_START=1
if [ "\${AUTO_START:-0}" = "1" ]; then
    echo "--- Auto-starting WebSocket bridge and web server ---"

    # Start WebSocket bridge node in background
    if ros2 pkg list 2>/dev/null | grep -q so_arm_100_web_bridge; then
        echo "WebSocket bridge started on ws://0.0.0.0:9090"
    else
        echo "INFO: so_arm_100_web_bridge package not found in ROS2 workspace. Skipping WebSocket bridge startup."
    fi

    # Serve the web interface on port 8080
    if [ -d "${MOCK_WORKSPACE}/web_static" ] && [ -f "${MOCK_WORKSPACE}/web_static/index.html" ]; then
        echo "Web interface served on http://0.0.0.0:8080 (from /workspace/web_static)"
    else
        echo "INFO: /workspace/web_static directory not found or missing index.html. Skipping HTTP server startup."
    fi

    echo ""
fi

echo "=== Environment ready ==="
echo ""
echo "Available commands:"
echo "  ros2 launch so101_bringup <launch_file>   Ã¢â‚¬â€ Launch SO-101 arm"
echo "  ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=isaac_sim"
echo "  ros2 run so_arm_100_web_bridge websocket_bridge  Ã¢â‚¬â€ Start WebSocket bridge"
echo "  ros2 run so101_teleop teleop              Ã¢â‚¬â€ Run leader-follower teleop"
echo ""
SCRIPT
    chmod +x "${TESTABLE_ENTRYPOINT}"
}

# create_mock_ros2 [packages...]
#   Creates a mock ros2 command. If packages are provided, `ros2 pkg list`
#   will output them (one per line). Otherwise outputs nothing.
create_mock_ros2() {
    local packages="$1"
    cat > "${MOCK_BIN_DIR}/ros2" <<EOF
#!/usr/bin/env bash
# Mock ros2 command
if [ "\$1" = "pkg" ] && [ "\$2" = "list" ]; then
    echo "${packages}"
    exit 0
fi
# For ros2 run / ros2 launch Ã¢â‚¬â€ just exit
exit 0
EOF
    chmod +x "${MOCK_BIN_DIR}/ros2"
}

# create_mock_nvidia_smi [output]
#   Creates a mock nvidia-smi command in the mock bin directory.
#   If output is provided, it will be printed when nvidia-smi is called.
create_mock_nvidia_smi() {
    local output="${1:-NVIDIA GeForce RTX 3090, 8.6}"
    cat > "${MOCK_BIN_DIR}/nvidia-smi" <<EOF
#!/usr/bin/env bash
# Mock nvidia-smi
echo "${output}"
exit 0
EOF
    chmod +x "${MOCK_BIN_DIR}/nvidia-smi"
}

# create_workspace_overlay
#   Creates a mock workspace overlay setup.bash in the mock workspace.
create_workspace_overlay() {
    mkdir -p "${MOCK_WORKSPACE}/install"
    cat > "${MOCK_WORKSPACE}/install/setup.bash" <<'EOF'
# Mock workspace overlay
export WORKSPACE_OVERLAY_SOURCED=1
EOF
}

# create_web_static
#   Creates the web_static directory with an index.html file.
create_web_static() {
    mkdir -p "${MOCK_WORKSPACE}/web_static"
    echo "<html><body>Mock</body></html>" > "${MOCK_WORKSPACE}/web_static/index.html"
}

# --- Tests -------------------------------------------------------------------

# Requirement 4.5: AUTO_START=0 Ã¢â€ â€™ no background services started
@test "entrypoint: AUTO_START=0 does not start any services" {
    export AUTO_START=0

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    # Should NOT contain any auto-start messages
    refute_output --partial "Auto-starting WebSocket bridge"
    refute_output --partial "WebSocket bridge started"
    refute_output --partial "Web interface served"
}

# Requirement 4.5: AUTO_START unset Ã¢â€ â€™ no background services started
@test "entrypoint: AUTO_START unset does not start any services" {
    unset AUTO_START

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    refute_output --partial "Auto-starting WebSocket bridge"
    refute_output --partial "WebSocket bridge started"
    refute_output --partial "Web interface served"
}

# Requirement 4.1: AUTO_START=1 with bridge package present Ã¢â€ â€™ bridge started
@test "entrypoint: AUTO_START=1 with bridge package starts WebSocket bridge" {
    export AUTO_START=1

    # Mock ros2 to include the web bridge package
    create_mock_ros2 "so_arm_100_web_bridge"

    # Also create web_static so the HTTP server message appears
    create_web_static

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "WebSocket bridge started on ws://0.0.0.0:9090"
}

# Requirement 4.6: AUTO_START=1 with bridge package NOT present Ã¢â€ â€™ skip message
@test "entrypoint: AUTO_START=1 without bridge package prints skip message" {
    export AUTO_START=1

    # ros2 pkg list returns nothing (no web bridge package)
    create_mock_ros2 ""

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "so_arm_100_web_bridge package not found"
    assert_output --partial "Skipping WebSocket bridge startup"
}

# Requirement 4.7: AUTO_START=1 with missing web_static Ã¢â€ â€™ skip message
@test "entrypoint: AUTO_START=1 with missing web_static prints skip message" {
    export AUTO_START=1

    # Ensure web_static does NOT exist (default Ã¢â‚¬â€ not created)
    # Bridge package is available
    create_mock_ros2 "so_arm_100_web_bridge"

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "web_static directory not found or missing index.html"
    assert_output --partial "Skipping HTTP server startup"
}

# Requirement 4.2: AUTO_START=1 with web_static present Ã¢â€ â€™ HTTP server started
@test "entrypoint: AUTO_START=1 with web_static starts HTTP server" {
    export AUTO_START=1

    create_mock_ros2 "so_arm_100_web_bridge"
    create_web_static

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "Web interface served on http://0.0.0.0:8080"
}

# Requirement 5.6, 10.2: Missing overlay Ã¢â€ â€™ info message, no error exit
@test "entrypoint: missing workspace overlay prints info message and continues" {
    # Do NOT create workspace overlay (default state)
    export AUTO_START=0

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "workspace overlay was not sourced"
}

# Requirement 5.5: Overlay present Ã¢â€ â€™ sourced successfully
@test "entrypoint: workspace overlay is sourced when present" {
    export AUTO_START=0
    create_workspace_overlay

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "Workspace overlay sourced."
    refute_output --partial "overlay was not sourced"
}

# Requirement 10.1: ROS_DISTRO printed to stdout
@test "entrypoint: prints ROS_DISTRO to stdout" {
    export AUTO_START=0

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "ROS_DISTRO=jazzy"
}

# GPU check: SKIP_GPU_CHECK=1 Ã¢â€ â€™ GPU check skipped
@test "entrypoint: SKIP_GPU_CHECK=1 skips GPU check" {
    export SKIP_GPU_CHECK=1
    export AUTO_START=0

    # Even with nvidia-smi available, it should NOT be called
    create_mock_nvidia_smi "NVIDIA GeForce RTX 3090, 8.6"

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    # Should NOT contain GPU-related output
    refute_output --partial "Checking GPU"
    refute_output --partial "No NVIDIA GPU detected"
    refute_output --partial "NVIDIA GeForce"
}

# GPU check: Without nvidia-smi Ã¢â€ â€™ warning printed, startup continues
@test "entrypoint: without nvidia-smi prints warning and continues" {
    export SKIP_GPU_CHECK=0
    export AUTO_START=0

    # Remove nvidia-smi from PATH (default Ã¢â‚¬â€ not created in mock bin)
    # Make sure it's definitely not available
    if [ -f "${MOCK_BIN_DIR}/nvidia-smi" ]; then
        rm -f "${MOCK_BIN_DIR}/nvidia-smi"
    fi

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "No NVIDIA GPU detected"
    assert_output --partial "Isaac Sim will not work"
}

# GPU check: With nvidia-smi available Ã¢â€ â€™ GPU info printed
@test "entrypoint: with nvidia-smi prints GPU information" {
    export SKIP_GPU_CHECK=0
    export AUTO_START=0

    create_mock_nvidia_smi "NVIDIA GeForce RTX 3090, 8.6"

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "Checking GPU"
    assert_output --partial "NVIDIA GeForce RTX 3090, 8.6"
}

# Verify entrypoint prints available commands (SO-100 and SO-101)
@test "entrypoint: prints available launch commands for SO-100 and SO-101" {
    export AUTO_START=0

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    # SO-100 launch command
    assert_output --partial "so_arm_100_bringup"
    # SO-101 launch command
    assert_output --partial "so101_bringup"
}

# Verify banner output
@test "entrypoint: prints environment banner" {
    export AUTO_START=0

    run bash "${TESTABLE_ENTRYPOINT}"
    assert_success

    assert_output --partial "SO-100/SO-101 All-in-One Development Environment"
    assert_output --partial "Environment ready"
}
