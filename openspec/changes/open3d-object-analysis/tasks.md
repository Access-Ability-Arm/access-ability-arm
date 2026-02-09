## 1. Depth-RGB Alignment

- [x] 1.1 Enable `rs.align(rs.stream.depth)` in `realsense_camera.py` `__init__()` and produce aligned 848x480 color frame in `get_frame_stream()`. Update return signature to `(success, color_1080p, depth, aligned_color_480p)`.
- [x] 1.2 Update `camera_daemon_socket.py` `_capture_loop()` to get all 3 frames from `get_frame_stream()`. Update `_broadcast_frame()` to send 4-segment protocol: `[rgb_size, depth_size, aligned_rgb_size, metadata_size]` header + data. Cache `self.latest_aligned_color`.
- [x] 1.3 Update `daemon_image_processor.py` to parse the new 4-segment message format (detect 16-byte header vs 12-byte for backward compat). Store `self._last_aligned_color`.
- [x] 1.4 Update `image_processor.py` `_capture_frame()` to store aligned color from `get_frame_stream()` return. Expose via property.
- [x] 1.5 Update `main_window.py` to capture `self.frozen_aligned_color` at freeze time alongside existing frozen frames. Update `get_object_depth_points()` to use aligned pair instead of coordinate scaling.

## 2. ObjectAnalyzer Core

- [x] 2.1 Create `packages/vision/src/aaa_vision/object_analyzer.py` with dataclasses: `PlaneInfo`, `ShapeEstimate`, `ObjectAnalysis`.
- [x] 2.2 Implement `_extract_table_plane()` using `PointCloudProcessor.remove_plane()` with vertical-normal validation (dot product > 0.8).
- [x] 2.3 Implement `_detect_top_plane()`: sort object points by Y, take upper 20%, RANSAC plane fit, accept if horizontal normal and inlier ratio > 30%.
- [x] 2.4 Implement `_characterize_main_body()`: statistical outlier removal + DBSCAN largest cluster selection via `PointCloudProcessor.preprocess()` and `cluster_objects()`. Return cleaned point cloud and characteristic radius.
- [x] 2.5 Implement `_compute_curvature_profile()`: k=30 neighborhood via `scipy.spatial.cKDTree`, normal covariance eigenvalues, median filter, classify flat/curved at threshold 0.01. Return `flat_ratio`, `curved_ratio`, `mean_curvature`.

## 3. Shape Estimation

- [x] 3.1 Add `pyransac3d>=0.6.0` to `packages/vision/pyproject.toml` dependencies.
- [x] 3.2 Implement sphere fitting using `pyransac3d.Sphere().fit()` with thresh=0.005.
- [x] 3.3 Implement box detection: OBB axes extraction, per-face point clustering (within 10% of extent), RANSAC plane fit per face, accept if inlier ratio > 50% and normal aligns with OBB axis (dot > 0.9). Confidence = confirmed_faces / 3.
- [x] 3.4 Implement cylinder fitting: OBB longest axis as cylinder axis, project points perpendicular, fit circle via `scipy.optimize.least_squares`, compute inliers within threshold.
- [x] 3.5 Implement `_estimate_shape()` orchestration: curvature pre-filter → candidate selection → RANSAC fitting → scoring (best inlier_ratio, "irregular" if < 0.4).

## 4. Grasp Planning

- [x] 4.1 Implement `_compute_grasp_point()` with per-shape heuristics: cylinder (centroid, perpendicular approach), box (largest face center, face-normal approach), sphere (centroid, top-down), irregular (centroid, top-down). Enforce 15mm table clearance.
- [x] 4.2 Implement `_check_graspable()`: validate grasp_width against GRIPPER_MAX_OPENING_M (66mm), GRIPPER_MIN_WIDTH_M (5mm), and minimum object height (5mm).
- [x] 4.3 Implement grasp confidence assignment: "high" (shape confidence > 0.7, visibility > 60%), "medium" (0.4-0.7 or 30-60% visibility), "low" (irregular, <200 points, or <30% visibility).
- [x] 4.4 Implement `analyze()` method orchestrating full pipeline: table plane → main body → curvature → shape → top plane → grasp point → graspability → confidence.
- [x] 4.5 Implement `analyze_from_file()` for loading .npz/.ply files and running analysis.

## 5. Test Infrastructure

- [x] 5.1 Create `scripts/download_test_pointclouds.py`: download YCB objects (mug, mustard bottle, cracker box, sugar box, baseball, wood block) via ycb-tools, convert meshes to point clouds. Download GraspNet D435 scenes. Generate Stanford Bunny from Open3D builtins. Create `test_data/manifest.json` with expected shapes.
- [x] 5.2 Add `test_data/` to `.gitignore`.
- [x] 5.3 Create `scripts/test_object_analysis.py`: load point clouds from file or live capture, run `ObjectAnalyzer.analyze()`, print structured results, visualize in Open3D (table=gray, top=blue, body=green, grasp point=red sphere). Validate shape classification against manifest ground truth.

## 6. GUI Integration

- [x] 6.1 Update `_on_object_selected()` in `main_window.py`: show "Analyzing..." (amber) on button immediately, spawn background thread calling `_analyze_selected_object()`.
- [x] 6.2 Implement `_analyze_selected_object()`: build binary mask from frozen contour (scale 1920x1080 → 848x480), create object point cloud via `PointCloudProcessor.extract_object()` with aligned pair, create scene point cloud, run `ObjectAnalyzer().analyze()`, update button text (checkmark on success, failure message on error), call `_update_frozen_frame_highlight()`.
- [x] 6.3 Implement `_project_to_pixel()`: project 3D grasp point to 2D using RealSense depth intrinsics (`rs2_project_point_to_pixel`), scale from 848x480 to 1920x1080 for display. Fall back to default D435 intrinsics if unavailable.
- [x] 6.4 Implement `_draw_gripper_icon()`: draw two parallel rectangles (gripper fingers) at projected grasp point, oriented by approach direction. High-contrast rendering (3px white border + 2px colored fill). Color: green (high confidence), yellow (medium), orange (low), red+X (not graspable). User-friendly label (min 24px): "Ready to grasp", "Grasp possible", "Uncertain grasp", "Too large for gripper", "Too small to grasp".
- [x] 6.5 Wire gripper overlay into `_update_frozen_frame_highlight()` when `self.object_analysis` is set. Log technical details (shape, confidence, dimensions) to console at debug level.

## 7. Package Exports

- [x] 7.1 Add `ObjectAnalyzer`, `PlaneInfo`, `ShapeEstimate`, `ObjectAnalysis` to `packages/vision/src/aaa_vision/__init__.py` exports.
