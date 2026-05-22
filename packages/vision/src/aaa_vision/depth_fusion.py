"""Multi-frame depth fusion.

The grasp-preview UI freezes the scene for ~1 s before the user makes a
decision. During that window the camera is stationary, so we can combine
many depth frames into a single noise-reduced depth map. Two strategies
live here:

- `capture_and_average_depth` — per-pixel mean across frames, ignoring
  invalid (zero) samples. Produces a smooth, full-resolution depth map that
  the existing single-frame deprojection path can use transparently.
- `capture_and_fuse` — TSDF volumetric fusion. Produces a unified point
  cloud with 3D outlier rejection but at voxel-grid density, which is
  inherently sparser than per-pixel deprojection.

The freeze path uses averaging by default for "smooth and dense"; TSDF and
its helper `project_pcd_to_mask` are kept as alternatives.
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


def variance_gated_average(
    frames_depth,
    min_valid_fraction: float = 0.34,
    std_threshold_mm: float = 40.0,
):
    """Average a depth-frame stack, rejecting temporally unstable pixels.

    Pure function (no camera dependency) so it can be replayed on saved raw
    stacks for offline validation — see scripts/validate_depth_fusion.py.

    For each pixel, across the frames where it has a valid (>0) reading:
      - compute the mean depth
      - compute the temporal std (two-pass, deviations-from-mean form, which
        is numerically stable — a naive E[x²]-E[x]² suffers catastrophic
        cancellation here because depths squared are large)

    A pixel is invalidated (set to 0) when either:
      - it has too few valid samples (< min_valid_fraction of frames), or
      - its temporal std exceeds `std_threshold_mm`.

    The std gate is the discontinuity fix: a pixel straddling an object edge
    flickers between foreground and background depth across frames, so a plain
    mean places a phantom point at the mid-depth (the "skirt"). Such a pixel
    has std in the hundreds of mm, while a stable surface pixel sits well
    under 10 mm — so the gate cleanly removes ambiguous edge pixels instead of
    inventing a depth for them.

    Returns (avg_uint16, std_float32, counts_float32). avg has gated pixels
    zeroed; std and counts are returned ungated for diagnostics.
    """
    if not frames_depth:
        return None, None, None

    h, w = frames_depth[0].shape[:2]
    n = len(frames_depth)

    # Pass 1: per-pixel mean over valid samples.
    sums = np.zeros((h, w), dtype=np.float32)
    counts = np.zeros((h, w), dtype=np.float32)
    for f in frames_depth:
        valid = f > 0
        sums += np.where(valid, f.astype(np.float32), 0.0)
        counts += valid.astype(np.float32)
    safe_counts = np.maximum(counts, 1.0)
    mean = sums / safe_counts

    # Pass 2: per-pixel variance as mean squared deviation from the mean.
    sqdev = np.zeros((h, w), dtype=np.float32)
    for f in frames_depth:
        valid = f > 0
        d = np.where(valid, f.astype(np.float32) - mean, 0.0)
        sqdev += d * d
    std = np.sqrt(np.maximum(sqdev / safe_counts, 0.0)).astype(np.float32)

    min_valid = max(2, int(round(n * min_valid_fraction)))
    avg = mean.astype(np.uint16)
    gated = (counts < min_valid) | (std > std_threshold_mm)
    avg[gated] = 0

    return avg, std, counts.astype(np.float32)


def capture_and_average_depth(
    image_processor,
    duration_sec: float = 1.0,
    max_frames: int = 20,
    min_valid_fraction: float = 0.34,
    std_threshold_mm: float = 40.0,
    save_raw_path: "Optional[str]" = None,
):
    """Collect frames and pixel-wise average them into one denoised depth map.

    Reads `_last_display_depth` (1080p depth aligned to color) and
    `_last_rgb_frame` (1080p RGB) from the image processor, then delegates to
    `variance_gated_average` for the actual fusion.

    If `save_raw_path` is given, the full raw frame stack plus the computed
    avg/std/counts are written there (np.savez_compressed) so the fusion can
    be replayed and validated offline without the camera.

    Returns (avg_depth_uint16, latest_rgb, depth_std_float32, depth_stack) —
    or (None, None, None, None) if no frames could be collected. The raw
    `depth_stack` (N, H, W uint16) is returned so the caller can retain it and
    later bundle a complete test fixture (e.g. on Export PLY).
    """
    frames_depth = []
    frames_rgb = []
    seen: set = set()
    deadline = time.time() + duration_sec
    while time.time() < deadline and len(frames_depth) < max_frames:
        depth = getattr(image_processor, "_last_display_depth", None)
        rgb = getattr(image_processor, "_last_rgb_frame", None)
        if depth is None or rgb is None:
            time.sleep(0.01)
            continue
        if depth.shape[:2] != rgb.shape[:2]:
            time.sleep(0.01)
            continue
        fid = (id(rgb), id(depth))
        if fid in seen:
            time.sleep(0.01)
            continue
        seen.add(fid)
        frames_depth.append(depth.copy())
        frames_rgb.append(rgb.copy())
        time.sleep(0.03)

    if not frames_depth:
        return None, None, None, None

    stack = np.stack(frames_depth, axis=0)

    if len(frames_depth) == 1:
        return frames_depth[0], frames_rgb[0], None, stack

    avg, std, counts = variance_gated_average(
        frames_depth,
        min_valid_fraction=min_valid_fraction,
        std_threshold_mm=std_threshold_mm,
    )

    h, w = frames_depth[0].shape[:2]
    valid_px = int(np.count_nonzero(avg))
    total_px = h * w
    # Pixels that have data but were rejected specifically by the std gate.
    edge_rejected = int(np.count_nonzero((counts > 0) & (avg == 0) & (std > std_threshold_mm)))
    print(
        f"  Depth averaging: {len(frames_depth)} frames → "
        f"{valid_px}/{total_px} valid px ({100.0 * valid_px / total_px:.1f}%), "
        f"{edge_rejected} px rejected as unstable edges (std>{std_threshold_mm:.0f}mm)"
    )

    if save_raw_path is not None:
        try:
            np.savez_compressed(
                save_raw_path,
                depth_stack=stack,
                rgb=frames_rgb[-1],
                avg=avg,
                std=std,
                counts=counts,
                std_threshold_mm=np.float32(std_threshold_mm),
                min_valid_fraction=np.float32(min_valid_fraction),
            )
            print(f"  Saved raw depth stack → {save_raw_path}")
        except Exception as ex:
            print(f"  Could not save raw depth stack: {ex}")

    return avg, frames_rgb[-1], std, stack


def save_fixture(
    path: str,
    depth_stack: np.ndarray,
    rgb: "Optional[np.ndarray]",
    avg_depth: "Optional[np.ndarray]",
    depth_std: "Optional[np.ndarray]",
    contours,
    selected_object: "Optional[int]",
    intrinsics: dict,
    processed_cloud_path: "Optional[str]" = None,
):
    """Write a complete depth-fusion test fixture (np.savez_compressed).

    Bundles everything needed to replay the freeze → mask → cloud pipeline
    offline so real recordings can become regression test cases:

      - depth_stack: raw per-frame depth (N, H, W uint16) — input to averaging
      - rgb: the frozen RGB frame
      - avg / std: the averaged depth and per-pixel temporal std
      - contours: the detection contours (object array; load with allow_pickle)
      - selected_object: which object index the cloud was exported for
      - intrinsics: camera intrinsics as a JSON string
      - processed_cloud_path: the .ply this fixture was saved alongside

    Replayable via scripts/validate_depth_fusion.py.
    """
    import json

    payload = {
        "depth_stack": depth_stack,
        "selected_object": np.int32(-1 if selected_object is None else selected_object),
        "intrinsics_json": json.dumps(intrinsics),
        "contours": np.array(
            [np.asarray(c) for c in (contours or [])], dtype=object
        ),
    }
    if rgb is not None:
        payload["rgb"] = rgb
    if avg_depth is not None:
        payload["avg"] = avg_depth
    if depth_std is not None:
        payload["std"] = depth_std
    if processed_cloud_path is not None:
        payload["processed_cloud_path"] = str(processed_cloud_path)

    np.savez_compressed(path, **payload)


def capture_and_fuse(
    image_processor,
    duration_sec: float = 1.0,
    max_frames: int = 20,
    voxel_size: float = 0.002,
    sdf_trunc: float = 0.010,
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
