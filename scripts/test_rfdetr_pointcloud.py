#!/usr/bin/env python3
"""
Full integration test: RealSense + RF-DETR + Open3D point clouds.

This script tests the complete pipeline:
1. Capture RGB-D from RealSense (via daemon)
2. Run RF-DETR segmentation on RGB
3. Extract point cloud for each detected object using masks
4. Visualize object point clouds

Usage:
    # With daemon running:
    python scripts/test_rfdetr_pointcloud.py
"""

import os
import sys
import time

# Add packages to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "packages", "core", "src")
)
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "packages", "vision", "src")
)

import numpy as np


def main():
    print("=" * 60)
    print("RF-DETR + OPEN3D POINT CLOUD INTEGRATION TEST")
    print("=" * 60)

    # Check dependencies
    try:
        import open3d as o3d

        print(f"Open3D version: {o3d.__version__}")
    except ImportError:
        print("ERROR: Open3D not installed")
        return 1

    # Import modules
    from aaa_core.daemon.camera_client_socket import CameraClientSocket
    from aaa_vision.point_cloud import (
        PointCloudProcessor,
        CameraIntrinsics,
        visualize_point_clouds,
        get_point_cloud_stats,
    )
    from aaa_vision.rfdetr_seg import RFDETRSeg

    # Connect to daemon
    print("\n[1] Connecting to camera daemon...")
    client = CameraClientSocket()

    if not client.connect():
        print("ERROR: Could not connect to daemon.")
        print("Start daemon with: make daemon-start")
        return 1

    print("    Connected!")

    # Initialize RF-DETR
    print("\n[2] Initializing RF-DETR segmentation...")
    t0 = time.time()
    detector = RFDETRSeg()
    t1 = time.time()
    print(f"    RF-DETR loaded in {t1 - t0:.1f}s")

    # Capture frame
    print("\n[3] Capturing frame...")

    # Get a few frames to stabilize
    for _ in range(5):
        client.get_frame()
        time.sleep(0.1)

    frame = client.get_frame()
    if frame is None:
        print("ERROR: Failed to get frame")
        client.disconnect()
        return 1

    color_image, depth_image, metadata = frame
    print(f"    Color: {color_image.shape}")
    print(f"    Depth: {depth_image.shape}")

    # Run RF-DETR detection
    print("\n[4] Running RF-DETR segmentation...")
    t0 = time.time()

    # RF-DETR expects RGB, daemon provides BGR
    color_rgb = color_image[:, :, ::-1].copy()
    detections = detector.detect(color_rgb)

    t1 = time.time()
    print(f"    Detected {len(detections)} objects in {(t1 - t0) * 1000:.0f}ms")

    for i, det in enumerate(detections):
        has_mask = det.mask is not None
        mask_pixels = np.sum(det.mask) if has_mask else 0
        print(
            f"    [{i}] {det.label}: conf={det.confidence:.2f}, mask={mask_pixels:,} pixels"
        )

    if len(detections) == 0:
        print("\n    No objects detected. Try pointing camera at objects.")
        client.disconnect()
        return 0

    # Initialize point cloud processor
    print("\n[5] Creating point clouds for detected objects...")

    # Get intrinsics (use depth image dimensions)
    intrinsics = CameraIntrinsics(
        width=depth_image.shape[1],
        height=depth_image.shape[0],
        fx=425.19,
        fy=425.19,
        cx=depth_image.shape[1] / 2,
        cy=depth_image.shape[0] / 2,
    )

    processor = PointCloudProcessor(
        intrinsics=intrinsics,
        depth_scale=1000.0,
        depth_trunc=2.0,
    )

    # Extract point cloud for each detected object
    object_clouds = []
    object_labels = []

    for i, det in enumerate(detections):
        if det.mask is None:
            print(f"    [{i}] {det.label}: No mask, skipping")
            continue

        t0 = time.time()
        pcd = processor.extract_object(
            depth_image,
            det.mask,
            color_image,
            preprocess=True,
        )
        t1 = time.time()

        stats = get_point_cloud_stats(pcd)

        if stats["num_points"] < 50:
            print(f"    [{i}] {det.label}: Only {stats['num_points']} points, skipping")
            continue

        print(
            f"    [{i}] {det.label}: {stats['num_points']:,} points, "
            f"centroid={[f'{x:.3f}' for x in stats['centroid']]}, "
            f"time={((t1 - t0) * 1000):.0f}ms"
        )

        object_clouds.append(pcd)
        object_labels.append(f"{det.label} ({det.confidence:.0%})")

    client.disconnect()

    if len(object_clouds) == 0:
        print("\n    No valid point clouds extracted.")
        print("    Check that objects have valid depth data.")
        return 0

    # Also create full scene point cloud for context
    print("\n[6] Creating scene point cloud...")
    pcd_scene = processor.create_from_depth(depth_image, color_image)
    pcd_scene = processor.preprocess(pcd_scene, voxel_size=0.01)
    scene_stats = get_point_cloud_stats(pcd_scene)
    print(f"    Scene: {scene_stats['num_points']:,} points")

    # Visualize
    print("\n" + "=" * 60)
    print("VISUALIZATION")
    print("=" * 60)
    print("Opening Open3D viewer...")
    print("\nPoint clouds shown:")
    print("  - Gray: Full scene (faded)")

    colors_list = [
        [1, 0, 0],  # Red
        [0, 1, 0],  # Green
        [0, 0, 1],  # Blue
        [1, 1, 0],  # Yellow
        [1, 0, 1],  # Magenta
        [0, 1, 1],  # Cyan
    ]

    for i, label in enumerate(object_labels):
        color = colors_list[i % len(colors_list)]
        print(f"  - RGB{color}: {label}")

    print("\nControls:")
    print("  - Left click + drag: Rotate")
    print("  - Scroll: Zoom")
    print("  - Q or Esc: Close")

    # Prepare visualization
    clouds_to_show = []
    colors = []

    # Scene (faded gray)
    pcd_scene.paint_uniform_color([0.5, 0.5, 0.5])
    # Make scene semi-transparent by reducing points
    pcd_scene_display = pcd_scene.voxel_down_sample(0.02)
    clouds_to_show.append(pcd_scene_display)
    colors.append([0.5, 0.5, 0.5])

    # Object clouds
    for i, pcd in enumerate(object_clouds):
        clouds_to_show.append(pcd)
        colors.append(colors_list[i % len(colors_list)])

    visualize_point_clouds(clouds_to_show, colors, "RF-DETR + Point Cloud")

    print("\nTest completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
