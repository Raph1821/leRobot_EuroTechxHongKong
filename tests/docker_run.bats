#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/docker-run.sh
#
# Validates:
#   - Default invocation includes --gpus all, --network host, --ipc host
#   - --no-gpu omits --gpus, adds -e SKIP_GPU_CHECK=1
#   - --auto sets -e AUTO_START=1
#   - --device /dev/nonexistent exits with error message
#   - Auto-detection of /dev/ttyUSB0 and /dev/ttyACM0 when present
#   - DISPLAY defaults to :0 when unset
#
# Requirements: 2.1, 2.4, 3.1, 3.2, 3.3, 7.1, 7.5
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'
load 'test_helper'

# --- Setup / Teardown --------------------------------------------------------

setup() {
    common_setup
    setup_mock_docker
    create_test_project_dir

    # Copy the real docker-run.sh into the test project so SCRIPT_DIR resolves
    cp "${BATS_TEST_DIRNAME}/../scripts/docker-run.sh" "${TEST_PROJECT_ROOT}/scripts/docker-run.sh"
    chmod +x "${TEST_PROJECT_ROOT}/scripts/docker-run.sh"
}

teardown() {
    common_teardown
}

# --- Helper ------------------------------------------------------------------

# run_docker_run [args...]
#   Executes docker-run.sh from the test project root.
run_docker_run() {
    run bash "${TEST_PROJECT_ROOT}/scripts/docker-run.sh" "$@"
}

# --- Tests -------------------------------------------------------------------

@test "default invocation includes --gpus all" {
    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"--gpus all"* ]]
}

@test "default invocation includes --network host" {
    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"--network host"* ]]
}

@test "default invocation includes --ipc host" {
    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"--ipc host"* ]]
}

@test "--no-gpu omits --gpus all" {
    run_docker_run --no-gpu
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" != *"--gpus all"* ]]
}

@test "--no-gpu adds -e SKIP_GPU_CHECK=1" {
    run_docker_run --no-gpu
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"-e SKIP_GPU_CHECK=1"* ]]
}

@test "--auto sets -e AUTO_START=1" {
    run_docker_run --auto
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"-e AUTO_START=1"* ]]
}

@test "--device with nonexistent path exits with error" {
    run_docker_run --device /dev/this_device_does_not_exist_xyz
    assert_failure
    assert_output --partial "does not exist"
}

@test "--device error message includes the device path" {
    run_docker_run --device /dev/this_device_does_not_exist_xyz
    assert_failure
    assert_output --partial "/dev/this_device_does_not_exist_xyz"
}

@test "auto-detects /dev/ttyUSB0 when present" {
    # Skip if /dev/ttyUSB0 doesn't exist on this system — can't test auto-detect
    # without the real device (script checks [ -e /dev/ttyUSB0 ] directly)
    if [ ! -e /dev/ttyUSB0 ]; then
        skip "No /dev/ttyUSB0 on this system"
    fi

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"--device /dev/ttyUSB0"* ]]
}

@test "auto-detects /dev/ttyACM0 when present" {
    # Skip if /dev/ttyACM0 doesn't exist on this system
    if [ ! -e /dev/ttyACM0 ]; then
        skip "No /dev/ttyACM0 on this system"
    fi

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"--device /dev/ttyACM0"* ]]
}

@test "does not include /dev/ttyUSB0 when absent" {
    # Skip if /dev/ttyUSB0 DOES exist — cannot test absence
    if [ -e /dev/ttyUSB0 ]; then
        skip "/dev/ttyUSB0 exists on this system"
    fi

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" != *"--device /dev/ttyUSB0"* ]]
}

@test "does not include /dev/ttyACM0 when absent" {
    # Skip if /dev/ttyACM0 DOES exist — cannot test absence
    if [ -e /dev/ttyACM0 ]; then
        skip "/dev/ttyACM0 exists on this system"
    fi

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" != *"--device /dev/ttyACM0"* ]]
}

@test "DISPLAY defaults to :0 when unset" {
    unset DISPLAY

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"-e DISPLAY=:0"* ]]
}

@test "DISPLAY uses host value when set" {
    export DISPLAY=":1"

    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"-e DISPLAY=:1"* ]]
}

@test "default invocation mounts X11 socket" {
    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *"/tmp/.X11-unix:/tmp/.X11-unix:rw"* ]]
}

@test "default invocation mounts project root to /workspace" {
    run_docker_run
    assert_success

    args="$(get_docker_run_args)"
    [[ "${args}" == *":/workspace:rw"* ]]
}
