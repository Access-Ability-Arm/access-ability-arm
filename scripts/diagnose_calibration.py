"""Diagnose depth->color calibration by computing per-point reprojection residuals.

Usage:
  python scripts/diagnose_calibration.py <pointcloud.npz|.npy|.ply> [--calibration my_calibration.json] [--out report_dir]

What it does:
- Loads point cloud (supports .npz with many common keys, .npy, .ply)
- Loads calibration JSON (rotation + translation and color intrinsics)
- If texture coordinates (u,v in [0,1]) are available in the input, computes
  reprojection residuals between projected calibrated 3D points and those texture coords.
- Produces numeric report (mean/median/max, percentiles) and heatmap overlay PNG
  (residuals colorized on top of color image if available, otherwise a scatter image).

This helps diagnose whether the computed extrinsic (R,t) maps depth-frame points
correctly into the color image.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


COMMON_POINT_KEYS = [
    "points",
    "vertices",
    "vtx",
    "xyz",
    "positions",
    "vertex",
    "verts",
    "pointcloud",
]

COMMON_TEX_KEYS = [
    "texture",
    "texture_coords",
    "tex",
    "uv",
    "uvs",
    "texcoords",
]

COMMON_COLOR_KEYS = [
    "color",
    "color_image",
    "rgb",
    "image",
    "frame",
]


def load_calibration(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Calibration file not found: {path}")
    with open(p, "r") as f:
        return json.load(f)


def find_in_npz(npz: dict, candidates: list) -> Optional[str]:
    for k in candidates:
        if k in npz:
            return k
    # try case-insensitive
    keys_lower = {kk.lower(): kk for kk in npz.keys()}
    for k in candidates:
        if k.lower() in keys_lower:
            return keys_lower[k.lower()]
    return None


def load_pointcloud(path: str) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """Load point cloud and optionally texture coords and color image.

    Returns (points (N,3), texcoords (N,2) or None, color_image (H,W,3) or None)
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    if p.suffix == ".npz":
        data = np.load(p)
        # find points
        key_pts = find_in_npz(data, COMMON_POINT_KEYS)
        if key_pts is None:
            # fallback: first array with shape (N,3)
            for k in data.files:
                arr = data[k]
                if isinstance(arr, np.ndarray) and arr.ndim == 2 and arr.shape[1] == 3:
                    key_pts = k
                    break
        if key_pts is None:
            raise ValueError("Could not find 3D points in npz file")
        points = np.array(data[key_pts])

        # texcoords
        key_tex = find_in_npz(data, COMMON_TEX_KEYS)
        tex = np.array(data[key_tex]) if key_tex is not None else None

        # color image
        key_col = find_in_npz(data, COMMON_COLOR_KEYS)
        col = np.array(data[key_col]) if key_col is not None else None

        return points, tex, col

    elif p.suffix == ".npy":
        arr = np.load(p)
        if arr.ndim == 2 and arr.shape[1] == 3:
            return arr, None, None
        raise ValueError("Loaded .npy but shape not (N,3)")

    elif p.suffix == ".ply":
        try:
            import open3d as o3d
        except Exception:
            raise RuntimeError("open3d required to read .ply files")
        pcd = o3d.io.read_point_cloud(str(p))
        pts = np.asarray(pcd.points)
        # colors if present
        cols = np.asarray(pcd.colors) if len(pcd.colors) > 0 else None
        return pts, None, cols

    else:
        raise ValueError("Unsupported file type: " + p.suffix)


def project_points(pc_color: np.ndarray, color_intr: dict) -> np.ndarray:
    """Project 3D points in color camera frame to pixel coordinates (u,v).

    pc_color: (N,3)
    color_intr: dict with fx, fy, ppx, ppy, width, height
    Returns (N,2) float pixel coords
    """
    fx = color_intr.get("fx")
    fy = color_intr.get("fy")
    ppx = color_intr.get("ppx") or color_intr.get("cx") or 0
    ppy = color_intr.get("ppy") or color_intr.get("cy") or 0

    X = pc_color[:, 0]
    Y = pc_color[:, 1]
    Z = pc_color[:, 2]
    valid = Z > 0

    u = np.full_like(Z, np.nan, dtype=float)
    v = np.full_like(Z, np.nan, dtype=float)

    u[valid] = fx * (X[valid] / Z[valid]) + ppx
    v[valid] = fy * (Y[valid] / Z[valid]) + ppy

    return np.stack([u, v], axis=1)


def compute_residuals(points_depth: np.ndarray, tex: np.ndarray, calib: dict) -> Tuple[np.ndarray, np.ndarray]:
    """Compute reprojection residuals.

    points_depth: (N,3) in depth frame (meters)
    tex: (N,2) texture coords in [0,1] mapping into color image, or pixel coords
    calib: loaded calibration dict

    Returns: residuals (N,), projected_pixels (N,2)
    """
    ext = calib.get("extrinsic_depth_to_color") or calib.get("extrinsic")
    if ext is None:
        raise KeyError("Calibration JSON missing 'extrinsic_depth_to_color' key")
    R = np.array(ext.get("rotation_matrix"))
    t = np.array(ext.get("translation_vector"))

    # transform points
    pc_color = (R @ points_depth.T + t.reshape(3, 1)).T

    color_intr = calib.get("color_intrinsics") or calib.get("color_intrin") or calib.get("color_intrinsic")
    if color_intr is None:
        raise KeyError("Calibration JSON missing 'color_intrinsics'")

    proj = project_points(pc_color, color_intr)  # pixel coords

    # Convert tex to pixel coords if in [0,1]
    tex_pixel = None
    if tex is None:
        raise ValueError("No texture coordinates provided in pointcloud for residual computation")

    # If tex shape Nx2 and values <=1 assume normalized
    if tex.max() <= 1.01:
        width = color_intr.get("width")
        height = color_intr.get("height")
        tex_pixel = np.stack([tex[:, 0] * width, tex[:, 1] * height], axis=1)
    else:
        tex_pixel = tex.astype(float)

    # Compute residual per point where proj and tex_pixel are finite
    valid = np.isfinite(proj).all(axis=1) & np.isfinite(tex_pixel).all(axis=1)
    d = np.linalg.norm(proj[valid] - tex_pixel[valid], axis=1)

    residuals = np.full(points_depth.shape[0], np.nan)
    residuals[valid] = d
    return residuals, proj


def make_heatmap_overlay(proj_pixels: np.ndarray, residuals: np.ndarray, color_image: Optional[np.ndarray], out_path: Path) -> None:
    """Create heatmap overlay image and save as PNG.

    If color_image is provided, overlay heatmap on top. Otherwise save scatter visualization.
    """
    # Determine image size
    if color_image is not None:
        img = color_image.copy()
        h, w = img.shape[:2]
    else:
        # derive bounds from projections
        finite = np.isfinite(proj_pixels).all(axis=1)
        pix = proj_pixels[finite]
        if pix.shape[0] == 0:
            raise ValueError("No valid projected pixels to render")
        minx, miny = np.floor(pix.min(axis=0)).astype(int)
        maxx, maxy = np.ceil(pix.max(axis=0)).astype(int)
        w = maxx - minx + 100
        h = maxy - miny + 100
        img = np.ones((h, w, 3), dtype=np.uint8) * 255
        proj_pixels = proj_pixels - np.array([minx - 50, miny - 50])

    # Build a grayscale residual map
    heat = np.zeros((img.shape[0], img.shape[1]), dtype=float)
    count = np.zeros_like(heat)

    for (px, rv) in zip(proj_pixels, residuals):
        if not np.isfinite(px).all() or not np.isfinite(rv):
            continue
        x = int(round(px[0]))
        y = int(round(px[1]))
        if x < 0 or y < 0 or x >= img.shape[1] or y >= img.shape[0]:
            continue
        heat[y, x] += rv
        count[y, x] += 1

    # Average where multiple points map to same pixel
    mask = count > 0
    heat[mask] = heat[mask] / count[mask]

    # Normalize for visualization
    finite_vals = heat[mask]
    if finite_vals.size == 0:
        raise ValueError("No residuals mapped to image for visualization")

    vmin = np.nanpercentile(finite_vals, 5)
    vmax = np.nanpercentile(finite_vals, 95)
    norm = (heat - vmin) / max(1e-6, (vmax - vmin))
    norm = np.clip(norm, 0.0, 1.0)
    cmap = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_JET)

    # Blend heatmap with color image
    alpha = 0.6
    mask3 = np.dstack([mask.astype(np.uint8)] * 3)
    overlay = img.copy()
    overlay[mask3 == 1] = cv2.addWeighted(img, 1 - alpha, cmap, alpha, 0)[mask3 == 1]

    # Save
    cv2.imwrite(str(out_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))


def summarize_and_save(residuals: np.ndarray, out_dir: Path) -> dict:
    valid = np.isfinite(residuals)
    d = residuals[valid]
    summary = {}
    if d.size == 0:
        summary = {"count": 0}
    else:
        summary = {
            "count": int(d.size),
            "mean_px": float(d.mean()),
            "median_px": float(np.median(d)),
            "max_px": float(d.max()),
            "p90_px": float(np.percentile(d, 90)),
            "p95_px": float(np.percentile(d, 95)),
            "pct_gt_1px": float((d > 1.0).sum() / d.size * 100.0),
            "pct_gt_2px": float((d > 2.0).sum() / d.size * 100.0),
        }
    # Save JSON summary
    out = out_dir / "diagnostics_summary.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Diagnose depth->color calibration errors")
    parser.add_argument("pointcloud", help="Path to .npz/.npy/.ply point cloud file")
    parser.add_argument(
        "--calibration",
        help="Path to calibration JSON (default: my_calibration.json or calibration_extrinsic.json)",
        default=None,
    )
    parser.add_argument("--out", help="Output directory for diagnostics", default="diagnostics")
    args = parser.parse_args()

    pc_path = Path(args.pointcloud)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine calibration file
    calib_path = args.calibration
    if calib_path is None:
        # prefer my_calibration.json then calibration_extrinsic.json
        for candidate in ["my_calibration.json", "calibration_extrinsic.json"]:
            if Path(candidate).exists():
                calib_path = candidate
                break
    if calib_path is None:
        raise FileNotFoundError("No calibration file specified and none found in project root")

    print(f"Loading calibration: {calib_path}")
    calib = load_calibration(calib_path)

    print(f"Loading point cloud: {pc_path}")
    points, tex, color = load_pointcloud(str(pc_path))
    points = np.asarray(points, dtype=float)

    print(f"Points: {points.shape[0]}")
    if tex is None:
        print("Warning: No texture coordinates found in pointcloud; cannot compute residuals against SDK mapping")

    try:
        residuals, proj = compute_residuals(points, tex, calib)
    except Exception as e:
        print(f"Failed to compute residuals: {e}")
        raise

    # Save numeric summary
    summary = summarize_and_save(residuals, out_dir)
    print("Diagnostics summary:")
    print(summary)

    # Save histogram image of residuals
    valid = np.isfinite(residuals)
    if valid.sum() > 0:
        import matplotlib.pyplot as plt

        vals = residuals[valid]
        plt.figure(figsize=(6, 4))
        plt.hist(vals, bins=100)
        plt.xlabel("Reprojection error (pixels)")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(out_dir / "residuals_histogram.png")
        plt.close()

    # Create overlay heatmap if possible
    overlay_path = out_dir / "residuals_overlay.png"
    try:
        make_heatmap_overlay(proj, residuals, None if color is None else color, overlay_path)
        print(f"Saved overlay heatmap: {overlay_path}")
    except Exception as e:
        print(f"Could not create overlay: {e}")

    # Save residuals array
    np.savez_compressed(out_dir / "residuals.npz", residuals=residuals, proj=proj)
    print(f"Saved residuals to {out_dir / 'residuals.npz'}")

    print("Done.")


if __name__ == "__main__":
    main()
