"""Calibrate RealSense depth-to-color camera extrinsic using a checkerboard pattern.

This script:
  1. Captures frames with a checkerboard visible
  2. Detects checkerboard corners in the color image
  3. Reads depth values and deprojects to 3D in the depth frame
  4. Computes depth->color extrinsic (R, t) using solvePnP
  5. Saves to calibration_extrinsic.json for reuse

Usage:
  python scripts/calibrate_camera_extrinsic.py [--output calibration_extrinsic.json] [--checkerboard 9 6] [--square-size 0.03]

  Interactive controls (during capture):
    'c' - Capture a frame and detect checkerboard
    'p' - Process all captures and compute extrinsic
    'q' - Quit without saving

Press 'p' to process once you have 3+ good captures from different angles.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except Exception:  # pragma: no cover - hardware dependent
    rs = None


def get_camera_intrinsics(profile) -> tuple[dict, dict]:
    """Extract intrinsics from RealSense profile for depth and color."""
    depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
    color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()

    depth_intrin = depth_profile.get_intrinsics()
    color_intrin = color_profile.get_intrinsics()

    depth_dict = {
        "fx": depth_intrin.fx,
        "fy": depth_intrin.fy,
        "ppx": depth_intrin.ppx,
        "ppy": depth_intrin.ppy,
        "width": depth_intrin.width,
        "height": depth_intrin.height,
    }
    color_dict = {
        "fx": color_intrin.fx,
        "fy": color_intrin.fy,
        "ppx": color_intrin.ppx,
        "ppy": color_intrin.ppy,
        "width": color_intrin.width,
        "height": color_intrin.height,
    }
    return depth_dict, color_dict


def deproject_pixel_to_point(
    intrin: dict, pixel_x: float, pixel_y: float, depth_value: float
) -> np.ndarray:
    """Deproject a pixel + depth to 3D point using intrinsics.
    Returns [x, y, z] in camera frame (meters).
    """
    fx, fy = intrin["fx"], intrin["fy"]
    ppx, ppy = intrin["ppx"], intrin["ppy"]
    x = (pixel_x - ppx) * depth_value / fx
    y = (pixel_y - ppy) * depth_value / fy
    z = depth_value
    return np.array([x, y, z])


def detect_checkerboard(image: np.ndarray, pattern_size: tuple[int, int]) -> Optional[np.ndarray]:
    """Detect checkerboard corners in grayscale image.
    Returns (N, 2) array of corner positions, or None if not found.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if ret:
        # Refine corners to sub-pixel accuracy
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        return corners.reshape(-1, 2)
    return None


def compute_extrinsic_solvepnp(
    object_points: np.ndarray, image_points: np.ndarray, color_intrin: dict
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Compute extrinsic (R, t) from depth frame to color frame using solvePnP.
    
    object_points: (N, 3) 3D points in depth camera frame
    image_points: (N, 2) 2D points in color image
    color_intrin: color camera intrinsics dict
    
    Returns (R, t) or None if failed.
    """
    camera_matrix = np.array(
        [
            [color_intrin["fx"], 0, color_intrin["ppx"]],
            [0, color_intrin["fy"], color_intrin["ppy"]],
            [0, 0, 1],
        ]
    )
    dist_coeffs = np.zeros(4)  # Assume no distortion for now

    success, rvec, tvec = cv2.solvePnP(
        object_points, image_points, camera_matrix, dist_coeffs, useExtrinsicGuess=False
    )
    if success:
        R, _ = cv2.Rodrigues(rvec)
        return R, tvec.flatten()
    return None


def reprojection_error(
    object_points: np.ndarray,
    image_points: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
    color_intrin: dict,
) -> float:
    """Compute reprojection error (mean Euclidean distance in pixels)."""
    camera_matrix = np.array(
        [
            [color_intrin["fx"], 0, color_intrin["ppx"]],
            [0, color_intrin["fy"], color_intrin["ppy"]],
            [0, 0, 1],
        ]
    )

    # Transform 3D points from depth frame to color frame
    pts_color = (R @ object_points.T + t.reshape(3, 1)).T  # (N, 3)

    # Project to color image
    pts_2d = (camera_matrix @ pts_color.T).T
    pts_2d = pts_2d[:, :2] / pts_2d[:, 2:3]

    error = np.linalg.norm(pts_2d - image_points, axis=1).mean()
    return error


def interactive_capture(
    pattern_size: tuple[int, int] = (9, 6),
    square_size: float = 0.03,
    output_file: str = "calibration_extrinsic.json",
):
    """Interactively capture checkerboards and compute extrinsic."""
    if rs is None:
        print("pyrealsense2 not available.")
        return 1

    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30)

    profile = pipeline.start(cfg)
    depth_intrin_dict, color_intrin_dict = get_camera_intrinsics(profile)

    print("\n=== RealSense Camera Intrinsics ===")
    print(f"Depth:  {depth_intrin_dict}")
    print(f"Color:  {color_intrin_dict}")

    captured_frames = []

    try:
        print("\n=== Interactive Capture Mode ===")
        print("Controls:")
        print("  'c' - Capture frame and detect checkerboard")
        print("  'p' - Process all captures and compute extrinsic")
        print("  'q' - Quit")
        print(f"\nShow a {pattern_size[0]}x{pattern_size[1]} checkerboard (~{square_size}m squares)")
        print("Capture from multiple angles for accuracy.\n")

        while True:
            frames = pipeline.wait_for_frames(timeout_ms=1000)
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()

            if not depth_frame or not color_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            # Display live
            display = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
            cv2.putText(
                display,
                f"Captured: {len(captured_frames)} | Press 'c' to capture, 'p' to process, 'q' to quit",
                (30, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.imshow("Calibration Capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c"):
                corners = detect_checkerboard(color_image, pattern_size)
                if corners is None:
                    print("Checkerboard not detected. Try a different angle or lighting.")
                    continue

                print(f"✓ Checkerboard #{len(captured_frames) + 1} detected ({len(corners)} corners)")

                # Extract 3D points from depth image
                object_points_3d = []
                image_points_2d = []

                for corner_idx, (px, py) in enumerate(corners):
                    px_int, py_int = int(round(px)), int(round(py))
                    # Clamp to image bounds
                    px_int = max(0, min(px_int, depth_image.shape[1] - 1))
                    py_int = max(0, min(py_int, depth_image.shape[0] - 1))

                    depth_mm = depth_image[py_int, px_int]
                    depth_m = depth_mm / 1000.0

                    if depth_m <= 0 or depth_m > 3.0:  # Invalid or too far
                        continue

                    pt_3d = deproject_pixel_to_point(depth_intrin_dict, px, py, depth_m)
                    object_points_3d.append(pt_3d)
                    image_points_2d.append([px, py])

                if len(object_points_3d) < 4:
                    print(f"  Warning: only {len(object_points_3d)} valid 3D points. Skipping this capture.")
                    continue

                captured_frames.append(
                    {
                        "object_points": np.array(object_points_3d),
                        "image_points": np.array(image_points_2d),
                    }
                )
                print(f"  Stored {len(object_points_3d)} valid 3D->2D correspondences.")

            elif key == ord("p"):
                if len(captured_frames) < 1:
                    print("Need at least 1 capture.")
                    continue

                print(f"\nProcessing {len(captured_frames)} captures...")
                all_object = np.vstack([f["object_points"] for f in captured_frames])
                all_image = np.vstack([f["image_points"] for f in captured_frames])

                result = compute_extrinsic_solvepnp(all_object, all_image, color_intrin_dict)
                if result is None:
                    print("solvePnP failed. Try different captures.")
                    continue

                R, t = result
                error = reprojection_error(all_object, all_image, R, t, color_intrin_dict)

                print("\n=== Calibration Result ===")
                print(f"Rotation (R) shape: {R.shape}")
                print(R)
                print(f"Translation (t) shape: {t.shape}")
                print(t)
                print(f"Reprojection error: {error:.3f} pixels")

                # Save to JSON
                cal_dict = {
                    "depth_intrinsics": depth_intrin_dict,
                    "color_intrinsics": color_intrin_dict,
                    "extrinsic_depth_to_color": {
                        "rotation_matrix": R.tolist(),
                        "translation_vector": t.tolist(),
                    },
                    "reprojection_error_pixels": float(error),
                    "num_captures": len(captured_frames),
                }

                with open(output_file, "w") as f:
                    json.dump(cal_dict, f, indent=2)

                print(f"\nCalibration saved to {output_file}")
                break

        cv2.destroyAllWindows()
        return 0

    finally:
        pipeline.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calibrate RealSense depth-to-color extrinsic using checkerboard")
    parser.add_argument(
        "--output", "-o", help="Output JSON filename", default="calibration_extrinsic.json"
    )
    parser.add_argument(
        "--checkerboard",
        nargs=2,
        type=int,
        default=[9, 6],
        help="Checkerboard pattern size (cols rows)",
    )
    parser.add_argument("--square-size", type=float, default=0.03, help="Checkerboard square size (meters)")
    args = parser.parse_args(argv)

    return interactive_capture(
        pattern_size=tuple(args.checkerboard),
        square_size=args.square_size,
        output_file=args.output,
    )


if __name__ == "__main__":
    sys.exit(main())
