# RealSense RGB-Depth Camera Alignment & Calibration Guide

## Overview

This guide explains how to align the RealSense D435 RGB and depth cameras using a checkerboard calibration pattern. The calibration computes the extrinsic transform (rotation + translation) from the depth camera frame to the color camera frame.

The alignment ensures that when you generate point clouds, the 3D coordinates are correctly mapped to the RGB pixels.

## Quick Start

### 1. Generate a Checkerboard Pattern

```bash
# Generate a 9×6 checkerboard (standard)
python scripts/generate_checkerboard.py

# Or save for printing
python scripts/generate_checkerboard.py --square-size-mm 30 --output checkerboard.png
```

The checkerboard will display on your screen. You can:
- View it live on screen and hold in front of the camera
- Print it on standard paper at 100% scale
- Display on another monitor or tablet

### 2. Debug Checkerboard Detection (optional)

If OpenCV can't detect your checkerboard:

```bash
python scripts/debug_checkerboard.py
```

**Controls:**
- **`c`** — Try to detect checkerboard
- **`t`** — Auto-trial different pattern sizes
- **`h`** — Show image quality metrics (sharpness, contrast, brightness)
- **`s`** — Save frame for offline analysis
- **`q`** — Quit

**Tips:**
- Good lighting is critical (overhead light + dark background works well)
- Checkerboard should be 0.5–1.5m away from camera
- Hold flat and perpendicular to camera lens
- Use high-contrast black/white (not gray)

### 3. Run Calibration

```bash
# Interactive capture mode
python scripts/calibrate_camera_extrinsic.py --checkerboard 9 6 --square-size 0.03 --output calibration_extrinsic.json
```

**Workflow:**
- Show checkerboard to camera in different poses
- Press **`c`** to capture and auto-detect
- Capture 3+ poses from different angles (left, right, top, bottom, tilted)
- Press **`p`** to compute the extrinsic transform
- Calibration is saved to `calibration_extrinsic.json`

**Output:** JSON file containing:
- Depth and color camera intrinsics
- Rotation matrix (3×3)
- Translation vector (3,)
- Reprojection error in pixels (should be <1 pixel for good calibration)

### 4. Test the Calibration

```bash
# Capture and visualize with calibration applied
python scripts/test_calibrated_pointcloud.py

# Or use explicit calibration file
python scripts/test_calibrated_pointcloud.py --calibration calibration_extrinsic.json
```

### 5. Apply to Existing Point Clouds

Transform previously saved point clouds using the new calibration:

```bash
# Transform and save
python scripts/apply_calibration.py logs/pointclouds/pointcloud_obj1_20260113_203318.npz --output transformed.ply

# Just show stats
python scripts/apply_calibration.py logs/pointclouds/pointcloud_obj1_20260113_203318.npz \
  --calibration calibration_extrinsic.json
```

## Configuration

### Via config.yaml

Add to your `config/config.yaml`:

```yaml
camera:
  calibration:
    enabled: true
    file: calibration_extrinsic.json  # Path to your calibration file
```

or leave `file: null` to auto-detect from project root.

### Programmatic Usage

```python
from aaa_vision.calibration import CameraCalibration
from aaa_vision.point_cloud import PointCloudProcessor

# Load calibration
calibration = CameraCalibration.load_from_json("calibration_extrinsic.json")

# Create point cloud processor with calibration
processor = PointCloudProcessor(calibration=calibration)

# Create point cloud from depth + color
pcd = processor.create_from_depth(depth_image, color_image)

# Apply calibration transform (depth frame -> color frame)
pcd = processor.apply_calibration(pcd)

# Now points are in color camera frame and aligned to RGB
```

## Understanding the Result

After calibration, your point cloud coordinates represent:
- **X** — Right/left relative to camera (camera's right = positive)
- **Y** — Down in image plane (down in image = positive)
- **Z** — Forward/backward from camera (away from lens = positive)

All in **meters**.

## Calibration Quality Metrics

- **Reprojection error < 0.5 pixels**: Excellent (professional-grade)
- **Reprojection error < 1.0 pixel**: Good (suitable for grasp planning)
- **Reprojection error 1–2 pixels**: Fair (acceptable for most applications)
- **Reprojection error > 2 pixels**: Poor (recalibrate with better captures)

## Troubleshooting

### "Checkerboard not detected"

1. **Check lighting**
   - Use overhead light to avoid shadows
   - Avoid glare on the checkerboard

2. **Check focus**
   - Use `realsense-viewer` to check if color feed is sharp
   - Adjust distance to camera

3. **Check pattern size**
   - Run `debug_checkerboard.py` and press `t` to auto-trial sizes
   - Common sizes: 8×6, 9×6, 10×7

4. **Check contrast**
   - Ensure pure black and white (not gray)
   - Test with a printed checkerboard instead of on-screen

### "solvePnP failed / Extrinsic computation failed"

1. **Need more captures**
   - Collect 5–10 captures from diverse angles
   - Include tilted/angled views (not just frontal)

2. **Bad depth readings**
   - Some pixels may have invalid depth (0 or >3m)
   - The script filters these, but try closer distance (0.5–1.5m)

3. **Pattern size mismatch**
   - Ensure `--checkerboard` matches your actual board (9×6 = 9 cols, 6 rows)
   - Run `debug_checkerboard.py` to auto-detect

### "Reprojection error is high (>2 pixels)"

1. **Recalibrate with better poses**
   - Capture from more angles (8+ captures)
   - Include off-center and tilted views

2. **Check camera focus**
   - Use RealSense viewer to confirm RGB is sharp

3. **Use a better checkerboard**
   - Print on high-quality paper with clear contrast
   - Avoid worn or faded boards

## Related Scripts

| Script | Purpose |
|--------|---------|
| `generate_checkerboard.py` | Generate calibration pattern |
| `debug_checkerboard.py` | Debug detection issues |
| `calibrate_camera_extrinsic.py` | Compute calibration from checkerboard |
| `apply_calibration.py` | Transform point clouds with calibration |
| `test_calibrated_pointcloud.py` | Capture and test calibrated point cloud |
| `align_and_view_pointcloud.py` | Quick visualization of aligned point cloud (uses SDK-only alignment) |

## Next Steps

1. **Grasp Planning**: Use calibrated point clouds with AnyGrasp / GraspNet
2. **Workspace Definition**: Define robot workspace with calibrated coordinates
3. **Validation**: Capture same scene with both RGB and depth, verify alignment visually

## References

- RealSense D435 specs: [docs/hardware/realsense-d435-specs.md](../../docs/hardware/realsense-d435-specs.md)
- Grasp planning roadmap: [docs/grasp_planning_report.md](../../docs/grasp_planning_report.md)
- OpenCV solvePnP: https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html#ga357634eb630715d342d331ccc5f1d30d
