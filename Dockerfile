# =============================================================================
# SO-100 + SO-101 All-in-One Development Environment
# Base: ROS2 Jazzy (Ubuntu 24.04) + Isaac Sim support + feetech_ros2_driver
#
# Usage:
#   docker build -t so100-all-in-one .
#   docker run --rm -it --gpus all --network host \
#     --device /dev/ttyUSB0:/dev/ttyUSB0 \
#     -v $(pwd):/workspace \
#     so100-all-in-one
# =============================================================================

FROM osrf/ros:jazzy-desktop AS base

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ─────────────────────────────────────────────────────────────────────────────
# System dependencies
# ─────────────────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        curl \
        wget \
        python3-pip \
        python3-colcon-common-extensions \
        python3-rosdep \
        python3-vcstool \
        python3-setuptools \
        python3-dev \
        libyaml-cpp-dev \
        libssl-dev \
        usbutils \
        udev \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# ROS2 Jazzy packages (so101 + so100 dependencies)
# ─────────────────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-controller-manager \
        ros-jazzy-joint-state-broadcaster \
        ros-jazzy-joint-trajectory-controller \
        ros-jazzy-gripper-controllers \
        ros-jazzy-robot-state-publisher \
        ros-jazzy-joint-state-publisher \
        ros-jazzy-joint-state-publisher-gui \
        ros-jazzy-xacro \
        ros-jazzy-ros2-control \
        ros-jazzy-ros2-controllers \
        ros-jazzy-rviz2 \
        ros-jazzy-tf2-ros \
        ros-jazzy-tf2-tools \
        ros-jazzy-cv-bridge \
        ros-jazzy-rosbag2 \
        ros-jazzy-rosbag2-cpp \
        ros-jazzy-rosbag2-storage \
        ros-jazzy-rosbag2-storage-mcap \
        ros-jazzy-rosbag2-py \
        ros-jazzy-moveit \
        ros-jazzy-moveit-ros-move-group \
        ros-jazzy-moveit-planners \
        ros-jazzy-moveit-simple-controller-manager \
        ros-jazzy-moveit-configs-utils \
        ros-jazzy-moveit-ros-visualization \
        ros-jazzy-usb-cam \
        ros-jazzy-camera-ros \
        ros-jazzy-ros-gz-bridge \
        ros-jazzy-ros-gz-sim \
        ros-jazzy-ros-gz-image \
        ros-jazzy-gz-ros2-control \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Python dependencies (websockets, lerobot tooling, rerun, etc.)
# ─────────────────────────────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
        websockets \
        numpy \
        rerun-sdk \
        gradio \
        pyyaml \
        pyserial \
        hypothesis \
        pytest \
        pytest-asyncio

# ─────────────────────────────────────────────────────────────────────────────
# Node.js for web interface build
# ─────────────────────────────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────────────────────
# Workspace layout
# ─────────────────────────────────────────────────────────────────────────────
ENV ROS_WS=/workspace
WORKDIR ${ROS_WS}

# ─────────────────────────────────────────────────────────────────────────────
# Clone feetech_ros2_driver (git submodule in so101 repo)
# ─────────────────────────────────────────────────────────────────────────────
RUN mkdir -p /workspace/src && \
    git clone --branch feat/joint-config-and-calibration \
        https://github.com/legalaspro/feetech_ros2_driver.git \
        /workspace/src/feetech_ros2_driver

# ─────────────────────────────────────────────────────────────────────────────
# Copy all SO-100 arm packages
# ─────────────────────────────────────────────────────────────────────────────
COPY so_arm_100/ /workspace/src/so_arm_100/
COPY so_arm_100_description/ /workspace/src/so_arm_100_description/
COPY so_arm_100_bringup/ /workspace/src/so_arm_100_bringup/
COPY so_arm_100_moveit_config/ /workspace/src/so_arm_100_moveit_config/
COPY so_arm_100_isaac_sim/ /workspace/src/so_arm_100_isaac_sim/
COPY so_arm_100_web_bridge/ /workspace/src/so_arm_100_web_bridge/

# ─────────────────────────────────────────────────────────────────────────────
# Copy all SO-101 packages (from so101-ros-physical-ai-main)
# These should be placed in the build context or use multi-stage
# ─────────────────────────────────────────────────────────────────────────────
# Note: Copy these from the so101 repo into the Docker build context first,
# or mount them. The Dockerfile expects them at the build context root.
COPY so101_description/ /workspace/src/so101_description/
COPY so101_bringup/ /workspace/src/so101_bringup/
COPY so101_teleop/ /workspace/src/so101_teleop/
COPY so101_moveit_config/ /workspace/src/so101_moveit_config/
COPY so101_kinematics/ /workspace/src/so101_kinematics/
COPY so101_kinematics_msgs/ /workspace/src/so101_kinematics_msgs/
COPY so101_camera_calibration/ /workspace/src/so101_camera_calibration/
COPY so101_inference/ /workspace/src/so101_inference/
COPY episode_recorder/ /workspace/src/episode_recorder/
COPY rosbag_to_lerobot/ /workspace/src/rosbag_to_lerobot/
COPY policy_server/ /workspace/src/policy_server/

# ─────────────────────────────────────────────────────────────────────────────
# Install rosdep dependencies and build workspace
# ─────────────────────────────────────────────────────────────────────────────
RUN rosdep update --rosdistro=jazzy && \
    source /opt/ros/jazzy/setup.bash && \
    rosdep install --from-paths /workspace/src \
        --ignore-src \
        --rosdistro jazzy \
        -y 2>/dev/null || true

# Build all packages (skip Gazebo-dependent ones that need gz_ros2_control)
RUN source /opt/ros/jazzy/setup.bash && \
    cd /workspace && \
    colcon build --symlink-install \
        --cmake-args -DCMAKE_BUILD_TYPE=Release \
        --packages-skip so_arm_100_bringup \
    || true

# Build bringup separately (may fail if gazebo deps missing — that's OK)
RUN source /opt/ros/jazzy/setup.bash && \
    source /workspace/install/setup.bash 2>/dev/null || true && \
    cd /workspace && \
    colcon build --symlink-install \
        --packages-select so_arm_100_bringup \
        --cmake-args -DCMAKE_BUILD_TYPE=Release \
    || echo "NOTE: so_arm_100_bringup skipped (Gazebo deps not available)"

# ─────────────────────────────────────────────────────────────────────────────
# Build web interface
# ─────────────────────────────────────────────────────────────────────────────
COPY web_interface/ /workspace/web_interface/
RUN cd /workspace/web_interface && \
    npm ci && \
    npx vite build && \
    mkdir -p /workspace/web_static && \
    cp -r dist/* /workspace/web_static/

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint script
# ─────────────────────────────────────────────────────────────────────────────
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/check_gpu.sh /usr/local/bin/check_gpu.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/check_gpu.sh

# Source ROS2 Jazzy + workspace overlay on shell start
RUN echo 'source /opt/ros/jazzy/setup.bash' >> /etc/bash.bashrc && \
    echo 'if [ -f /workspace/install/setup.bash ]; then source /workspace/install/setup.bash; fi' >> /etc/bash.bashrc

# ─────────────────────────────────────────────────────────────────────────────
# Expose ports
# WebSocket bridge: 9090, Web interface: 8080
# ─────────────────────────────────────────────────────────────────────────────
EXPOSE 9090 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
