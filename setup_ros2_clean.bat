@echo off
REM Clean ROS2 environment setup - removes pixi interference

echo Setting up clean ROS2 environment...

REM Remove pixi from PATH
set "PATH=%PATH:C:\Users\croqu\.pixi\bin;=%"
set "PATH=%PATH:C:\pixi_ws\.pixi\envs\default=%"
set "PATH=%PATH:C:\pixi_ws\.pixi\envs\default\Scripts;=%"
set "PATH=%PATH:C:\pixi_ws\.pixi\envs\default\Library\bin;=%"

REM Clear Python-related environment variables that pixi might have set
set PYTHONPATH=
set PYTHONHOME=

REM Setup Visual Studio environment (needed for building)
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1

REM Add Python 3.10 to PATH first
set "PATH=C:\Users\croqu\AppData\Local\Programs\Python\Python310;C:\Users\croqu\AppData\Local\Programs\Python\Python310\Scripts;%PATH%"

REM Add ROS2 bin directories to PATH explicitly (for DLL loading)
set "PATH=C:\opt\ros\ros2-windows\bin;C:\opt\ros\ros2-windows\Lib\site-packages;%PATH%"

REM Setup ROS2
call C:\opt\ros\ros2-windows\local_setup.bat

echo.
echo ============================================
echo ROS2 Environment Ready (pixi disabled)
echo ============================================
echo.
echo Test with: ros2 --version
echo.
echo Available mock testing commands:
echo   ros2 launch so101_bringup follower.launch.py hardware_type:=mock
echo   ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false
echo.
