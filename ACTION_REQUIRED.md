# ⚠️ ACTION REQUIRED - ROS2 Setup Status

## Current Status

**System Check (Just Verified):**
- ✅ WSL2 Ubuntu 20.04.6 LTS installed and working
- ❌ **ROS2 NOT installed yet** (this is the missing piece!)
- ⚠️ Workspace has old Windows build artifacts (should be rebuilt in WSL)

---

## What You Need to Do NOW

### Quick Start (5 commands):

Open Ubuntu terminal (Windows Start Menu → Ubuntu, or run `wsl -d Ubuntu`):

```bash
# 1. Navigate to workspace
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"

# 2. Run the installation script (this installs ROS2 + builds workspace)
chmod +x install_ros2_manual.sh
./install_ros2_manual.sh

# 3. After installation completes (20-30 min), reload shell
source ~/.bashrc

# 4. Verify everything works
./test_ros2_packages.sh

# 5. Test a launch file
ros2 launch so101_bringup follower.launch.py hardware_type:=mock
```

---

## Why ROS2 Isn't Installed Yet

The automated `setup_wsl.bat` script may have:
1. Not been run yet, OR
2. Failed due to interactive prompts requiring manual password entry, OR  
3. Timed out waiting for user input

**Solution:** Run the manual installation script above (it handles all of this properly).

---

## What the Installation Will Do

The `install_ros2_manual.sh` script will:

1. ✅ Update Ubuntu packages
2. ✅ Add ROS2 Foxy repository  
3. ✅ Install ROS2 Foxy Desktop (~2GB download)
4. ✅ Install xacro, MoveIt, Gazebo, ros2_control, etc.
5. ✅ Initialize rosdep
6. ✅ Install workspace dependencies
7. ✅ Build all 15+ ROS2 packages in the workspace
8. ✅ Configure ~/.bashrc to auto-load ROS2

**Total time: 20-30 minutes**  
**Internet required: Yes** (downloading ROS2 packages)  
**Disk space needed: ~3GB**

---

## After Installation Success

You'll be able to run all 42 launch files in mock mode:

### SO-101 Launch Files (Mock Mode)

```bash
# Follower arm only
ros2 launch so101_bringup follower.launch.py hardware_type:=mock

# Teleoperation (leader + follower, no cameras)
ros2 launch so101_bringup teleop.launch.py hardware_type:=mock use_cameras:=false

# URDF visualization
ros2 launch so101_description display.launch.py

# MoveIt motion planning demo
ros2 launch so101_moveit_config demo.launch.py

# Recording session (mock)
ros2 launch so101_bringup recording_session.launch.py hardware_type:=mock use_cameras:=false

# Inference demo (mock, no actual inference)
ros2 launch so101_bringup inference.launch.py hardware_type:=mock use_inference:=false
```

### SO-ARM-100 Launch Files (Simulation/Mock)

```bash
# Fake hardware with RViz
ros2 launch so_arm_100_bringup hardware.launch.py use_fake_hardware:=true rviz:=false

# Gazebo simulation
ros2 launch so_arm_100_bringup sim.launch.py sim_backend:=gazebo

# Interactive joint GUI
ros2 launch so_arm_100_description joint_state_pub_gui.launch.py

# MoveIt demo
ros2 launch so_arm_100_moveit_config demo.launch.py
```

**Note:** RViz and Gazebo GUI windows require X server (VcXsrv) on Windows. For now, test without GUIs using `rviz:=false`.

---

## Verification Checklist

After running `./test_ros2_packages.sh`, you should see:

- ✅ ROS2 CLI available
- ✅ xacro installed
- ✅ robot_state_publisher installed
- ✅ moveit installed
- ✅ gazebo_ros installed
- ✅ All so101_* packages found
- ✅ All so_arm_100_* packages found
- ✅ episode_recorder found
- ✅ Launch files exist

**Expected result:** "All tests passed! ✓"

---

## Troubleshooting

### If installation script fails:

1. **Check internet connection** - ROS2 packages are downloaded from the internet

2. **Check disk space:**
   ```bash
   df -h /
   # Should have at least 5GB free
   ```

3. **Run installation steps manually** - See `MANUAL_SETUP_STEPS.md`

4. **Check for error messages** - The script will show what failed

### If build fails:

```bash
# Clean old Windows build artifacts
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong"
rm -rf build install log

# Source ROS2
source /opt/ros/foxy/setup.bash

# Rebuild
colcon build --symlink-install
```

### If packages not found after build:

```bash
# Source both ROS2 and workspace
source /opt/ros/foxy/setup.bash
source install/setup.bash

# Or just reload shell (if .bashrc is configured)
source ~/.bashrc
```

---

## Files You Have

| File | Purpose | When to Use |
|------|---------|-------------|
| `install_ros2_manual.sh` | **RUN THIS NOW** | Main installation script |
| `test_ros2_packages.sh` | Verification tests | After installation |
| `MANUAL_SETUP_STEPS.md` | Step-by-step guide | Detailed instructions |
| `WSL_ROS2_GUIDE.md` | Comprehensive reference | Ongoing reference |
| `ACTION_REQUIRED.md` | This file | Current status |
| `setup_wsl_ros2.sh` | Original auto script | Alternative method |
| `setup_wsl.bat` | Windows launcher | Windows shortcut |

---

## Ready to Start?

### Copy-paste this into WSL Ubuntu terminal:

```bash
cd "/mnt/c/Users/croqu/Downloads/git_minh/Nouveau dossier/leRobot_EuroTechxHongKong" && chmod +x install_ros2_manual.sh test_ros2_packages.sh && ./install_ros2_manual.sh
```

**That's it!** The script will guide you through the rest.

---

## Expected Timeline

1. **Script preparation:** 30 seconds  
2. **System updates:** 2-3 minutes  
3. **ROS2 installation:** 10-15 minutes  
4. **Additional packages:** 3-5 minutes  
5. **Workspace build:** 5-10 minutes  
6. **Configuration:** 1 minute  

**Total: ~20-30 minutes**

The script will show progress for each step.

---

## What to Do After Success

1. ✅ Run verification: `./test_ros2_packages.sh`
2. ✅ Test launch file: `ros2 launch so101_bringup follower.launch.py hardware_type:=mock`
3. ✅ Explore other launch files
4. ✅ Celebrate! 🎉

---

## Need Help?

If the installation fails or you encounter errors:

1. **Read the error message** - it usually tells you what's wrong
2. **Check `MANUAL_SETUP_STEPS.md`** - has troubleshooting steps
3. **Run verification:** `./test_ros2_packages.sh` - shows what's missing
4. **Ask for help** - provide the error message

---

## Bottom Line

**You need to run ONE command:**

```bash
./install_ros2_manual.sh
```

**Location:** In WSL Ubuntu, in the workspace directory

**Time:** 20-30 minutes

**Result:** Fully working ROS2 with all 42 launch files ready to test!

🚀 **Let's do this!**
