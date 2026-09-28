FROM ros:humble-ros-base

SHELL ["/bin/bash", "-c"]

# rtabmap_ros comes from this repository (rtabmap_ros/, introlab/rtabmap_ros
# ros2 branch at aec4f91f6150e82572bae1a5378fd9e5be924ca0); the RTAB-Map
# library is downloaded from introlab/rtabmap at this commit.
ARG RTABMAP_COMMIT=27ca7ec05849b2fc5c22540673afa6b156a2cfff

ENV DEBIAN_FRONTEND=noninteractive
ENV RTABMAP_WS=/opt/rtabmap_ws
WORKDIR ${RTABMAP_WS}

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        git \
        python3-colcon-common-extensions \
        python3-pip \
        python3-rosdep \
        python3-vcstool \
        ros-humble-compressed-depth-image-transport \
        ros-humble-compressed-image-transport && \
    rm -rf /var/lib/apt/lists/*

COPY rtabmap_ros src/rtabmap_ros

RUN mkdir -p src/rtabmap && \
    curl -fsSL https://github.com/introlab/rtabmap/archive/${RTABMAP_COMMIT}.tar.gz | \
        tar -xz -C src/rtabmap --strip-components=1 && \
    apt-get update && \
    (rosdep init || true) && \
    rosdep update --rosdistro humble && \
    source /opt/ros/humble/setup.bash && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro humble && \
    colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sfn ${RTABMAP_WS} /ws

# SLAM-Hive plays ROS2 datasets in its platform format (mcap, metadata v8): every
# ROS2 algorithm image needs the mcap storage plugin.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ros-humble-rosbag2-storage-mcap && \
    rm -rf /var/lib/apt/lists/*

CMD ["python3", "/slamhive/mapping.py"]
