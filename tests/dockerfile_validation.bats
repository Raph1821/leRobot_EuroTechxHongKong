#!/usr/bin/env bats
# =============================================================================
# dockerfile_validation.bats - Validation tests for Dockerfile and image metadata
#
# Tests are split into two categories:
#   1. Static Dockerfile parsing (no Docker required)
#   2. Image-based validation (requires built so100-all-in-one image)
#
# Requirements: 1.5, 1.7, 4.4, 5.7
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'
load 'test_helper'

# Path to the Dockerfile relative to the project root
DOCKERFILE_PATH=""
IMAGE_NAME="so100-all-in-one"

setup() {
    common_setup
    # Resolve Dockerfile path (tests/ is one level below project root)
    DOCKERFILE_PATH="${BATS_TEST_DIRNAME}/../Dockerfile"
}

teardown() {
    common_teardown
}

# --- Helper Functions --------------------------------------------------------

# Check if the Docker image is available locally
image_available() {
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1
}

# =============================================================================
# Static Dockerfile Parsing Tests (no Docker daemon required)
# =============================================================================

@test "Dockerfile contains EXPOSE 9090 8080 directive" {
    # Validates: Requirement 4.4 - Container exposes ports 9090 and 8080
    run grep -E '^EXPOSE\s+.*9090' "${DOCKERFILE_PATH}"
    assert_success

    run grep -E '^EXPOSE\s+.*8080' "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile writes ROS2 sourcing commands to /etc/bash.bashrc" {
    # Validates: Requirement 5.7 - /etc/bash.bashrc sources ROS2 setup
    run grep -E "bash.bashrc.*source.*/opt/ros/jazzy/setup.bash" "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile conditionally sources workspace overlay in /etc/bash.bashrc" {
    # Validates: Requirement 5.7 - /etc/bash.bashrc conditionally sources workspace overlay
    run grep -E "bash.bashrc.*workspace/install/setup.bash" "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile copies web_interface and builds to web_static" {
    # Validates: Requirement 1.7 - Web interface is built with Vite
    run grep -E '^COPY\s+web_interface/' "${DOCKERFILE_PATH}"
    assert_success

    run grep -E 'web_static' "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile creates /workspace/web_static with built assets" {
    # Validates: Requirement 1.7 - Static assets output to /workspace/web_static
    run grep -E 'mkdir.*web_static|cp.*web_static' "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile builds colcon workspace producing install artifacts" {
    # Validates: Requirement 1.5 - colcon build produces install directory
    run grep -E 'colcon build' "${DOCKERFILE_PATH}"
    assert_success
}

@test "Dockerfile EXPOSE directive lists both ports on same line" {
    # Validates: Requirement 4.4 - Both ports exposed
    run grep -E '^EXPOSE\s+9090\s+8080' "${DOCKERFILE_PATH}"
    assert_success
}

# =============================================================================
# Image-Based Validation Tests (require built Docker image)
# =============================================================================

@test "built image exposes port 9090" {
    # Validates: Requirement 4.4 - Image metadata shows port 9090 exposed
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker inspect --format='{{json .Config.ExposedPorts}}' "${IMAGE_NAME}"
    assert_success
    assert_output --partial "9090/tcp"
}

@test "built image exposes port 8080" {
    # Validates: Requirement 4.4 - Image metadata shows port 8080 exposed
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker inspect --format='{{json .Config.ExposedPorts}}' "${IMAGE_NAME}"
    assert_success
    assert_output --partial "8080/tcp"
}

@test "/etc/bash.bashrc contains ROS2 Jazzy sourcing command" {
    # Validates: Requirement 5.7 - /etc/bash.bashrc sources /opt/ros/jazzy/setup.bash
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker run --rm "${IMAGE_NAME}" cat /etc/bash.bashrc
    assert_success
    assert_output --partial "source /opt/ros/jazzy/setup.bash"
}

@test "/etc/bash.bashrc contains conditional workspace overlay sourcing" {
    # Validates: Requirement 5.7 - /etc/bash.bashrc conditionally sources workspace overlay
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker run --rm "${IMAGE_NAME}" cat /etc/bash.bashrc
    assert_success
    assert_output --partial "/workspace/install/setup.bash"
}

@test "/workspace/web_static/index.html exists in built image" {
    # Validates: Requirement 1.7 - Pre-built web interface with index.html
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker run --rm "${IMAGE_NAME}" test -f /workspace/web_static/index.html
    assert_success
}

@test "/workspace/install/setup.bash exists in built image" {
    # Validates: Requirement 1.5 - Compiled artifacts under /workspace/install
    if ! image_available; then
        skip "Docker image '${IMAGE_NAME}' not available - skipping image-based test"
    fi

    run docker run --rm "${IMAGE_NAME}" test -f /workspace/install/setup.bash
    assert_success
}
