@echo off
echo ========================================
echo Setting up ROS2 in WSL2 Ubuntu
echo ========================================
echo.
echo This will:
echo   1. Install ROS2 Foxy in your WSL Ubuntu
echo   2. Install all dependencies
echo   3. Build the workspace
echo.
echo This may take 20-30 minutes depending on your internet speed.
echo You will be prompted for your Ubuntu password.
echo.
pause

echo.
echo Starting WSL setup...
echo.

wsl -d Ubuntu bash -c "cd /mnt/c/Users/croqu/Downloads/git_minh/Nouveau\ dossier/leRobot_EuroTechxHongKong && chmod +x setup_wsl_ros2.sh && ./setup_wsl_ros2.sh"

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To test ROS2, run:
echo   wsl -d Ubuntu
echo.
echo Then in Ubuntu terminal:
echo   ros2 --version
echo   ros2 launch so101_bringup follower.launch.py hardware_type:=mock
echo.
pause
