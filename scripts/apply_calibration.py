"""Apply saved depth-to-color calibration extrinsic to a point cloud.

This script loads a previously saved calibration (from calibrate_camera_extrinsic.py)
and applies the extrinsic transform to move points from depth camera frame to
color camera frame (or world frame if specified).

Usage:
  python scripts/apply_calibration.py <pointcloud.npy|.npz|.ply> [--calibration config/calibration_extrinsic.json] [--output transformed.ply]

Example:
  python scripts/apply_calibration.py logs/pointclouds/pointcloud_obj1_20260113_203318.npz --output transformed.ply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import open3d as o3d
except Exception:  # pragma: no cover
    o3d = None


def load_calibration(cal_file: str) -> Optional[dict]:
    """Load calibration JSON file."""
    try:
        with open(cal_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Calibration file not found: {cal_file}")
        return None


def load_pointcloud(cloud_file: str) -> Optional[np.ndarray]:
    """Load point cloud from .npy, .npz, or .ply file.
    Returns (N, 3) array of 3D points, or None if failed.
    """
    path = Path(cloud_file)
    if not path.exists():
        print(f"Point cloud file not found: {cloud_file}")
        return None

    if path.suffix == ".npy":
        return np.load(cloud_file)
    elif path.suffix == ".npz":
        data = np.load(cloud_file)
        # Try common keys
        if "points" in data:
            return data["points"]
        elif "vertices" in data:
            return data["vertices"]
        else:
            # Return first array
            key = list(data.keys())[0]
            return data[key]
    elif path.suffix == ".ply":
        if o3d is None:
            print("open3d required to load .ply files")
            return None
        pcd = o3d.io.read_point_cloud(cloud_file)
        return np.asarray(pcd.points)
    else:
        print(f"Unsupported file format: {path.suffix}")
        return None


def apply_extrinsic(
    points: np.ndarray, R: np.ndarray, t: np.ndarray
) -> np.ndarray:
    """Apply extrinsic transform to points.
    p_out = R @ p_in + t
    """
    return (R @ points.T + t.reshape(3, 1)).T


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply depth-to-color calibration extrinsic to point cloud")
    parser.add_argument("pointcloud", help="Input point cloud file (.npy, .npz, or .ply)")
    parser.add_argument(
        "--calibration", "-c", default="config/calibration_extrinsic.json", help="Calibration JSON file"
    )
    parser.add_argument("--output", "-o", help="Output point cloud file (.npy or .ply)")
    args = parser.parse_args(argv)

    # Load calibration
    cal = load_calibration(args.calibration)
    if cal is None:
        return 1

    R = np.array(cal["extrinsic_depth_to_color"]["rotation_matrix"])
    t = np.array(cal["extrinsic_depth_to_color"]["translation_vector"])
    error = cal.get("reprojection_error_pixels", "N/A")

    print(f"Calibration loaded from {args.calibration}")
    print(f"  Reprojection error: {error} pixels")

    # Load point cloud
    points = load_pointcloud(args.pointcloud)
    if points is None:
        return 1

    print(f"Point cloud loaded: {points.shape[0]} points")

    # Apply transform
    points_transformed = apply_extrinsic(points, R, t)
    print(f"Applied extrinsic transform (depth -> color frame)")

    # Save or display stats
    if args.output:
        output_path = Path(args.output)
        if output_path.suffix == ".npy":
            np.save(args.output, points_transformed)
            print(f"Saved to {args.output}")
        elif output_path.suffix == ".ply":
            if o3d is None:
                print("open3d required to save .ply files")
                return 1
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points_transformed)
            o3d.io.write_point_cloud(args.output, pcd)
            print(f"Saved to {args.output}")
        else:
            print(f"Unsupported output format: {output_path.suffix}")
            return 1
    else:
        # Just print stats
        print(f"\nPoint cloud statistics (color frame):")
        print(f"  X: [{points_transformed[:, 0].min():.3f}, {points_transformed[:, 0].max():.3f}]")
        print(f"  Y: [{points_transformed[:, 1].min():.3f}, {points_transformed[:, 1].max():.3f}]")
        print(f"  Z: [{points_transformed[:, 2].min():.3f}, {points_transformed[:, 2].max():.3f}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
