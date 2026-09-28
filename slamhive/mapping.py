#!/usr/bin/env python3

import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml


CONFIG_PATH = Path("/slamhive/config.yaml")
TEMP_CONFIG_PATH = Path("/slamhive/tep_config.yaml")
TEMPLATE_RENDERER = Path("/slamhive/render_template.py")
MAPPINGTASK_PATH = Path("/slamhive/mappingtask.yaml")
MAPPING_LAUNCH = Path("/slamhive/mapping_user.launch")
RESULT_DIR = Path("/slamhive/result")
DATABASE_PATH = RESULT_DIR / "rtabmap.db"
TRAJ_PATH = RESULT_DIR / "traj.txt"
TRAJ_FLAG = RESULT_DIR / "traj_flag.txt"
FINISHED = RESULT_DIR / "finished"
RTABMAP_WS = Path(os.environ.get("RTABMAP_WS", "/opt/rtabmap_ws"))


DEFAULT_CONTEXT = {
    "use_sim_time": "true",
    "frame_id": "base_footprint",
    "odom_frame_id": "odom",
    "map_frame_id": "map",
    "database_path": str(DATABASE_PATH),
    "rgb_topic": "/data_throttled_image",
    "depth_topic": "/data_throttled_image_depth",
    "camera_info_topic": "/data_throttled_camera_info",
    "scan_topic": "/jn0/base_scan",
    "subscribe_scan": "true",
    "image_transport": "compressed",
    "depth_transport": "compressedDepth",
    "approx_sync": "true",
    "sync_queue_size": "10",
    "topic_queue_size": "10",
    "approx_sync_max_interval": "0.02",
    "launch_start_wait": "10",
    "post_play_wait": "10",
    "Rtabmap_DetectionRate": "1.0",
    "RGBD_NeighborLinkRefining": "true",
    "RGBD_ProximityBySpace": "true",
    "RGBD_ProximityByTime": "false",
    "RGBD_ProximityPathMaxNeighbors": "10",
    "Reg_Strategy": "1",
    "Vis_MinInliers": "12",
    "RGBD_OptimizeFromGraphEnd": "false",
    "RGBD_OptimizeMaxError": "4",
    "Reg_Force3DoF": "true",
    "Grid_FromDepth": "false",
    "Mem_STMSize": "30",
    "RGBD_LocalRadius": "5",
    "Icp_CorrespondenceRatio": "0.2",
    "Icp_PM": "false",
    "Icp_PointToPlane": "false",
    "Icp_MaxCorrespondenceDistance": "0.15",
    "Icp_VoxelSize": "0.05",
}


def shell_join(parts):
    if hasattr(shlex, "join"):
        return shlex.join(parts)
    return " ".join(shlex.quote(str(part)) for part in parts)


def normalize_key(key):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(key)).strip("_")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_context(config):
    context = dict(DEFAULT_CONTEXT)
    for key, value in (config.get("algorithm-parameters") or {}).items():
        context[normalize_key(key)] = value
    context["database_path"] = str(RESULT_DIR / "rtabmap.db")
    return context


def write_temp_config(context):
    with TEMP_CONFIG_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(context, handle, default_flow_style=False, sort_keys=False)


def source_prefix():
    return (
        "source /opt/ros/humble/setup.bash >/dev/null 2>&1 && "
        "source {} >/dev/null 2>&1 && "
    ).format(shlex.quote(str(RTABMAP_WS / "install" / "setup.bash")))


def run_sourced(command, log_path=None, check=True):
    full_command = source_prefix() + command
    stdout = None
    handle = None
    if log_path is not None:
        handle = open(log_path, "w", encoding="utf-8")
        stdout = handle
    try:
        print("[mapping.py] run: {}".format(full_command), flush=True)
        return subprocess.run(["bash", "-lc", full_command], stdout=stdout, stderr=subprocess.STDOUT, check=check)
    finally:
        if handle is not None:
            handle.close()


def start_launch():
    command = source_prefix() + "python3 {}".format(shlex.quote(str(MAPPING_LAUNCH)))
    log_path = RESULT_DIR / "rtabmap_launch.log"
    log_handle = log_path.open("w", encoding="utf-8")
    print("[mapping.py] starting launch: {}".format(command), flush=True)
    process = subprocess.Popen(
        ["bash", "-lc", command],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    return process, log_handle


def stop_launch(process, log_handle):
    if process.poll() is None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGINT)
            process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=10)
    log_handle.close()


def valid_tum_rows(path):
    if not path.exists() or path.stat().st_size == 0:
        return 0
    rows = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = text.split()
            if len(parts) != 8:
                return 0
            try:
                [float(part) for part in parts]
            except ValueError:
                return 0
            rows += 1
    return rows


def export_trajectory():
    if not DATABASE_PATH.exists():
        raise RuntimeError("RTAB-Map database was not created: {}".format(DATABASE_PATH))
    export_base = RESULT_DIR / "rtabmap"
    export_path = RESULT_DIR / "rtabmap_poses.txt"
    command = "rtabmap-export --poses --poses_format 10 --output {} --output_dir {} {}".format(
        shlex.quote(export_base.name),
        shlex.quote(str(RESULT_DIR)),
        shlex.quote(str(DATABASE_PATH)),
    )
    run_sourced(command, log_path=RESULT_DIR / "rtabmap_export.log", check=True)
    if not export_path.exists():
        raise RuntimeError("RTAB-Map pose export did not create {}".format(export_path))
    shutil.move(str(export_path), str(TRAJ_PATH))
    rows = valid_tum_rows(TRAJ_PATH)
    if rows <= 0:
        raise RuntimeError("Exported trajectory has no valid TUM rows")
    print("[mapping.py] exported {} TUM poses to {}".format(rows, TRAJ_PATH), flush=True)


def write_completion():
    rows = valid_tum_rows(TRAJ_PATH)
    TRAJ_FLAG.write_text("True" if rows > 0 else "False", encoding="utf-8")
    FINISHED.touch()
    print("[mapping.py] trajectory rows: {}".format(rows), flush=True)
    print("[mapping.py] wrote {}".format(FINISHED), flush=True)


def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HOME", str(RESULT_DIR / "home"))
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)

    config = load_config()
    launch_process = None
    launch_log = None
    try:
        context = build_context(config)
        write_temp_config(context)
        subprocess.run(["python3", str(TEMPLATE_RENDERER)], check=True)
        if not MAPPINGTASK_PATH.exists():
            raise RuntimeError("{} was not generated".format(MAPPINGTASK_PATH))

        if DATABASE_PATH.exists():
            DATABASE_PATH.unlink()

        launch_process, launch_log = start_launch()
        time.sleep(float(context.get("launch_start_wait", 10)))

        run_sourced(
            "python3 /slamhive/dataset/rosbag_play.py",
            log_path=RESULT_DIR / "rosbag_play.log",
            check=True,
        )
        time.sleep(float(context.get("post_play_wait", 10)))
    except Exception as exc:
        print("[mapping.py] {}".format(exc), file=sys.stderr, flush=True)
    finally:
        if launch_process is not None and launch_log is not None:
            stop_launch(launch_process, launch_log)
        try:
            export_trajectory()
        except Exception as exc:
            print("[mapping.py] trajectory export failed: {}".format(exc), file=sys.stderr, flush=True)
            if not TRAJ_PATH.exists():
                TRAJ_PATH.touch()
        write_completion()


if __name__ == "__main__":
    main()
