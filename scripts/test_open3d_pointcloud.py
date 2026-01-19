#!/usr/bin/env python3
"""
Test Open3D point cloud generation from RealSense depth.

This script tests the point cloud processing pipeline:
1. Capture depth from RealSense (via daemon or direct)
2. Create point cloud with Open3D
3. Preprocess (outlier removal, downsampling, normals)
4. Crop to workspace
5. Remove table plane
6. Visualize results

Usage:
    # With daemon running (recommended):
    python scripts/test_open3d_pointcloud.py

    # Direct RealSense (requires sudo on macOS):
    sudo python scripts/test_open3d_pointcloud.py --direct
"""

import argparse
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


def test_with_daemon():
    """Test point cloud using camera daemon."""
    from aaa_core.daemon.camera_client_socket import CameraClientSocket
    from aaa_vision.point_cloud import (
        CameraIntrinsics,
        PointCloudProcessor,
        get_point_cloud_stats,
        visualize_point_clouds,
    )

    print("Connecting to camera daemon...")
    client = CameraClientSocket()

    if not client.connect():
        print("ERROR: Could not connect to daemon.")
        print("Start daemon with: make daemon-start")
        return False

    print("Connected to daemon. Capturing frames...")

    # Get a few frames to stabilize
    for _ in range(5):
        client.get_frame()
        time.sleep(0.1)

    # Capture frame
    frame = client.get_frame()
    if frame is None:
        print("ERROR: Failed to get frame from daemon")
        client.disconnect()
        return False

    color_image, depth_image, metadata = frame
    print(f"Captured frame: color {color_image.shape}, depth {depth_image.shape}")

    # Get intrinsics from metadata if available
    if metadata and "intrinsics" in metadata:
        intr = metadata["intrinsics"]
        intrinsics = CameraIntrinsics(
            width=intr.get("width", depth_image.shape[1]),
            height=intr.get("height", depth_image.shape[0]),
            fx=intr.get("fx", 425.19),
            fy=intr.get("fy", 425.19),
            cx=intr.get("ppx", depth_image.shape[1] / 2),
            cy=intr.get("ppy", depth_image.shape[0] / 2),
        )
    else:
        # Use defaults for D435 at 848x480
        intrinsics = CameraIntrinsics(
            width=depth_image.shape[1],
            height=depth_image.shape[0],
            fx=425.19,
            fy=425.19,
            cx=depth_image.shape[1] / 2,
            cy=depth_image.shape[0] / 2,
        )

    client.disconnect()

    # Process point cloud
    return process_point_cloud(color_image, depth_image, intrinsics)


def test_direct_realsense():
    """Test point cloud with direct RealSense access."""
    try:
        import pyrealsense2 as rs
    except ImportError:
        print("ERROR: pyrealsense2 not installed")
        return False

    from aaa_vision.point_cloud import (
        CameraIntrinsics,
        PointCloudProcessor,
    )

    print("Initializing RealSense directly...")
    print("(Requires sudo on macOS)")

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)

    try:
        profile = pipeline.start(config)
        print("RealSense pipeline started")

        # Get intrinsics
        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        intr = depth_profile.get_intrinsics()
        intrinsics = CameraIntrinsics(
            width=intr.width,
            height=intr.height,
            fx=intr.fx,
            fy=intr.fy,
            cx=intr.ppx,
            cy=intr.ppy,
        )

        # Align depth to color
        align = rs.align(rs.stream.color)

        # Wait for frames to stabilize
        print("Waiting for camera to stabilize...")
        for _ in range(30):
            pipeline.wait_for_frames()

        # Capture frame
        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)

        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()

        if not depth_frame or not color_frame:
            print("ERROR: Failed to get frames")
            return False

        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        print(f"Captured frame: color {color_image.shape}, depth {depth_image.shape}")

    finally:
        pipeline.stop()

    return process_point_cloud(color_image, depth_image, intrinsics)


def process_point_cloud(color_image, depth_image, intrinsics):
    """Process and visualize point cloud."""
    from aaa_vision.point_cloud import (
        PointCloudProcessor,
        get_point_cloud_stats,
        visualize_point_clouds,
    )

    print("\n" + "=" * 50)
    print("POINT CLOUD PROCESSING")
    print("=" * 50)

    # Initialize processor
    processor = PointCloudProcessor(
        intrinsics=intrinsics,
        depth_scale=1000.0,  # RealSense depth is in mm
        depth_trunc=2.0,  # Max 2 meters
    )

    # Step 1: Create point cloud from depth
    print("\n[1] Creating point cloud from depth...")
    t0 = time.time()
    pcd_raw = processor.create_from_depth(depth_image, color_image)
    t1 = time.time()
    stats = get_point_cloud_stats(pcd_raw)
    print(f"    Points: {stats['num_points']:,}")
    print(f"    Time: {(t1 - t0) * 1000:.1f}ms")

    if stats["num_points"] == 0:
        print("ERROR: No points in cloud. Check depth image.")
        return False

    # Step 2: Preprocess
    print("\n[2] Preprocessing (outlier removal, downsampling, normals)...")
    t0 = time.time()
    pcd_preprocessed = processor.preprocess(
        pcd_raw,
        voxel_size=0.005,  # 5mm voxels
        nb_neighbors=20,
        std_ratio=2.0,
    )
    t1 = time.time()
    stats = get_point_cloud_stats(pcd_preprocessed)
    print(f"    Points: {stats['num_points']:,}")
    print(f"    Has normals: {stats['has_normals']}")
    print(f"    Time: {(t1 - t0) * 1000:.1f}ms")

    # Step 3: Crop to workspace
    print("\n[3] Cropping to workspace...")
    workspace_bounds = {
        "x": (-0.5, 0.5),  # 1m width
        "y": (-0.4, 0.4),  # 80cm height
        "z": (0.2, 1.5),  # 20cm to 1.5m depth
    }
    t0 = time.time()
    pcd_cropped = processor.crop_to_workspace(pcd_preprocessed, workspace_bounds)
    t1 = time.time()
    stats = get_point_cloud_stats(pcd_cropped)
    print(f"    Points: {stats['num_points']:,}")
    print(
        f"    Bounds: x={workspace_bounds['x']}, y={workspace_bounds['y']}, z={workspace_bounds['z']}"
    )
    print(f"    Time: {(t1 - t0) * 1000:.1f}ms")

    # Step 4: Remove table plane
    print("\n[4] Removing table plane (RANSAC)...")
    t0 = time.time()
    pcd_objects, plane_model = processor.remove_plane(
        pcd_cropped,
        distance_threshold=0.01,  # 1cm
    )
    t1 = time.time()
    stats = get_point_cloud_stats(pcd_objects)
    print(f"    Points after plane removal: {stats['num_points']:,}")
    if plane_model is not None:
        print(
            f"    Plane: {plane_model[0]:.3f}x + {plane_model[1]:.3f}y + {plane_model[2]:.3f}z + {plane_model[3]:.3f} = 0"
        )
    print(f"    Time: {(t1 - t0) * 1000:.1f}ms")

    # Step 5: Cluster objects
    print("\n[5] Clustering objects (DBSCAN)...")
    t0 = time.time()
    clusters = processor.cluster_objects(
        pcd_objects,
        eps=0.02,  # 2cm clustering distance
        min_points=50,  # Minimum 50 points per object
    )
    t1 = time.time()
    print(f"    Found {len(clusters)} object cluster(s)")
    for i, cluster in enumerate(clusters):
        cluster_stats = get_point_cloud_stats(cluster)
        print(
            f"    Cluster {i}: {cluster_stats['num_points']:,} points, centroid={[f'{x:.3f}' for x in cluster_stats['centroid']]}"
        )
    print(f"    Time: {(t1 - t0) * 1000:.1f}ms")

    # Visualize
    print("\n" + "=" * 50)
    print("VISUALIZATION")
    print("=" * 50)
    print("Opening Open3D viewer...")
    print("  - Red: Raw point cloud (downsampled for display)")
    print("  - Green: After preprocessing + workspace crop")
    print("  - Blue/Yellow/etc: Individual object clusters")
    print("\nControls:")
    print("  - Left click + drag: Rotate")
    print("  - Scroll: Zoom")
    print("  - Middle click + drag: Pan")
    print("  - Q or Esc: Close")

    # Prepare visualization
    clouds_to_show = []
    colors = []

    # Raw (heavily downsampled for comparison)
    pcd_raw_display = pcd_raw.voxel_down_sample(0.02)
    clouds_to_show.append(pcd_raw_display)
    colors.append([0.8, 0.2, 0.2])  # Red

    # Preprocessed + cropped
    clouds_to_show.append(pcd_cropped)
    colors.append([0.2, 0.8, 0.2])  # Green

    # Object clusters
    cluster_colors = [
        [0.2, 0.2, 0.8],  # Blue
        [0.8, 0.8, 0.2],  # Yellow
        [0.8, 0.2, 0.8],  # Magenta
        [0.2, 0.8, 0.8],  # Cyan
    ]
    for i, cluster in enumerate(clusters):
        clouds_to_show.append(cluster)
        colors.append(cluster_colors[i % len(cluster_colors)])

    visualize_point_clouds(clouds_to_show, colors, "Point Cloud Test")

    print("\nTest completed successfully!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test Open3D point cloud processing")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Use direct RealSense access instead of daemon",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("OPEN3D POINT CLOUD TEST")
    print("=" * 50)

    # Check Open3D
    try:
        import open3d as o3d

        print(f"Open3D version: {o3d.__version__}")
    except ImportError:
        print("ERROR: Open3D not installed. Run: pip install open3d")
        return 1

    if args.direct:
        success = test_direct_realsense()
    else:
        success = test_with_daemon()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
