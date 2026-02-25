"""Capture RealSense frames, align depth->color, create colored pointcloud and visualize with Open3D.

Usage:
  python scripts/align_and_view_pointcloud.py [--save out.ply] [--voxel 0.005]

This script attempts to open a RealSense camera. If none is found it exits cleanly.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

import numpy as np

try:
    import pyrealsense2 as rs
except Exception:  # pragma: no cover - hardware dependent
    rs = None

import open3d as o3d
import cv2


def capture_aligned_pointcloud(save_path: Optional[str] = None, voxel_size: Optional[float] = None):
    if rs is None:
        print("pyrealsense2 not available in this environment.")
        return 1

    pipeline = rs.pipeline()
    cfg = rs.config()
    # Use common resolutions; align will map depth into color frame
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30)

    profile = pipeline.start(cfg)
    align_to = rs.stream.color
    align = rs.align(align_to)

    try:
        print("Warming up camera and grabbing a frame...")
        for _ in range(5):
            pipeline.wait_for_frames()

        frames = pipeline.wait_for_frames(timeout_ms=5000)
        aligned = align.process(frames)
        depth_aligned = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()

        if not depth_aligned or not color_frame:
            print("Failed to get aligned frames.")
            return 1

        # Create pointcloud and map to color
        pc = rs.pointcloud()
        pc.map_to(color_frame)
        points = pc.calculate(depth_aligned)

        vtx = np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1, 3)
        tex = np.asanyarray(points.get_texture_coordinates()).view(np.float32).reshape(-1, 2)

        color_image = np.asanyarray(color_frame.get_data())
        # color frame comes in BGR because we asked for bgr8
        color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
        h, w = color_image.shape[:2]

        u = np.clip((tex[:, 0] * w).astype(np.int32), 0, w - 1)
        v = np.clip((tex[:, 1] * h).astype(np.int32), 0, h - 1)

        colors = color_image[v, u].astype(np.float32) / 255.0

        # Filter invalid points
        valid = np.isfinite(vtx).all(axis=1) & (vtx[:, 2] > 0)
        vtx = vtx[valid]
        colors = colors[valid]

        # Build Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(vtx)
        pcd.colors = o3d.utility.Vector3dVector(colors)

        if voxel_size is not None and voxel_size > 0:
            pcd = pcd.voxel_down_sample(voxel_size)

        if save_path:
            o3d.io.write_point_cloud(save_path, pcd)
            print(f"Saved aligned pointcloud to: {save_path}")

        # Orient axes for easier viewing: RealSense camera frame is x-right, y-down, z-forward.
        # Open3D viewer treats +Y as up; the raw cloud is in camera frame.
        vis_pcd = pcd

        print("Opening Open3D viewer (close the window to exit)...")
        print(f"Pointcloud stats: {len(pcd.points)} points, X={vtx[:,0].min():.2f}..{vtx[:,0].max():.2f}, "
              f"Y={vtx[:,1].min():.2f}..{vtx[:,1].max():.2f}, Z={vtx[:,2].min():.2f}..{vtx[:,2].max():.2f}")
        o3d.visualization.draw_geometries([vis_pcd], window_name="Aligned RGB PointCloud")
        return 0
    finally:
        pipeline.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture aligned RealSense pointcloud and view with Open3D")
    parser.add_argument("--save", "-s", help="Optional output PLY filename", default=None)
    parser.add_argument("--voxel", "-v", help="Voxel size for downsampling (meters)", type=float, default=0.0)
    args = parser.parse_args(argv)

    voxel = args.voxel if args.voxel and args.voxel > 0.0 else None
    return_code = capture_aligned_pointcloud(save_path=args.save, voxel_size=voxel)
    sys.exit(return_code if return_code is not None else 0)


if __name__ == "__main__":
    main()
