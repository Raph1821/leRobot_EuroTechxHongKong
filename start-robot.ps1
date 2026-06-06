# ===================================================================
# SO-100/SO-101 Robot Arm - Windows Startup Script
# ===================================================================
# This script starts the robot arm interface on Windows
# Works with real hardware (COM3) or fake hardware for testing
# ===================================================================

param(
    [switch]$FakeHardware = $false,
    [string]$SerialPort = "COM3"
)

Write-Host "=== SO-100/SO-101 Robot Arm Startup ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
$dockerRunning = docker info 2>&1 | Out-Null; $?
if (-not $dockerRunning) {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Stop any existing containers
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker compose down 2>&1 | Out-Null

# Start the container
Write-Host "Starting ROS2 container..." -ForegroundColor Green
docker compose up -d

# Wait for container to be ready
Write-Host "Waiting for container to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Launch hardware interface
if ($FakeHardware) {
    Write-Host "Launching with FAKE HARDWARE (simulation mode)..." -ForegroundColor Cyan
    docker exec -d so100-dev bash -c "source /workspace/install/setup.bash && ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true"
} else {
    Write-Host "Launching with REAL HARDWARE on $SerialPort..." -ForegroundColor Cyan
    Write-Host "NOTE: Make sure the robot is connected to $SerialPort" -ForegroundColor Yellow
    
    # Map COM port to Linux device path
    # COM3 -> /dev/ttyS3, COM4 -> /dev/ttyS4, etc.
    $portNum = $SerialPort.Replace("COM", "")
    $linuxPort = "/dev/ttyS$portNum"
    
    docker exec -d so100-dev bash -c "source /workspace/install/setup.bash && ros2 launch so_arm_100_bringup hardware.launch.py serial_port:=$linuxPort use_fake_hardware:=false"
}

Start-Sleep -Seconds 8

# Launch WebSocket bridge
Write-Host "Starting WebSocket bridge on port 9090..." -ForegroundColor Green
docker exec -d so100-dev bash -c "source /workspace/install/setup.bash && ros2 run so_arm_100_web_bridge websocket_bridge"

Start-Sleep -Seconds 3

# Start web server
Write-Host "Starting web interface on port 8080..." -ForegroundColor Green
docker exec -d so100-dev bash -c "cd /workspace/web_static && python3 -m http.server 8080"

Start-Sleep -Seconds 2

# Check if services are running
Write-Host ""
Write-Host "Checking services..." -ForegroundColor Yellow
$processes = docker exec so100-dev bash -c "ps aux | grep -E 'ros2|websocket|http.server' | grep -v grep" 2>&1

if ($processes -match "ros2_control_node") {
    Write-Host "✓ ROS2 controllers running" -ForegroundColor Green
} else {
    Write-Host "✗ ROS2 controllers NOT running" -ForegroundColor Red
}

if ($processes -match "websocket_bridge") {
    Write-Host "✓ WebSocket bridge running" -ForegroundColor Green
} else {
    Write-Host "✗ WebSocket bridge NOT running" -ForegroundColor Red
}

if ($processes -match "http.server") {
    Write-Host "✓ Web server running" -ForegroundColor Green
} else {
    Write-Host "✗ Web server NOT running" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Robot Interface Ready! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Web Interface: " -NoNewline -ForegroundColor Yellow
Write-Host "http://localhost:8080" -ForegroundColor Green
Write-Host "WebSocket:     " -NoNewline -ForegroundColor Yellow
Write-Host "ws://localhost:9090" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to view logs or close this window" -ForegroundColor Gray
Write-Host ""

# Show live logs
docker logs -f so100-dev
