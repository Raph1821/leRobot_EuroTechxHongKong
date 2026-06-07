# Robot Web Control Launcher
# Starts all required services for web-based robot control

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Robot Web Control System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if ROS2 is sourced
if (-not $env:ROS_DISTRO) {
    Write-Host "[ERROR] ROS2 not sourced. Please run:" -ForegroundColor Red
    Write-Host "  source /opt/ros/humble/setup.bash" -ForegroundColor Yellow
    Write-Host "  source install/setup.bash" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] ROS2 Distribution: $env:ROS_DISTRO" -ForegroundColor Green
Write-Host ""

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Check for required commands
Write-Host "[INFO] Checking dependencies..." -ForegroundColor Cyan

if (-not (Test-Command "ros2")) {
    Write-Host "[ERROR] ros2 command not found" -ForegroundColor Red
    exit 1
}

if (-not (Test-Command "node")) {
    Write-Host "[ERROR] Node.js not found. Please install Node.js" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] All dependencies found" -ForegroundColor Green
Write-Host ""

# Menu
Write-Host "Select launch mode:" -ForegroundColor Cyan
Write-Host "  1. Full System (Simulation + Bridge + Web)" -ForegroundColor White
Write-Host "  2. Bridge Only (robot already running)" -ForegroundColor White
Write-Host "  3. Web Frontend Only (bridge already running)" -ForegroundColor White
Write-Host "  4. Simulation Only" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "[INFO] Starting Full System..." -ForegroundColor Cyan
        Write-Host ""
        
        # Start simulation
        Write-Host "[1/3] Launching robot simulation..." -ForegroundColor Yellow
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; ros2 launch so_arm_100_bringup sim.launch.py" -WindowStyle Normal
        
        Start-Sleep -Seconds 5
        
        # Start WebSocket bridge
        Write-Host "[2/3] Launching WebSocket bridge..." -ForegroundColor Yellow
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; ros2 launch so_arm_100_bringup web_control.launch.py" -WindowStyle Normal
        
        Start-Sleep -Seconds 3
        
        # Start web frontend
        Write-Host "[3/3] Launching web frontend..." -ForegroundColor Yellow
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\webapp'; npm run dev" -WindowStyle Normal
        
        Start-Sleep -Seconds 2
        
        Write-Host ""
        Write-Host "[SUCCESS] All services started!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Access the web interface at:" -ForegroundColor Cyan
        Write-Host "  http://localhost:3000" -ForegroundColor White
        Write-Host ""
        Write-Host "WebSocket Bridge:" -ForegroundColor Cyan
        Write-Host "  ws://localhost:9090" -ForegroundColor White
    }
    
    "2" {
        Write-Host ""
        Write-Host "[INFO] Starting WebSocket Bridge..." -ForegroundColor Cyan
        Write-Host ""
        
        ros2 launch so_arm_100_bringup web_control.launch.py
    }
    
    "3" {
        Write-Host ""
        Write-Host "[INFO] Starting Web Frontend..." -ForegroundColor Cyan
        Write-Host ""
        
        Set-Location "$PSScriptRoot\webapp"
        npm run dev
    }
    
    "4" {
        Write-Host ""
        Write-Host "[INFO] Starting Simulation..." -ForegroundColor Cyan
        Write-Host ""
        
        ros2 launch so_arm_100_bringup sim.launch.py
    }
    
    default {
        Write-Host "[ERROR] Invalid choice" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Control Instructions" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open http://localhost:3000 in your browser" -ForegroundColor White
Write-Host "2. Login as Nurse or Doctor" -ForegroundColor White
Write-Host "3. Navigate to 'Control' page" -ForegroundColor White
Write-Host "4. Click 'Teleop' tab" -ForegroundColor White
Write-Host "5. Choose control mode:" -ForegroundColor White
Write-Host "   - Keyboard: Real-time velocity control" -ForegroundColor Gray
Write-Host "   - Cartesian: Position-based IK control" -ForegroundColor Gray
Write-Host "   - Recorder: Episode recording/replay" -ForegroundColor Gray
Write-Host ""
Write-Host "See ROBOT_WEB_CONTROL.md for full documentation" -ForegroundColor Cyan
Write-Host ""
