# Quick Integration: Using Camera Calibration in Your Code

This document shows where and how to use the camera calibration in your application.

## Integration Points

### 1. Vision Package: Point Cloud Processor

The `PointCloudProcessor` now automatically loads calibration if available.

**Before (no calibration):**
```python
from aaa_vision.point_cloud import PointCloudProcessor

processor = PointCloudProcessor()
pcd = processor.create_from_depth(depth_image, color_image)
```

**After (with calibration - automatic):**
```python
from aaa_vision.point_cloud import PointCloudProcessor

# Automatically loads calibration from config/calibration_extrinsic.json if present
processor = PointCloudProcessor(auto_load_calibration=True)
pcd = processor.create_from_depth(depth_image, color_image)

# Apply calibration transform
pcd = processor.apply_calibration(pcd)
```

**With explicit calibration:**
```python
from aaa_vision.point_cloud import PointCloudProcessor
from aaa_vision.calibration import CameraCalibration

calibration = CameraCalibration.load_from_json("config/calibration_extrinsic.json")

processor = PointCloudProcessor(
    calibration=calibration,
    auto_load_calibration=False
)

pcd = processor.create_from_depth(depth_image, color_image)
pcd = processor.apply_calibration(pcd)  # Apply transform
```

### 2. Core Package: Configuration

The `AppConfig` now includes calibration settings:

```python
from aaa_core.config.settings import app_config

# Check if calibration is enabled
if app_config.camera_calibration_enabled:
    print(f"Calibration file: {app_config.camera_calibration_file}")
```

### 3. Main Application Integration

In your main application (e.g., `main.py` or GUI window):

```python
from aaa_vision.point_cloud import PointCloudProcessor
from aaa_vision.calibration import try_load_calibration
from aaa_core.config.settings import app_config

# At initialization
class MyGraspPlanningPipeline:
    def __init__(self):
        # Load calibration from config file path or auto-detect
        calibration = None
        if app_config.camera_calibration_enabled:
            calibration = try_load_calibration()
            if calibration:
                print(f"✓ Loaded camera calibration")
                print(f"  Reprojection error: {calibration.reprojection_error_pixels:.2f}px")
        
        # Create processor with optional calibration
        self.processor = PointCloudProcessor(
            calibration=calibration,
            auto_load_calibration=False
        )
    
    def process_realsense_frame(self, depth_frame, color_frame):
        """Process RealSense frame with calibration."""
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())
        
        # Create point cloud (depth frame coordinates)
        pcd = self.processor.create_from_depth(depth_image, color_image)
        
        # Apply calibration if available (transforms to color frame)
        pcd = self.processor.apply_calibration(pcd)
        
        # Continue with preprocessing, segmentation, grasp planning, etc.
        pcd = self.processor.preprocess(pcd, voxel_size=0.005)
        
        return pcd
```

## Configuration File (config.yaml)

Add to your `config/config.yaml`:

```yaml
camera:
  calibration:
    enabled: true
    file: config/calibration_extrinsic.json
```

Or leave `file: null` to auto-load from `config/calibration_extrinsic.json`.

## Minimal Example

```python
#!/usr/bin/env python3
"""Minimal example: capture RealSense frame and create calibrated point cloud."""

import numpy as np
import pyrealsense2 as rs
import open3d as o3d
from aaa_vision.point_cloud import PointCloudProcessor

def main():
    # Initialize RealSense
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30)
    profile = pipeline.start(cfg)
    
    # Align depth to color
    align = rs.align(rs.stream.color)
    
    try:
        # Capture one frame
        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        
        # Extract images
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())
        
        # Process with calibration (auto-loads if available)
        processor = PointCloudProcessor()
        pcd = processor.create_from_depth(depth_image, color_image)
        pcd = processor.apply_calibration(pcd)  # Apply transform if available
        
        print(f"Point cloud: {len(pcd.points)} points")
        print(f"Calibration applied: {processor.calibration is not None}")
        
        # Visualize
        o3d.visualization.draw_geometries([pcd])
        
    finally:
        pipeline.stop()

if __name__ == "__main__":
    main()
```

## Accessing Calibration Metadata

```python
from aaa_vision.calibration import try_load_calibration
import numpy as np

# Load calibration
cal = try_load_calibration()

if cal:
    print("Calibration info:")
    print(f"  File: {cal.calibration_file}")
    print(f"  Captures: {cal.num_captures}")
    print(f"  Error: {cal.reprojection_error_pixels:.3f} pixels")
    
    # Access transformation matrices
    R = cal.rotation_matrix  # (3, 3)
    t = cal.translation_vector  # (3,)
    
    # Get intrinsics
    depth_fx = cal.depth_intrinsics.get("fx")
    color_fx = cal.color_intrinsics.get("fx")
    
    print(f"  Depth focal length: {depth_fx}")
    print(f"  Color focal length: {color_fx}")
```

## Disabling Calibration

If you want to use unaligned point clouds (for comparison):

```python
# Explicitly disable auto-loading
processor = PointCloudProcessor(
    calibration=None,
    auto_load_calibration=False
)
pcd = processor.create_from_depth(depth_image, color_image)
# Points will be in depth frame (unaligned)
```

Or in config:
```yaml
camera:
  calibration:
    enabled: false
```

## Next Steps

1. **Create calibration**: Run `scripts/calibrate_camera_extrinsic.py`
2. **Test it**: Run `scripts/test_calibrated_pointcloud.py`
3. **Integrate**: Use patterns from this guide in your code
4. **Validate**: Visually compare aligned vs. unaligned point clouds

## Related Files

- [Camera Calibration User Guide](camera_calibration_guide.md)
- [Point Cloud Processing](../packages/vision/src/aaa_vision/point_cloud.py)
- [Calibration Module](../packages/vision/src/aaa_vision/calibration.py)
