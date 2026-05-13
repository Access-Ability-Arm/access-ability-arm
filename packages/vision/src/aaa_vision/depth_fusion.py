"""Multi-frame depth fusion via Open3D TSDF integration.

The grasp-preview UI freezes the scene for ~1 s before the user makes a
decision. During that window the camera is stationary, so we can integrate
many RGB-D frames into a single TSDF volume and extract a much cleaner
point cloud than any individual frame would give.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np


# D435 color intrinsics at 1920x1080 — used as a fallback when the image
# processor cannot expose live intrinsics (daemon mode). These match the
# hard-coded values used in _mixin_point_cloud.py for the same reason.
_D435_COLOR_INTRINSICS_1080P = {
    "width": 1920,
    "height": 1080,
    "fx": 1386.12,
    "fy": 1386.12,
    "cx": 964.83,
    "cy": 545.55,
}


def get_color_intrinsics(image_processor) -> dict:
    """Return 1080p color-camera intrinsics for the current image processor.

    Prefers live RealSense intrinsics from the device profile when available
    (direct mode), otherwise returns D435 defaults.
    """
    rs_cam = getattr(image_processor, "rs_camera", None)
    if rs_cam is not None:
        try:
            import pyrealsense2 as rs

            profile = rs_cam.profile
            stream = profile.get_stream(rs.stream.color).as_video_stream_profile()
            intr = stream.get_intrinsics()
            return {
                "width": intr.width,
                "height": intr.height,
                "fx": intr.fx,
                "fy": intr.fy,
                "cx": intr.ppx,
                "cy": intr.ppy,
            }
        except Exception:
            pass
    return dict(_D435_COLOR_INTRINSICS_1080P)


def capture_and_fuse(
    image_processor,
    duration_sec: float = 1.0,
    max_frames: int = 20,
    voxel_size: float = 0.003,
    sdf_trunc: float = 0.012,
    depth_trunc_m: float = 2.0,
):
    """Collect RGB-D frames over `duration_sec` and fuse them with TSDF.

    Reads `_last_rgb_frame` (1080p RGB) and `_last_display_depth` (1080p depth
    aligned to color FOV) from the image processor at roughly camera framerate.
    Consecutive frames that are the same object reference are skipped to avoid
    integrating identical data.

    Returns an Open3D PointCloud in the color-camera frame (meters), or None
    if Open3D is unavailable or no usable frames were collected.
    """
    try:
        import open3d as o3d
    except ImportError:
        return None

    intr = get_color_intrinsics(image_processor)
    pinhole = o3d.camera.PinholeCameraIntrinsic(
        intr["width"], intr["height"], intr["fx"], intr["fy"], intr["cx"], intr["cy"]
    )

    frames = []
    seen_ids: set = set()
    deadline = time.time() + duration_sec
    while time.time() < deadline and len(frames) < max_frames:
        rgb = getattr(image_processor, "_last_rgb_frame", None)
        depth = getattr(image_processor, "_last_display_depth", None)
        if rgb is None or depth is None:
            time.sleep(0.01)
            continue
        if rgb.shape[:2] != depth.shape[:2]:
            time.sleep(0.01)
            continue
        fid = (id(rgb), id(depth))
        if fid in seen_ids:
            time.sleep(0.01)
            continue
        seen_ids.add(fid)
        # Capture thread overwrites references in place; copy before queueing
        frames.append((rgb.copy(), depth.copy()))
        time.sleep(0.03)

    if not frames:
        return None

    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
    )
    extrinsic = np.eye(4)
    integrated = 0
    for rgb, depth in frames:
        try:
            color_img = o3d.geometry.Image(np.ascontiguousarray(rgb))
            depth_img = o3d.geometry.Image(np.ascontiguousarray(depth))
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color_img,
                depth_img,
                depth_scale=1000.0,
                depth_trunc=depth_trunc_m,
                convert_rgb_to_intensity=False,
            )
            volume.integrate(rgbd, pinhole, extrinsic)
            integrated += 1
        except Exception:
            continue

    if integrated == 0:
        return None

    try:
        pcd = volume.extract_point_cloud()
    except Exception:
        return None

    print(f"  TSDF fusion: integrated {integrated}/{len(frames)} frames → {len(pcd.points)} points")
    return pcd


def project_pcd_to_mask(
    pcd,
    mask: np.ndarray,
    intrinsics: dict,
) -> "Optional[tuple[np.ndarray, np.ndarray]]":
    """Project an Open3D pointcloud into image space and keep points inside `mask`.

    `mask` is a uint8 image (255 = inside, 0 = outside) at the same resolution
    as `intrinsics`. Returns (points_meters, colors_uint8_or_None) for the
    subset of pcd whose projections land on True mask pixels, or None when the
    cloud is empty.
    """
    if pcd is None or len(pcd.points) == 0:
        return None

    pts = np.asarray(pcd.points)
    has_colors = pcd.has_colors() and len(pcd.colors) == len(pcd.points)
    colors = np.asarray(pcd.colors) if has_colors else None

    fx = intrinsics["fx"]
    fy = intrinsics["fy"]
    cx = intrinsics["cx"]
    cy = intrinsics["cy"]
    w = intrinsics["width"]
    h = intrinsics["height"]

    z = pts[:, 2]
    in_front = z > 1e-3
    pts_f = pts[in_front]
    if len(pts_f) == 0:
        return None
    colors_f = colors[in_front] if colors is not None else None

    u = (pts_f[:, 0] * fx / pts_f[:, 2] + cx).astype(np.int32)
    v = (pts_f[:, 1] * fy / pts_f[:, 2] + cy).astype(np.int32)

    in_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    if not np.any(in_bounds):
        return None

    pts_in = pts_f[in_bounds]
    u_in = u[in_bounds]
    v_in = v[in_bounds]
    colors_in = colors_f[in_bounds] if colors_f is not None else None

    inside = mask[v_in, u_in] > 0
    if not np.any(inside):
        return None

    out_pts = pts_in[inside]
    out_colors = None
    if colors_in is not None:
        out_colors = (colors_in[inside] * 255.0).clip(0, 255).astype(np.uint8)
    return out_pts, out_colors
