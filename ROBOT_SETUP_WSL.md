# Robot Setup Guide — SO-101 on WSL Ubuntu 22.04

This guide gets the two SO-101 arms (leader + follower) moving via ROS2 Humble
on WSL, so you can do teleoperation and record imitation-learning demos.

> **Time estimate:** ~2-3 hours including downloads and first build.
> **Goal milestones (in order):**
> 1. ROS2 Humble installed
> 2. USB arms visible inside WSL
> 3. One arm moves via a joint command
> 4. Leader controls follower (teleop)
> 5. Record demonstrations

---

## Part 1 — Install ROS2 Humble

In your **WSL Ubuntu 22.04** terminal:

```bash
# Set locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Add the ROS2 apt repository
sudo apt install -y software-properties-common curl
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
    | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble (desktop = includes RViz, demos)
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools

# Source ROS2 automatically in every new terminal
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Verify:
```bash
ros2 --help        # should print help, not "command not found"
echo $ROS_DISTRO   # should print: humble
```

---

## Part 2 — Forward the USB arms into WSL (usbipd)

WSL2 can't see USB devices by default. You bind them from Windows.

### On Windows (PowerShell as Administrator):

```powershell
# Install usbipd (one time)
winget install usbipd

# List USB devices — find the two SO-101 arms (look for "USB Serial" / CH340 / FTDI)
usbipd list
```

You'll see lines with BUSID like `2-1`, `2-2`. Identify the two arm adapters.

```powershell
# Bind each arm (one time per device, use the real BUSIDs)
usbipd bind --busid 2-1
usbipd bind --busid 2-2

# Attach them to WSL (repeat each time you replug or reboot)
usbipd attach --wsl --busid 2-1
usbipd attach --wsl --busid 2-2
```

### Back in WSL — verify the arms appear:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
# You should see two devices, e.g. /dev/ttyACM0 and /dev/ttyACM1
sudo chmod 666 /dev/ttyACM0 /dev/ttyACM1
```

> **Tip:** create stable names so leader/follower don't swap.
> For the hackathon, just note which BUSID is which arm and attach in the same order.

---

## Part 3 — Build the workspace (includes the feetech driver)

The servo driver (`feetech_ros2_driver`) is an external dependency — it is NOT
in this repo. We clone and build it alongside our packages.

```bash
# Create a ROS2 workspace
mkdir -p ~/carebot_ws/src
cd ~/carebot_ws/src

# Symlink (or copy) this repo's ROS2 packages into the workspace.
# Adjust the path to where the repo lives in WSL (see note below).
ln -s /mnt/c/Users/phamq/OneDrive/"Máy tính"/hack/main/leRobot_EuroTechxHongKong ./carebot

# Clone the external Feetech servo driver
git clone --branch feat/joint-config-and-calibration \
    https://github.com/legalaspro/feetech_ros2_driver.git

cd ~/carebot_ws

# Install dependencies
sudo apt install -y python3-rosdep
sudo rosdep init 2>/dev/null; rosdep update
rosdep install --from-paths src --ignore-src -r -y

# Build
colcon build --symlink-install
source install/setup.bash
```

> **Performance note:** building from `/mnt/c/...` (the Windows filesystem) is slow.
> For best results, COPY the repo into the WSL filesystem instead of symlinking:
> ```bash
> cp -r /mnt/c/Users/phamq/OneDrive/"Máy tính"/hack/main/leRobot_EuroTechxHongKong ~/carebot_ws/src/carebot
> ```

---

## Part 4 — Milestone: move ONE arm (follower)

```bash
# Terminal 1 — launch the follower with real hardware
ros2 launch so101_bringup follower.launch.py \
    hardware_type:=real usb_port:=/dev/ttyACM0
```

```bash
# Terminal 2 — send a joint position command (6 joints, radians)
# Order: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper
source ~/carebot_ws/install/setup.bash
ros2 topic pub --once /follower/forward_controller/commands \
    std_msgs/Float64MultiArray "{data: [0.2, 0.0, 0.0, 0.0, 0.0, 0.0]}"
```

If the arm moves → **hardware control works.** This is the foundation.

> If it doesn't move: check `ros2 topic echo /follower/joint_states` shows data
> (confirms the servos are read), and that the USB port + chmod are correct.

---

## Part 5 — Milestone: leader controls follower (teleop)

```bash
# Terminal 1 — follower (real)
ros2 launch so101_bringup follower.launch.py hardware_type:=real usb_port:=/dev/ttyACM0

# Terminal 2 — leader (real, read-only positions)
ros2 launch so101_bringup leader.launch.py usb_port:=/dev/ttyACM1

# Terminal 3 — teleop relay (leader joint_states → follower commands)
ros2 launch so101_teleop teleop.launch.py
```

Now physically move the leader arm → the follower mirrors it. This is the
data-collection setup for imitation learning.

---

## Part 6 — Milestone: record demonstrations

```bash
# With teleop running, record episodes
ros2 launch so101_bringup follower_recording.launch.py
# (see episode_recorder/ for output location and controls)
```

These recordings become training data (convert with `minh/training/hdf5_to_lerobot.py`).

---

## Part 7 — Scripted bottle rotation (for medicine scanning)

Once one arm moves, you can script poses to rotate a bottle in front of the
clear webcam. Use the kinematics service:

```bash
# Terminal 1 — follower
ros2 launch so101_bringup follower.launch.py hardware_type:=real usb_port:=/dev/ttyACM0

# Terminal 2 — kinematics (IK) node
ros2 run so101_kinematics cartesian_motion_node

# Terminal 3 — call /go_to_pose with target poses (rotate the wrist between calls)
ros2 service call /go_to_pose so101_kinematics_msgs/srv/GoToPose \
    "{target: {header: {frame_id: 'follower/base_link'}, pose: {position: {x: 0.2, y: 0.0, z: 0.15}, orientation: {w: 1.0}}}}"
```

A small Python script can loop: go to pose → wait for OCR result → rotate wrist →
repeat until the medicine name + expiration are both detected.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `usbipd: command not found` | Install from Windows: `winget install usbipd` |
| Arms not in `/dev/` after attach | Re-run `usbipd attach`; check `dmesg | tail` in WSL |
| `feetech_ros2_driver not found` | You skipped the git clone in Part 3 |
| Permission denied on /dev/ttyACM0 | `sudo chmod 666 /dev/ttyACM0` |
| Arm jerks / wrong direction | Calibration mismatch — check `so101_bringup/config/hardware/*.json` |
| Build errors on /mnt/c | Copy repo into WSL filesystem (~/carebot_ws), don't symlink |
| `rosdep: command not found` | `sudo apt install python3-rosdep` |

---

## What runs where (recap)

| Task | Where | Needs ROS2? |
|------|-------|-------------|
| Medicine ID + expiration (webcam OCR) | Windows (conda) | No |
| Patrol + fall detection (wrist cam) | Windows (conda) | No |
| LLM interaction | Windows (conda) | No |
| Web dashboard | Windows (Node.js) | No |
| Arm movement / teleop / recording | **WSL (ROS2)** | **Yes** |
| Scripted bottle rotation (IK) | **WSL (ROS2)** | **Yes** |
