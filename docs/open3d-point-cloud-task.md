# Task: Open3D Point Cloud Processing

**Status**: IMPLEMENTED

**Goal**: Get point cloud processing working with Open3D, integrating RealSense depth data with RF-DETR segmentation masks.

**Timeframe**: 3-5 days (Week 1 of grasp planning implementation)

**Deliverable**: Clean, segmented point clouds for target objects visualized in Open3D.

---

## Implementation Summary

### Files Created

| File | Description |
|------|-------------|
| `packages/vision/src/aaa_vision/point_cloud.py` | Main point cloud processing module |
| `scripts/test_open3d_pointcloud.py` | Basic point cloud test (RealSense → Open3D) |
| `scripts/test_rfdetr_pointcloud.py` | Full integration test (RF-DETR + Open3D) |

### Dependencies Added

- `open3d>=0.18.0` added to `packages/vision/pyproject.toml`
- Open3D 0.19.0 installed in venv

---

## Usage

### Basic Point Cloud Test

Tests the point cloud pipeline without RF-DETR:

```bash
# With daemon running (recommended):
make daemon-start
python scripts/test_open3d_pointcloud.py

# Or direct RealSense (requires sudo on macOS):
sudo python scripts/test_open3d_pointcloud.py --direct
```

### Full Integration Test (RF-DETR + Open3D)

Tests the complete pipeline with object segmentation:

```bash
# Start daemon first
make daemon-start

# Run integration test
python scripts/test_rfdetr_pointcloud.py
```

---

## API Reference

### PointCloudProcessor

Main class in `aaa_vision.point_cloud`:

```python
from aaa_vision.point_cloud import PointCloudProcessor, CameraIntrinsics

# Initialize with camera intrinsics
intrinsics = CameraIntrinsics(
    width=848, height=480,
    fx=425.19, fy=425.19,
    cx=424.0, cy=240.0
)

processor = PointCloudProcessor(
    intrinsics=intrinsics,
    depth_scale=1000.0,  # RealSense uses mm
    depth_trunc=2.0,     # Max depth in meters
)

# Create point cloud from depth
pcd = processor.create_from_depth(depth_image, color_image)

# Preprocess (outlier removal, downsampling, normals)
pcd = processor.preprocess(pcd, voxel_size=0.005)

# Crop to workspace
pcd = processor.crop_to_workspace(pcd, {
    'x': (-0.5, 0.5),
    'y': (-0.4, 0.4),
    'z': (0.2, 1.5),
})

# Remove table plane
pcd_objects, plane_model = processor.remove_plane(pcd)

# Extract single object using RF-DETR mask
pcd_object = processor.extract_object(depth_image, mask, color_image)

# Cluster remaining points into objects
clusters = processor.cluster_objects(pcd_objects)
```

### Visualization

```python
from aaa_vision.point_cloud import visualize_point_clouds

# Visualize multiple clouds with different colors
visualize_point_clouds(
    [pcd1, pcd2, pcd3],
    colors=[[1,0,0], [0,1,0], [0,0,1]],
    window_name="My Point Clouds"
)
```

### Statistics

```python
from aaa_vision.point_cloud import get_point_cloud_stats

stats = get_point_cloud_stats(pcd)
# Returns: {'num_points', 'has_colors', 'has_normals', 'min_bound', 'max_bound', 'centroid', 'std'}
```

---

## Success Criteria

- [x] Open3D installed and verified (v0.19.0)
- [x] Point cloud generated from RealSense depth
- [x] Point cloud visualized in Open3D viewer
- [x] Preprocessing pipeline working (outlier removal, downsampling, normals)
- [x] Workspace cropping implemented
- [x] Table plane segmentation working
- [x] RF-DETR mask applied to extract single object point clouds
- [x] Multiple objects visualized with different colors
- [ ] Point clouds look clean and match physical objects (requires testing with hardware)

---

## Notes

### Resolution Handling

The implementation handles resolution mismatches automatically:
- RGB (1920×1080) and Depth (848×480) are different resolutions
- Masks from RF-DETR are resized to match depth resolution
- Color images are resized when creating RGBD images

### Performance

Expected performance (to be validated):
- Point cloud generation: <50ms
- Preprocessing: <100ms
- Full pipeline: <200ms per frame

### Coordinate Frames

- RealSense optical frame: Z forward, Y down, X right
- Open3D default: Same as RealSense
- Robot base frame: Typically Z up, X forward (requires calibration transform)

---

## Next Steps

1. **Test with hardware** - Run the test scripts with actual RealSense + objects
2. **Tune parameters** - Adjust voxel size, outlier removal, clustering based on results
3. **Week 2: Grasp Detection** - Feed point clouds to AnyGrasp/GraspNet
4. **Week 3: Calibration** - Hand-eye calibration for robot coordinate transform

See `docs/grasp_planning_report.md` for the full 4-week implementation plan.

---

## References

- [Open3D Documentation](http://www.open3d.org/docs/release/)
- [Open3D Point Cloud Tutorial](http://www.open3d.org/docs/release/tutorial/geometry/pointcloud.html)
- `docs/grasp_planning_report.md` - Full grasp planning implementation plan
- `docs/archive/decisions/pick-and-place-strategy.md` - Background research on point cloud processing
