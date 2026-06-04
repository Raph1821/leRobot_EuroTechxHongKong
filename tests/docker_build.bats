#!/usr/bin/env bats
# =============================================================================
# docker_build.bats - Tests for scripts/docker-build.sh
#
# Validates:
#   - SO-101 directory missing â†’ exit 1 with error message containing path
#   - Partial packages â†’ copies found ones, warns for missing
#   - Cleanup removes all SO-101 packages from project root after build
#   - Trap cleanup fires on simulated failure (mock docker build failure)
#
# Requirements: 8.2, 8.3, 8.4, 8.5
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'
load 'test_helper'

# --- Setup / Teardown --------------------------------------------------------

setup() {
    common_setup
    setup_mock_docker
    create_test_project_dir

    # Copy the real docker-build.sh into the test project
    cp "${BATS_TEST_DIRNAME}/../scripts/docker-build.sh" "${TEST_PROJECT_ROOT}/scripts/docker-build.sh"
    chmod +x "${TEST_PROJECT_ROOT}/scripts/docker-build.sh"
}

teardown() {
    common_teardown
}

# --- Helper: run docker-build.sh with PROJECT_ROOT override ------------------
# The script derives PROJECT_ROOT from SCRIPT_DIR (BASH_SOURCE), so placing
# the script inside TEST_PROJECT_ROOT/scripts/ makes it compute the correct
# PROJECT_ROOT automatically.

run_docker_build() {
    run bash "${TEST_PROJECT_ROOT}/scripts/docker-build.sh" "$@"
}

# =============================================================================
# Test: SO-101 directory missing â†’ exit 1 with error message containing path
# Requirement: 8.2
# =============================================================================

@test "docker-build.sh exits 1 when SO-101 source directory does not exist" {
    # Point SO101_SRC_DIR to a nonexistent path
    export SO101_SRC_DIR="/nonexistent/path/to/so101"

    run_docker_build

    assert_failure
    # The error message should contain the path that was attempted
    assert_output --partial "/nonexistent/path/to/so101"
    assert_output --partial "ERROR"
    assert_output --partial "SO101_SRC_DIR"
}

@test "docker-build.sh error message includes instructions to set SO101_SRC_DIR" {
    export SO101_SRC_DIR="/tmp/no_such_dir_$$"

    run_docker_build

    assert_failure
    assert_output --partial "export SO101_SRC_DIR"
}

# =============================================================================
# Test: Partial packages â†’ copies found ones, warns for missing
# Requirement: 8.3
# =============================================================================

@test "docker-build.sh copies available packages and warns for missing ones" {
    # Create partial SO-101 source with only 2 packages
    create_partial_so101_source_dir so101_description so101_bringup
    export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"

    run_docker_build

    assert_success

    # Verify found packages were copied into project root
    [ -d "${TEST_PROJECT_ROOT}/so101_description" ]
    [ -d "${TEST_PROJECT_ROOT}/so101_bringup" ]

    # Verify warnings for missing packages
    assert_output --partial "WARNING"
    assert_output --partial "so101_teleop"
    assert_output --partial "skipping"
}

@test "docker-build.sh copies all packages when all are present" {
    # Create full SO-101 source with all packages
    create_so101_source_dir
    export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"

    run_docker_build

    assert_success

    # Verify all packages were copied
    for pkg in "${SO101_PACKAGES[@]}"; do
        [ -d "${TEST_PROJECT_ROOT}/${pkg}" ] || \
            fail "Expected package directory ${pkg} to exist in project root"
    done

    # No warnings should appear for missing packages
    refute_output --partial "WARNING"
}

# =============================================================================
# Test: Cleanup removes all SO-101 packages from project root after build
# Requirement: 8.4
# =============================================================================

@test "docker-build.sh cleans up SO-101 packages after successful build" {
    create_so101_source_dir
    export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"
    export MOCK_DOCKER_BUILD_EXIT_CODE=0

    run_docker_build

    assert_success

    # Verify ALL SO-101 packages have been removed from the project root
    for pkg in "${SO101_PACKAGES[@]}"; do
        [ ! -d "${TEST_PROJECT_ROOT}/${pkg}" ] || \
            fail "Expected package directory ${pkg} to be cleaned up, but it still exists"
    done
}

# =============================================================================
# Test: Trap cleanup fires on simulated failure (mock docker build failure)
# Requirement: 8.5
# =============================================================================

@test "docker-build.sh cleans up SO-101 packages after docker build failure" {
    create_so101_source_dir
    export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"
    export MOCK_DOCKER_BUILD_EXIT_CODE=1

    run_docker_build

    # Script should propagate the non-zero exit code
    assert_failure

    # Verify ALL SO-101 packages have been removed despite the build failure
    for pkg in "${SO101_PACKAGES[@]}"; do
        [ ! -d "${TEST_PROJECT_ROOT}/${pkg}" ] || \
            fail "Expected package directory ${pkg} to be cleaned up after failure, but it still exists"
    done
}

@test "docker-build.sh propagates docker build exit code on failure" {
    create_so101_source_dir
    export SO101_SRC_DIR="${MOCK_SO101_SRC_DIR}"
    export MOCK_DOCKER_BUILD_EXIT_CODE=1

    run_docker_build

    # The exit status should be non-zero (propagated from docker build)
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker build failed"
}
