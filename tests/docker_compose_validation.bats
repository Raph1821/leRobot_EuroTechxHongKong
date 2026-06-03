#!/usr/bin/env bats
# =============================================================================
# docker_compose_validation.bats - YAML validation tests for docker-compose.yaml
#
# Validates the docker-compose.yaml declarative configuration against the
# specification requirements. Uses Python yaml module for structured parsing.
#
# Requirements: 3.5, 9.1, 9.2, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7
# =============================================================================

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

# --- Setup / Teardown --------------------------------------------------------

setup() {
    COMPOSE_FILE="${BATS_TEST_DIRNAME}/../docker-compose.yaml"
    # Ensure docker-compose.yaml exists
    [ -f "${COMPOSE_FILE}" ] || skip "docker-compose.yaml not found"

    # Check Python3 with yaml module is available
    if ! python3 -c "import yaml" 2>/dev/null; then
        skip "Python3 with PyYAML not available"
    fi
}

# --- Helper: query compose file using Python yaml ----------------------------

# query_yaml <python_expression>
#   Loads docker-compose.yaml and evaluates the given Python expression
#   where 'data' is the parsed YAML dict.
query_yaml() {
    local expr="$1"
    python3 -c "
import yaml, sys
with open('${COMPOSE_FILE}', 'r') as f:
    data = yaml.safe_load(f)
svc = data['services']['so100-dev']
result = ${expr}
print(result)
"
}

# query_yaml_raw <full_python_script>
#   Runs a full Python script with 'data' pre-loaded from the compose file.
query_yaml_raw() {
    python3 -c "
import yaml, sys
with open('${COMPOSE_FILE}', 'r') as f:
    data = yaml.safe_load(f)
$1
"
}

# =============================================================================
# Test: Service definition exists with image and container_name
# Requirement: 11.1
# =============================================================================

@test "docker-compose.yaml defines so100-dev service with image and container_name" {
    run query_yaml "'image' in svc and 'container_name' in svc"
    assert_output "True"

    run query_yaml "svc['image']"
    assert_output --partial "so100-all-in-one"

    run query_yaml "svc['container_name']"
    assert_output "so100-dev"
}

# =============================================================================
# Test: All six environment variables present with correct defaults
# Requirement: 11.2
# =============================================================================

@test "docker-compose.yaml has NVIDIA_VISIBLE_DEVICES with default 'all'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if 'NVIDIA_VISIBLE_DEVICES' in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}'
assert ':-all' in found[0] or 'all}' in found[0], f'Default not all: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has NVIDIA_DRIVER_CAPABILITIES with default 'all'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if 'NVIDIA_DRIVER_CAPABILITIES' in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}'
assert ':-all' in found[0] or 'all}' in found[0], f'Default not all: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has DISPLAY with default ':0'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if e.startswith('DISPLAY=') or '- DISPLAY' in e]
# Handle list of strings format
found = [e for e in env if 'DISPLAY' in e and 'DRIVER' not in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}: {found}'
assert ':-:0' in found[0] or ':0}' in found[0], f'Default not :0: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has ROS_DOMAIN_ID with default '0'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if 'ROS_DOMAIN_ID' in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}'
assert ':-0}' in found[0], f'Default not 0: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has AUTO_START with default '0'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if 'AUTO_START' in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}'
assert ':-0}' in found[0], f'Default not 0: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has SKIP_GPU_CHECK with default '0'" {
    run query_yaml_raw "
env = svc['environment']
found = [e for e in env if 'SKIP_GPU_CHECK' in e]
assert len(found) == 1, f'Expected 1 match, got {len(found)}'
assert ':-0}' in found[0], f'Default not 0: {found[0]}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml has exactly six environment variables" {
    run query_yaml "len(svc['environment'])"
    assert_output "6"
}

# =============================================================================
# Test: GPU reservation with correct capabilities
# Requirements: 2.6, 11.5
# =============================================================================

@test "docker-compose.yaml has NVIDIA GPU device reservation" {
    run query_yaml_raw "
devices = svc['deploy']['resources']['reservations']['devices']
assert len(devices) >= 1, 'No device reservations found'
nvidia_dev = devices[0]
assert nvidia_dev.get('driver') == 'nvidia', f'Driver is not nvidia: {nvidia_dev.get(\"driver\")}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml GPU reservation has gpu, compute, utility capabilities" {
    run query_yaml_raw "
devices = svc['deploy']['resources']['reservations']['devices']
nvidia_dev = devices[0]
caps = nvidia_dev.get('capabilities', [])
for required in ['gpu', 'compute', 'utility']:
    assert required in caps, f'Missing capability: {required}. Found: {caps}'
print('PASS')
"
    assert_output "PASS"
}

# =============================================================================
# Test: Health check parameters match specification
# Requirements: 9.1, 9.2
# =============================================================================

@test "docker-compose.yaml healthcheck test runs 'ros2 topic list'" {
    run query_yaml_raw "
hc = svc['healthcheck']
test = hc['test']
# test can be a list like ['CMD', 'ros2', 'topic', 'list'] or a string
if isinstance(test, list):
    cmd_str = ' '.join(test)
else:
    cmd_str = test
assert 'ros2' in cmd_str and 'topic' in cmd_str and 'list' in cmd_str, f'Health test not ros2 topic list: {test}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml healthcheck interval is 30s" {
    run query_yaml "svc['healthcheck']['interval']"
    assert_output "30s"
}

@test "docker-compose.yaml healthcheck timeout is 10s" {
    run query_yaml "svc['healthcheck']['timeout']"
    assert_output "10s"
}

@test "docker-compose.yaml healthcheck start_period is 15s" {
    run query_yaml "svc['healthcheck']['start_period']"
    assert_output "15s"
}

@test "docker-compose.yaml healthcheck retries is 3" {
    run query_yaml "svc['healthcheck']['retries']"
    assert_output "3"
}

# =============================================================================
# Test: Volume mounts correct
# Requirements: 5.2, 6.2, 11.6
# =============================================================================

@test "docker-compose.yaml mounts project root to /workspace:rw" {
    run query_yaml_raw "
volumes = svc['volumes']
found = any('.:/workspace:rw' in v or '.:/workspace' in v for v in volumes)
assert found, f'Volume .:/workspace:rw not found in: {volumes}'
print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml mounts /tmp/.X11-unix:/tmp/.X11-unix:rw" {
    run query_yaml_raw "
volumes = svc['volumes']
found = any('/tmp/.X11-unix:/tmp/.X11-unix:rw' in v or '/tmp/.X11-unix:/tmp/.X11-unix' in v for v in volumes)
assert found, f'Volume /tmp/.X11-unix not found in: {volumes}'
print('PASS')
"
    assert_output "PASS"
}

# =============================================================================
# Test: network_mode, ipc, stdin_open, tty, working_dir correct
# Requirements: 7.2, 11.3, 11.4, 11.7
# =============================================================================

@test "docker-compose.yaml network_mode is host" {
    run query_yaml "svc['network_mode']"
    assert_output "host"
}

@test "docker-compose.yaml ipc is host" {
    run query_yaml "svc['ipc']"
    assert_output "host"
}

@test "docker-compose.yaml stdin_open is true" {
    run query_yaml "svc['stdin_open']"
    assert_output "True"
}

@test "docker-compose.yaml tty is true" {
    run query_yaml "svc['tty']"
    assert_output "True"
}

@test "docker-compose.yaml working_dir is /workspace" {
    run query_yaml "svc['working_dir']"
    assert_output "/workspace"
}

# =============================================================================
# Test: Devices list includes /dev/ttyUSB0 and /dev/ttyACM0
# Requirement: 3.5
# =============================================================================

@test "docker-compose.yaml declares /dev/ttyUSB0 device" {
    run query_yaml_raw "
# Devices may be in the hardware profile service that extends so100-dev
hw_svc = data['services'].get('so100-hardware', {})
devices = hw_svc.get('devices', svc.get('devices', []))
if not devices:
    # Fall back to checking the whole file for ttyUSB0
    import re
    with open('${COMPOSE_FILE}', 'r') as f:
        content = f.read()
    assert '/dev/ttyUSB0' in content, 'Device /dev/ttyUSB0 not declared anywhere in compose file'
    print('PASS')
else:
    device_str = ' '.join(str(d) for d in devices)
    assert '/dev/ttyUSB0' in device_str or 'ttyUSB0' in device_str, f'/dev/ttyUSB0 not in devices: {devices}'
    print('PASS')
"
    assert_output "PASS"
}

@test "docker-compose.yaml declares /dev/ttyACM0 device" {
    run query_yaml_raw "
# Devices may be in the hardware profile service that extends so100-dev
hw_svc = data['services'].get('so100-hardware', {})
devices = hw_svc.get('devices', svc.get('devices', []))
if not devices:
    # Fall back to checking the whole file for ttyACM0
    with open('${COMPOSE_FILE}', 'r') as f:
        content = f.read()
    assert '/dev/ttyACM0' in content, 'Device /dev/ttyACM0 not declared anywhere in compose file'
    print('PASS')
else:
    device_str = ' '.join(str(d) for d in devices)
    assert '/dev/ttyACM0' in device_str or 'ttyACM0' in device_str, f'/dev/ttyACM0 not in devices: {devices}'
    print('PASS')
"
    assert_output "PASS"
}
