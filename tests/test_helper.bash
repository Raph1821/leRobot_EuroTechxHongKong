#!/usr/bin/env bash
# =============================================================================
# test_helper.bash - Shared test helpers for the Docker All-in-One bats suite
#
# Provides:
#   - Mock docker commands (build, run, inspect) via PATH manipulation
#   - Temporary directory creation simulating SO-101 source layout
#   - Fake device file helpers for testing USB device detection
#   - Setup/teardown helpers for managing test state
#
# Usage in .bats files:
#   load 'test_helper'
#
# Requirements: 3.1, 8.3
# =============================================================================

# --- Configuration -----------------------------------------------------------

# SO-101 packages expected by docker-build.sh
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

# --- Mock Docker Commands ----------------------------------------------------

# Control variable: set to non-zero to make mock docker build fail
# Usage: MOCK_DOCKER_BUILD_EXIT_CODE=1  (simulate build failure)
MOCK_DOCKER_BUILD_EXIT_CODE="${MOCK_DOCKER_BUILD_EXIT_CODE:-0}"

# Control variable: set to non-zero to make mock docker run fail
MOCK_DOCKER_RUN_EXIT_CODE="${MOCK_DOCKER_RUN_EXIT_CODE:-0}"

# File where mock docker run captures its arguments for later assertion
# Set during setup_mock_docker()
MOCK_DOCKER_RUN_ARGS_FILE=""

# File where mock docker build captures its arguments
MOCK_DOCKER_BUILD_ARGS_FILE=""

# Mock docker inspect output (JSON string)
MOCK_DOCKER_INSPECT_OUTPUT='[{"Config":{"ExposedPorts":{"8080/tcp":{},"9090/tcp":{}}}}]'

# setup_mock_docker
#   Creates a temporary directory with a mock `docker` script and prepends it
#   to PATH so that all docker invocations in tests are intercepted.
#
#   The mock script dispatches based on the first argument:
#     - build: exits with MOCK_DOCKER_BUILD_EXIT_CODE, logs args
#     - run:   exits with MOCK_DOCKER_RUN_EXIT_CODE, logs args
#     - inspect: prints MOCK_DOCKER_INSPECT_OUTPUT, exits 0
#
#   Sets:
#     MOCK_DOCKER_BIN_DIR    - path to directory containing the mock
#     MOCK_DOCKER_RUN_ARGS_FILE  - file capturing docker run arguments
#     MOCK_DOCKER_BUILD_ARGS_FILE - file capturing docker build arguments
setup_mock_docker() {
    MOCK_DOCKER_BIN_DIR="$(mktemp -d)"
    MOCK_DOCKER_RUN_ARGS_FILE="$(mktemp)"
    MOCK_DOCKER_BUILD_ARGS_FILE="$(mktemp)"

    # Export variables so the mock script can access them
    export MOCK_DOCKER_BUILD_EXIT_CODE
    export MOCK_DOCKER_RUN_EXIT_CODE
    export MOCK_DOCKER_INSPECT_OUTPUT
    export MOCK_DOCKER_RUN_ARGS_FILE
    export MOCK_DOCKER_BUILD_ARGS_FILE

    cat > "${MOCK_DOCKER_BIN_DIR}/docker" <<'MOCK_SCRIPT'
#!/usr/bin/env bash
# Mock docker command - intercepts build, run, inspect subcommands

subcmd="${1}"
shift

case "${subcmd}" in
    build)
        # Log all build arguments
        echo "build $*" >> "${MOCK_DOCKER_BUILD_ARGS_FILE}"
        exit "${MOCK_DOCKER_BUILD_EXIT_CODE}"
        ;;
    run)
        # Log all run arguments
        echo "run $*" >> "${MOCK_DOCKER_RUN_ARGS_FILE}"
        exit "${MOCK_DOCKER_RUN_EXIT_CODE}"
        ;;
    inspect)
        # Return mock metadata
        echo "${MOCK_DOCKER_INSPECT_OUTPUT}"
        exit 0
        ;;
    *)
        # Pass through any other docker commands as no-ops
        echo "mock-docker: unhandled subcommand '${subcmd}'" >&2
        exit 0
        ;;
esac
MOCK_SCRIPT

    chmod +x "${MOCK_DOCKER_BIN_DIR}/docker"

    # Prepend mock dir to PATH so it shadows real docker
    export PATH="${MOCK_DOCKER_BIN_DIR}:${PATH}"
}

# teardown_mock_docker
#   Removes the mock docker directory and argument capture files.
#   Restores PATH by removing the mock directory prefix.
teardown_mock_docker() {
    if [[ -n "${MOCK_DOCKER_BIN_DIR:-}" && -d "${MOCK_DOCKER_BIN_DIR}" ]]; then
        rm -rf "${MOCK_DOCKER_BIN_DIR}"
        # Remove mock dir from PATH
        export PATH="${PATH#"${MOCK_DOCKER_BIN_DIR}:"}"
    fi
    if [[ -n "${MOCK_DOCKER_RUN_ARGS_FILE:-}" && -f "${MOCK_DOCKER_RUN_ARGS_FILE}" ]]; then
        rm -f "${MOCK_DOCKER_RUN_ARGS_FILE}"
    fi
    if [[ -n "${MOCK_DOCKER_BUILD_ARGS_FILE:-}" && -f "${MOCK_DOCKER_BUILD_ARGS_FILE}" ]]; then
        rm -f "${MOCK_DOCKER_BUILD_ARGS_FILE}"
    fi
}

# get_docker_run_args
#   Returns the captured docker run arguments from the last mock invocation.
#   Useful for asserting that the correct flags were passed.
get_docker_run_args() {
    if [[ -f "${MOCK_DOCKER_RUN_ARGS_FILE}" ]]; then
        cat "${MOCK_DOCKER_RUN_ARGS_FILE}"
    fi
}

# get_docker_build_args
#   Returns the captured docker build arguments from the last mock invocation.
get_docker_build_args() {
    if [[ -f "${MOCK_DOCKER_BUILD_ARGS_FILE}" ]]; then
        cat "${MOCK_DOCKER_BUILD_ARGS_FILE}"
    fi
}

# --- SO-101 Source Directory Simulation --------------------------------------

# create_so101_source_dir
#   Creates a temporary directory simulating the SO-101 source repository
#   with all expected package subdirectories. Each package directory contains
#   a minimal package.xml to confirm it as a valid ROS2 package.
#
#   Sets:
#     MOCK_SO101_SRC_DIR - path to the created SO-101 source directory
#
#   Usage:
#     create_so101_source_dir
#     export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"
create_so101_source_dir() {
    MOCK_SO101_SRC_DIR="$(mktemp -d)"
    export MOCK_SO101_SRC_DIR

    for pkg in "${SO101_PACKAGES[@]}"; do
        mkdir -p "${MOCK_SO101_SRC_DIR}/${pkg}"
        # Create a minimal package.xml to simulate a valid ROS2 package
        cat > "${MOCK_SO101_SRC_DIR}/${pkg}/package.xml" <<EOF
<?xml version="1.0"?>
<package format="3">
  <name>${pkg}</name>
  <version>0.0.1</version>
  <description>Mock ${pkg} package for testing</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>MIT</license>
</package>
EOF
    done
}

# create_partial_so101_source_dir [packages...]
#   Creates a temporary SO-101 source directory with only the specified packages.
#   Useful for testing partial-copy and warning behavior.
#
#   Args:
#     packages... - names of packages to include (others will be missing)
#
#   Sets:
#     MOCK_SO101_SRC_DIR - path to the created directory
#
#   Usage:
#     create_partial_so101_source_dir so101_description so101_bringup
create_partial_so101_source_dir() {
    MOCK_SO101_SRC_DIR="$(mktemp -d)"
    export MOCK_SO101_SRC_DIR

    for pkg in "$@"; do
        mkdir -p "${MOCK_SO101_SRC_DIR}/${pkg}"
        cat > "${MOCK_SO101_SRC_DIR}/${pkg}/package.xml" <<EOF
<?xml version="1.0"?>
<package format="3">
  <name>${pkg}</name>
  <version>0.0.1</version>
  <description>Mock ${pkg} package for testing</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>MIT</license>
</package>
EOF
    done
}

# teardown_so101_source_dir
#   Removes the mock SO-101 source directory.
teardown_so101_source_dir() {
    if [[ -n "${MOCK_SO101_SRC_DIR:-}" && -d "${MOCK_SO101_SRC_DIR}" ]]; then
        rm -rf "${MOCK_SO101_SRC_DIR}"
    fi
}

# --- Fake Device File Helpers ------------------------------------------------

# create_fake_devices [device_paths...]
#   Creates fake device files at the specified paths inside a temporary
#   directory. Returns the base directory so tests can override the
#   device check path.
#
#   Since tests typically run as non-root and cannot create real /dev nodes,
#   this creates a temporary directory structure and regular files that
#   simulate device presence for existence checks ([ -e path ]).
#
#   Sets:
#     MOCK_DEV_DIR - the temporary directory acting as a fake /dev
#
#   Usage:
#     create_fake_devices ttyUSB0 ttyACM0
#     # Files exist at: ${MOCK_DEV_DIR}/ttyUSB0, ${MOCK_DEV_DIR}/ttyACM0
create_fake_devices() {
    MOCK_DEV_DIR="$(mktemp -d)"
    export MOCK_DEV_DIR

    for device in "$@"; do
        touch "${MOCK_DEV_DIR}/${device}"
    done
}

# create_fake_dev_paths [full_paths...]
#   Creates fake device files at full paths inside a temporary root.
#   Useful for testing scripts that check absolute paths like /dev/ttyUSB0.
#
#   Sets:
#     MOCK_ROOT_DIR - the temporary directory acting as a fake filesystem root
#
#   Usage:
#     create_fake_dev_paths /dev/ttyUSB0 /dev/ttyACM0
#     # Files exist at: ${MOCK_ROOT_DIR}/dev/ttyUSB0, ${MOCK_ROOT_DIR}/dev/ttyACM0
create_fake_dev_paths() {
    MOCK_ROOT_DIR="$(mktemp -d)"
    export MOCK_ROOT_DIR

    for path in "$@"; do
        local dir
        dir="$(dirname "${MOCK_ROOT_DIR}${path}")"
        mkdir -p "${dir}"
        touch "${MOCK_ROOT_DIR}${path}"
    done
}

# teardown_fake_devices
#   Removes the fake device directory.
teardown_fake_devices() {
    if [[ -n "${MOCK_DEV_DIR:-}" && -d "${MOCK_DEV_DIR}" ]]; then
        rm -rf "${MOCK_DEV_DIR}"
    fi
    if [[ -n "${MOCK_ROOT_DIR:-}" && -d "${MOCK_ROOT_DIR}" ]]; then
        rm -rf "${MOCK_ROOT_DIR}"
    fi
}

# --- General Setup/Teardown Helpers ------------------------------------------

# TEST_TEMP_DIR - a per-test temporary directory, created by common_setup
TEST_TEMP_DIR=""

# ORIGINAL_PATH - saved PATH before any mock manipulation
ORIGINAL_PATH=""

# common_setup
#   Standard setup function to be called from bats setup().
#   Creates a fresh temp directory and saves the original PATH.
#
#   Usage in .bats:
#     setup() { common_setup; }
common_setup() {
    TEST_TEMP_DIR="$(mktemp -d)"
    export TEST_TEMP_DIR
    ORIGINAL_PATH="${PATH}"
    export ORIGINAL_PATH
}

# common_teardown
#   Standard teardown function to be called from bats teardown().
#   Cleans up temp directory, mock docker, fake devices, and restores PATH.
#
#   Usage in .bats:
#     teardown() { common_teardown; }
common_teardown() {
    # Restore original PATH
    if [[ -n "${ORIGINAL_PATH:-}" ]]; then
        export PATH="${ORIGINAL_PATH}"
    fi

    # Clean up test temp directory
    if [[ -n "${TEST_TEMP_DIR:-}" && -d "${TEST_TEMP_DIR}" ]]; then
        rm -rf "${TEST_TEMP_DIR}"
    fi

    # Clean up mock docker
    teardown_mock_docker

    # Clean up SO-101 source directory
    teardown_so101_source_dir

    # Clean up fake devices
    teardown_fake_devices
}

# create_test_project_dir
#   Creates a minimal project directory structure inside TEST_TEMP_DIR
#   that mimics the SO-100 project root with a scripts/ directory.
#   Useful for testing docker-build.sh and docker-run.sh in isolation.
#
#   Sets:
#     TEST_PROJECT_ROOT - the path to the mock project root
#
#   Usage:
#     create_test_project_dir
#     cp real_script "${TEST_PROJECT_ROOT}/scripts/docker-build.sh"
create_test_project_dir() {
    TEST_PROJECT_ROOT="${TEST_TEMP_DIR}/project"
    export TEST_PROJECT_ROOT
    mkdir -p "${TEST_PROJECT_ROOT}/scripts"
    mkdir -p "${TEST_PROJECT_ROOT}/web_interface"
}
