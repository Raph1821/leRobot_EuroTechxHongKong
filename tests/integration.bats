#!/usr/bin/env bats
# =============================================================================
# integration.bats - Integration tests for the full Docker build-and-run cycle
#
# These tests require:
#   - Docker daemon access
#   - The built so100-all-in-one Docker image
#   - Optionally SO-101 source availability (for build test)
#
# All tests check prerequisites and skip if unavailable.
#
# Requirements: 1.5, 4.1, 4.2, 9.1, 10.1
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'
load 'test_helper'

# --- Configuration -----------------------------------------------------------

IMAGE_NAME="so100-all-in-one"
CONTAINER_NAME_PREFIX="so100-integration-test"
# Timeout for waiting on services (seconds)
SERVICE_TIMEOUT=30
# Health check timing from docker-compose.yaml: start_period=15s + interval=30s
HEALTH_TIMEOUT=50

setup() {
    common_setup
}

teardown() {
    # Stop and remove any test containers that may still be running
    local containers
    containers=$(docker ps -aq --filter "name=${CONTAINER_NAME_PREFIX}" 2>/dev/null || true)
    if [[ -n "${containers}" ]]; then
        docker rm -f ${containers} >/dev/null 2>&1 || true
    fi
    common_teardown
}

# --- Helper Functions --------------------------------------------------------

# Check if Docker is available on the system
docker_available() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

# Check if the so100-all-in-one image is built and available locally
image_available() {
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1
}

# Wait for a port to respond on localhost
# Args: $1 = port, $2 = timeout in seconds
wait_for_port() {
    local port="$1"
    local timeout="${2:-${SERVICE_TIMEOUT}}"
    local elapsed=0

    while [[ ${elapsed} -lt ${timeout} ]]; do
        if curl -s --max-time 2 "http://localhost:${port}" >/dev/null 2>&1; then
            return 0
        elif command -v nc >/dev/null 2>&1 && nc -z localhost "${port}" 2>/dev/null; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    return 1
}

# Wait for container health check to pass
# Args: $1 = container name, $2 = timeout in seconds
wait_for_healthy() {
    local container="$1"
    local timeout="${2:-${HEALTH_TIMEOUT}}"
    local elapsed=0

    while [[ ${elapsed} -lt ${timeout} ]]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "${container}" 2>/dev/null || echo "unknown")
        if [[ "${status}" == "healthy" ]]; then
            return 0
        fi
        if [[ "${status}" == "unhealthy" ]]; then
            return 1
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done
    return 1
}

# =============================================================================
# Integration Tests
# =============================================================================

@test "integration: build image via docker-build.sh succeeds" {
    # Validates: Requirement 1.5 - Multi-stage image build produces compiled artifacts
    command -v docker >/dev/null 2>&1 || skip "Docker not available"
    docker info >/dev/null 2>&1 || skip "Docker daemon not running"

    # This test requires SO-101 source directory access
    local script_dir="${BATS_TEST_DIRNAME}/../scripts"
    local project_root="${BATS_TEST_DIRNAME}/.."
    local so101_default="${project_root}/../../so101-ros-physical-ai-main/so101-ros-physical-ai-main"
    local so101_dir="${SO101_SRC_DIR:-}"

    # Resolve SO-101 source directory
    if [[ -z "${so101_dir}" ]]; then
        if [[ -d "${so101_default}" ]]; then
            so101_dir="${so101_default}"
        else
            skip "SO-101 source directory not available (set SO101_SRC_DIR)"
        fi
    elif [[ ! -d "${so101_dir}" ]]; then
        skip "SO101_SRC_DIR='${so101_dir}' does not exist"
    fi

    # Run the build script
    run bash "${script_dir}/docker-build.sh"
    assert_success

    # Verify the image was created
    run docker image inspect "${IMAGE_NAME}"
    assert_success
}

@test "integration: container outputs ROS_DISTRO=jazzy on startup" {
    # Validates: Requirement 10.1 - Entrypoint prints ROS_DISTRO to stdout
    command -v docker >/dev/null 2>&1 || skip "Docker not available"
    docker info >/dev/null 2>&1 || skip "Docker daemon not running"
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1 || skip "Image not built"

    # Run container with a quick command and capture entrypoint output
    run docker run --rm \
        --name "${CONTAINER_NAME_PREFIX}-distro" \
        -e SKIP_GPU_CHECK=1 \
        "${IMAGE_NAME}" \
        echo "done"
    assert_success
    assert_output --partial "ROS_DISTRO=jazzy"
}

@test "integration: AUTO_START=1 starts WebSocket bridge on port 9090" {
    # Validates: Requirement 4.1 - WebSocket bridge listens on port 9090
    command -v docker >/dev/null 2>&1 || skip "Docker not available"
    docker info >/dev/null 2>&1 || skip "Docker daemon not running"
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1 || skip "Image not built"

    # Start container in background with AUTO_START=1
    docker run -d --rm \
        --name "${CONTAINER_NAME_PREFIX}-ports" \
        --network host \
        --ipc host \
        -e AUTO_START=1 \
        -e SKIP_GPU_CHECK=1 \
        "${IMAGE_NAME}" \
        bash -c "sleep 60"

    # Wait for port 9090 to respond (WebSocket bridge)
    run wait_for_port 9090 "${SERVICE_TIMEOUT}"
    assert_success

    # Cleanup
    docker rm -f "${CONTAINER_NAME_PREFIX}-ports" >/dev/null 2>&1 || true
}

@test "integration: AUTO_START=1 starts HTTP server on port 8080" {
    # Validates: Requirement 4.2 - HTTP server listens on port 8080
    command -v docker >/dev/null 2>&1 || skip "Docker not available"
    docker info >/dev/null 2>&1 || skip "Docker daemon not running"
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1 || skip "Image not built"

    # Start container in background with AUTO_START=1
    docker run -d --rm \
        --name "${CONTAINER_NAME_PREFIX}-http" \
        --network host \
        --ipc host \
        -e AUTO_START=1 \
        -e SKIP_GPU_CHECK=1 \
        "${IMAGE_NAME}" \
        bash -c "sleep 60"

    # Wait for port 8080 to respond (HTTP server)
    run wait_for_port 8080 "${SERVICE_TIMEOUT}"
    assert_success

    # Cleanup
    docker rm -f "${CONTAINER_NAME_PREFIX}-http" >/dev/null 2>&1 || true
}

@test "integration: health check passes within start_period + interval" {
    # Validates: Requirement 9.1 - Health check using ros2 topic list passes
    command -v docker >/dev/null 2>&1 || skip "Docker not available"
    docker info >/dev/null 2>&1 || skip "Docker daemon not running"
    docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1 || skip "Image not built"
    command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || skip "Docker Compose not available"

    local compose_file="${BATS_TEST_DIRNAME}/../docker-compose.yaml"
    [[ -f "${compose_file}" ]] || skip "docker-compose.yaml not found"

    # Start the service using docker compose in detached mode
    docker compose -f "${compose_file}" up -d so100-dev 2>/dev/null || \
        docker-compose -f "${compose_file}" up -d so100-dev 2>/dev/null || \
        skip "Failed to start compose service (may require GPU or devices)"

    # Wait for the health check to report healthy
    # Health timing: start_period(15s) + interval(30s) = 45s, use 50s timeout
    run wait_for_healthy "so100-dev" "${HEALTH_TIMEOUT}"

    # Teardown compose
    docker compose -f "${compose_file}" down >/dev/null 2>&1 || \
        docker-compose -f "${compose_file}" down >/dev/null 2>&1 || true

    assert_success
}
