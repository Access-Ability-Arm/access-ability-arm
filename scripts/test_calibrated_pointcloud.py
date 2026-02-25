"""
Example script showing how to integrate camera calibration into the main image processing pipeline.

This script demonstrates:
1. Loading calibration from calibration_extrinsic.json
2. Using PointCloudProcessor with calibration
3. Creating aligned point clouds for grasp planning

Usage:
  python scripts/test_calibrated_pointcloud.py [--calibration calibration_extrinsic.json]
"""

from pathlib import Path
import sys

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pyrealsense2 as rs
except ImportError:
    print("pyrealsense2 not available. This script requires RealSense camera.")
    sys.exit(1)

try:
    import open3d as o3d
except ImportError:
    print("open3d not available. Install with: pip install open3d")
    sys.exit(1)

from aaa_vision.calibration import CameraCalibration, try_load_calibration
from aaa_vision.point_cloud import PointCloudProcessor


def capture_and_process_with_calibration(calibration_file=None):
    """
    Capture RealSense frames and create calibrated point cloud.
    
    Args:
        calibration_file: Path to calibration JSON (uses default if None)
    """
    print("\n=== Calibrated Point Cloud Capture ===\n")
    
    # Load calibration
    try:
        if calibration_file:
            calibration = CameraCalibration.load_from_json(calibration_file)
            print(f"✓ Loaded calibration from: {calibration_file}")
        else:
            calibration = try_load_calibration()
            if calibration:
                print(f"✓ Auto-loaded calibration from: {calibration.calibration_file}")
            else:
                print("⚠ No calibration found. Using default (unaligned) point cloud.")
    except Exception as e:
        print(f"⚠ Failed to load calibration: {e}")
        print("Using default (unaligned) point cloud.")
        calibration = None
    
    if calibration:
        print(f"  Reprojection error: {calibration.reprojection_error_pixels:.2f} pixels")
        print(f"  Based on {calibration.num_captures} captures")
        print()
    
    # Initialize RealSense
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30)
    
    profile = pipeline.start(cfg)
    
    # Align depth to color for proper correspondence
    align = rs.align(rs.stream.color)
    
    try:
        print("Warming up camera...")
        for _ in range(5):
            pipeline.wait_for_frames()
        
        print("Capturing frame...")
        frames = pipeline.wait_for_frames(timeout_ms=5000)
        
        aligned = align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        
        if not depth_frame or not color_frame:
            print("Failed to get frames.")
            return 1
        
        # Extract frames
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())
        
        print(f"  Depth: {depth_image.shape}, Color: {color_image.shape}")
        
        # Initialize point cloud processor with optional calibration
        processor = PointCloudProcessor(
            calibration=calibration,
            auto_load_calibration=False  # Already loaded above
        )
        
        # Create point cloud from depth + color
        pcd = processor.create_from_depth(depth_image, color_image)
        print(f"✓ Created point cloud: {len(pcd.points)} points")
        
        # Apply calibration extrinsic (transforms depth frame -> color frame)
        if calibration:
            pcd = processor.apply_calibration(pcd)
            print("✓ Applied calibration transform (depth -> color frame)")
        
        # Preprocess
        pcd = processor.preprocess(pcd, voxel_size=0.005)
        print(f"✓ Preprocessed: {len(pcd.points)} points after downsampling")
        
        # Print statistics
        points = np.asarray(pcd.points)
        print(f"\nPoint cloud statistics (frame coordinates):")
        print(f"  X: [{points[:, 0].min():.3f}, {points[:, 0].max():.3f}] m")
        print(f"  Y: [{points[:, 1].min():.3f}, {points[:, 1].max():.3f}] m")
        print(f"  Z: [{points[:, 2].min():.3f}, {points[:, 2].max():.3f}] m")
        
        # Optionally visualize
        print("\nOpening visualization (close window to exit)...")
        o3d.visualization.draw_geometries(
            [pcd],
            window_name="Calibrated Point Cloud" if calibration else "Default Point Cloud"
        )
        
        return 0
        
    finally:
        pipeline.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test calibrated point cloud capture")
    parser.add_argument(
        "--calibration", "-c",
        help="Path to calibration JSON file",
        default=None
    )
    args = parser.parse_args()
    
    exit_code = capture_and_process_with_calibration(args.calibration)
    sys.exit(exit_code)
