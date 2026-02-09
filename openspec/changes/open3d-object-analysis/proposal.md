## Why

The Access Ability Arm can detect and select objects, but has no understanding of their 3D geometry. Without shape analysis and grasp planning, the system cannot determine *how* to pick up a selected object. This change adds the analysis layer that bridges "I see an object" to "I know how to grasp it" -- a prerequisite for autonomous grasping.

Additionally, the current depth-RGB alignment is disabled, causing point clouds to have incorrect depth values at object edges. This must be fixed first for any geometry analysis to be accurate.

## What Changes

- **New `ObjectAnalyzer` class** that performs full 3D analysis of a selected object: table plane extraction, shape estimation (cylinder/box/sphere/irregular via curvature + RANSAC), grasp point computation with Lite6 gripper constraints, and graspability checking
- **Depth-RGB alignment fix** enabling `rs.align()` to produce pixel-aligned color+depth frames, threaded through daemon and processor pipelines. **BREAKING**: `get_frame_stream()` return signature changes to include aligned color frame; daemon socket protocol adds a fourth segment for aligned RGB data
- **GUI gripper overlay** that projects the computed grasp point onto the frozen frame as a color-coded gripper icon with user-friendly status text (e.g., "Ready to grasp", "Too large for gripper")
- **Auto-analysis on object selection** with "Analyzing..." feedback state on the selected button, running analysis in a background thread
- **Test infrastructure** with YCB/GraspNet point cloud downloads and a standalone analysis test script
- **New dependency**: `pyransac3d>=0.6.0` for primitive fitting

## Capabilities

### New Capabilities

- `object-analysis`: 3D shape estimation (cylinder, box, sphere, irregular), table/top plane detection, centroid computation, and main body characterization from point clouds
- `grasp-planning`: Grasp point computation with shape-aware heuristics, approach direction, gripper width calculation, graspability checking against Lite6 physical constraints, and confidence assessment
- `depth-alignment`: Dual-frame pipeline producing pixel-aligned 848x480 color+depth pairs alongside the 1920x1080 RGB video feed, threaded through daemon socket and image processors
- `grasp-visualization`: 3D-to-2D projection of grasp points onto the camera feed with color-coded gripper icons indicating graspability and confidence level

### Modified Capabilities

(No existing specs to modify)

## Impact

- **Core pipeline** (`realsense_camera.py`, `camera_daemon_socket.py`, `daemon_image_processor.py`, `image_processor.py`): Return signatures and socket protocol change for aligned frames
- **GUI** (`main_window.py`): New analysis trigger on object selection, gripper overlay rendering, button state management
- **Vision package** (`aaa_vision`): New `object_analyzer.py` module, new package exports
- **Dependencies**: Adds `pyransac3d>=0.6.0`, uses existing `open3d`, `scipy`
- **Daemon protocol**: Header grows from 3 segments to 4 (adds aligned RGB). Existing daemon clients must handle the new format
- **Test data**: New `test_data/` directory (gitignored) for YCB/GraspNet point clouds
