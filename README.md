# RTAB-Map ROS2 for SLAM-Hive

Fork of [introlab/rtabmap_ros](https://github.com/introlab/rtabmap_ros) (ROS2
Humble). `rtabmap_ros/` is the upstream `ros2` branch at
`aec4f91f6150e82572bae1a5378fd9e5be924ca0`, unchanged; the Dockerfile downloads the
RTAB-Map library from [introlab/rtabmap](https://github.com/introlab/rtabmap) at
`27ca7ec05849b2fc5c22540673afa6b156a2cfff`. `slamhive/` runs RTAB-Map RGB-D (+
optional laser scan) mapping in a SLAM-Hive task and exports the optimized poses
to `/slamhive/result/traj.txt` (TUM format).

### Build the RTAB-Map ROS2 Dockerfile
Firstly, git clone the algorithm Dockerfile repository to your computer, then:
```
cd rtabmap-ros2
./install.sh
```
You can check whether the image is successfully built as follows:
```
docker images
```
you can see:
```
slam-hive-algorithm rtabmap-ros2 [IMAGE ID] [CREATED] [SIZE]
```

### Register in SLAM-Hive
Image tag `rtabmap-ros2`, ROS version `ros2`. SLAM-Hive plays every dataset to
the algorithm as ROS2 (ROS1 bags and ROS2 bags Humble cannot read are converted
to mcap), so the image includes `ros-humble-rosbag2-storage-mcap`.

### Parameters
Algorithm parameters override the defaults in `slamhive/mapping.py`, which
follow the official `robot_mapping_demo.launch.py` (rtabmap_demos demo bag).

| Parameter | Default | Notes |
| --- | --- | --- |
| `Rtabmap/DetectionRate` | 1.0 | Hz of map updates / loop closure detection |
| `Vis/MinInliers` | 12 | visual inliers to accept a transform |
| `Reg/Strategy` | 1 | 0 visual, 1 ICP, 2 visual + ICP |
| `Reg/Force3DoF` | true | `false` for 6DoF (handheld camera) |
| `RGBD/OptimizeMaxError` | 4 | reject loop closures above this graph error |
| `Mem/STMSize` | 30 | short-term memory size |
| `RGBD/LocalRadius` | 5 | m, radius of local proximity detection |
| `Icp/CorrespondenceRatio`, `Icp/MaxCorrespondenceDistance`, `Icp/VoxelSize` | 0.2, 0.15, 0.05 | ICP |
| `sync_queue_size`, `topic_queue_size` | 10, 10 | |
| `approx_sync`, `approx_sync_max_interval` | true, 0.02 | RGB / depth / scan sync |
| `rgb_topic`, `depth_topic`, `camera_info_topic` | `/data_throttled_image`, `/data_throttled_image_depth`, `/data_throttled_camera_info` | |
| `image_transport`, `depth_transport` | `compressed`, `compressedDepth` | `raw` for raw images |
| `subscribe_scan`, `scan_topic` | true, `/jn0/base_scan` | |
| `frame_id`, `odom_frame_id`, `map_frame_id` | `base_footprint`, `odom`, `map` | |
| `launch_start_wait`, `post_play_wait` | 10, 10 | s before playback / after it |

Example, TUM RGB-D (`rgbd_dataset_freiburg1_xyz`): `rgb_topic`
`/camera/rgb/image_color`, `depth_topic` `/camera/depth/image`,
`camera_info_topic` `/camera/rgb/camera_info`, `image_transport` and
`depth_transport` `raw`, `frame_id` `openni_rgb_optical_frame`,
`subscribe_scan` `false`, `Reg/Strategy` 0, `Reg/Force3DoF` `false`, and the
dataset remap `/tf_bag: /tf` (the bag's mocap `/tf` would otherwise fight the
odometry). ATE 0.034-0.047 m over three runs of this image, from the ROS1 bag
and from a Jazzy mcap copy (RTAB-Map runs in real time, so results vary
between runs and with machine load).
