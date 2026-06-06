# 🚀 Next Steps - ROS2 Setup in WSL2

## What We've Done

✅ Identified that your Windows ROS2 installation has compatibility issues  
✅ Installed Python 3.10 and fixed ROS2 scripts  
✅ Discovered WSL2 with Ubuntu 20.04 is already installed  
✅ Created automated setup scripts for WSL2 + ROS2  

## What You Need to Do Now

### Step 1: Run the Automated Setup

**Option A: Double-click** `setup_wsl.bat` in Windows Explorer

**Option B: From Command Prompt:**
```batch
cd "C:\Users\croqu\Downloads\git_minh\Nouveau dossier\leRobot_EuroTechxHongKong"
setup_wsl.bat
```

**Option C: Manually in WSL:**
```batch
wsl -d Ubuntu
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
./setup_wsl_ros2.sh
```

**What this does:**
- Installs ROS2 Foxy in your WSL Ubuntu
- Installs all ROS2 packages (xacro, MoveIt, Gazebo, controllers, etc.)
- Installs Python dependencies
- Builds the entire workspace
- Configures your environment

**Time:** 20-30 minutes (mostly automated downloads and compilation)

**You will be prompted for your Ubuntu password once at the beginning.**

---

### Step 2: After Setup Completes

Open a WSL terminal:
```batch
wsl -d Ubuntu
```

Test ROS2:
```bash
ros2 --version
# Should show: ros2 cli version 0.9.x
```

---

### Step 3: Test Launch Files

Try these commands to test without hardware:

```bash
# SO-101 follower arm (mock mode)
ros2 launch so101_bringup follower.launch.py hardware_type:=mock

# SO-101 teleoperation (mock mode, no cameras)
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false

# SO-ARM-100 with fake hardware
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=true

# MoveIt demo
ros2 launch so101_moveit_config demo.launch.py
```

---

## Files Created

| File | Purpose |
|------|---------|
| `setup_wsl_ros2.sh` | Automated WSL/ROS2 setup script |
| `setup_wsl.bat` | Windows launcher for setup script |
| `WSL_ROS2_GUIDE.md` | Comprehensive guide for using WSL + ROS2 |
| `NEXT_STEPS.md` | This file - what to do next |
| `ROS2_SETUP_GUIDE.md` | Troubleshooting for Windows ROS2 (reference) |
| `setup_ros2_clean.bat` | Windows ROS2 env script (deprecated - use WSL) |

---

## Troubleshooting

### Setup script fails during apt install
**Solution:** Run in WSL manually:
```bash
wsl -d Ubuntu
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
sudo apt update
sudo apt upgrade -y
./setup_wsl_ros2.sh
```

### "Permission denied" when running script
**Solution:**
```bash
chmod +x setup_wsl_ros2.sh
./setup_wsl_ros2.sh
```

### Build fails with dependency errors
**Solution:**
```bash
source /opt/ros/foxy/setup.bash
rosdep update
rosdep install --from-paths . --ignore-src -r -y
colcon build --symlink-install
```

### Can't see RViz/Gazebo windows
**Solution:** Install VcXsrv on Windows (see WSL_ROS2_GUIDE.md)

---

## Quick Command Reference

### Open WSL
```batch
wsl -d Ubuntu
```

### Navigate to workspace
```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
```

### Source ROS2 (if not automatic)
```bash
source /opt/ros/foxy/setup.bash
source install/setup.bash
```

### Rebuild workspace
```bash
colcon build --symlink-install
```

---

## Expected Output After Successful Setup

When you run `ros2 --version`, you should see:
```
ros2 cli version 0.9.x
ros2 api version 0.9.x
```

When you run `ros2 pkg list | grep so101`, you should see:
```
so101_bringup
so101_camera_calibration
so101_description
so101_inference
so101_kinematics
so101_kinematics_msgs
so101_moveit_config
so101_teleop
```

---

## Support & Documentation

- **Full guide:** `WSL_ROS2_GUIDE.md`
- **ROS2 Foxy docs:** https://docs.ros.org/en/foxy/
- **Workspace README:** `README.md`

---

## Why WSL Instead of Windows?

| Windows ROS2 Issues | WSL2 Advantages |
|---------------------|-----------------|
| ❌ Missing packages (xacro, etc.) | ✅ All packages available |
| ❌ Python version conflicts | ✅ Clean environment |
| ❌ DLL dependency hell | ✅ Native Linux libraries |
| ❌ Limited community support | ✅ Excellent support |
| ❌ Complex troubleshooting | ✅ Standard Linux setup |

**Bottom line:** WSL2 is the recommended way to run ROS2 on Windows.

---

## Ready?

Run this to start:
```batch
setup_wsl.bat
```

Or if you prefer manual control:
```batch
wsl -d Ubuntu
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
./setup_wsl_ros2.sh
```

**Let me know if you encounter any issues during setup!** 🚀
