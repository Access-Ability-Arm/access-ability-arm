# Plan: Open3D Object Analysis for Grasp Planning (Implemented)

## Context

The Access Ability Arm already has a working pipeline: RF-DETR detects objects, the user selects one via GUI buttons, and point clouds can be exported. What's missing is the **analysis layer** -- understanding the selected object's 3D geometry (shape, planes, centroid) and showing a visual grasp indicator. This bridges the gap between "I see objects" and "I know how to pick this up."

## What We're Building

A new `ObjectAnalyzer` class that, when an object is selected in the GUI, automatically:
1. Creates the object's Open3D point cloud from the frozen depth/RGB frames
2. Extracts the table plane, top plane (if flat), shape estimate, and centroid
3. Draws a gripper outline on the frozen frame at the recommended grasp point

Also: a standalone script to run analysis on saved `.npz`/`.ply` files for offline testing.

Additionally: **fix depth-RGB alignment** so point clouds are accurate. Currently disabled at [realsense_camera.py:116-122](packages/core/src/aaa_core/hardware/realsense_camera.py#L116-L122), causing misaligned depth lookups at object edges. The fix: always produce aligned frames alongside the high-res video feed.

---

## Prerequisite: Depth-RGB Alignment Fix

### Problem
The D435's RGB camera and IR depth sensor are ~50mm apart. Without alignment, an object's RF-DETR mask (from RGB) maps to wrong depth pixels at edges -- you get table depth where you expect object, corrupting point clouds.

### Solution: Dual-frame approach
Keep 1920x1080 RGB for video display. Always produce an aligned 848x480 RGB+depth pair for point cloud work. Cost: ~3-5ms/frame (negligible at 30fps).

### Files to modify

**`packages/core/src/aaa_core/hardware/realsense_camera.py`:**
- In `__init__()`: Create `self.align = rs.align(rs.stream.depth)` (line 122, currently `None`)
  - **Note**: `rs.align(rs.stream.depth)` aligns *color TO depth*, so both share the 848x480 depth grid. This is what we want -- pixel-perfect correspondence for point cloud generation. We are NOT aligning depth to color (which would upscale depth to 1080p and waste memory).
- In `get_frame_stream()`: After getting frames, also produce aligned pair:
  ```python
  # Align color TO depth so both share the 848x480 grid
  aligned_frames = self.align.process(frames)
  aligned_color = np.asanyarray(aligned_frames.get_color_frame().get_data())
  # depth stays the same (native resolution)
  ```
- Return signature changes: `(success, color_1080p, depth, aligned_color_480p)`

**`packages/core/src/aaa_core/daemon/camera_daemon_socket.py`:**
- `_capture_loop()` (line 306): Get all 3 frames from `get_frame_stream()`
- `_broadcast_frame()` (line 342): Add aligned color to message protocol
- Header becomes `[rgb_size, depth_size, aligned_rgb_size, metadata_size]`
- Cache `self.latest_aligned_color` alongside existing cached frames

**`packages/core/src/aaa_core/workers/daemon_image_processor.py`:**
- Parse the new 4-part message format
- Store `self._last_aligned_color` alongside existing `_last_rgb_frame`

**`packages/core/src/aaa_core/workers/image_processor.py`:**
- Store aligned color from `get_frame_stream()` return
- Expose via property for GUI to access at freeze time

**`packages/gui/src/aaa_gui/flet/main_window.py`:**
- At freeze time: store `self.frozen_aligned_color` (848x480) alongside existing frozen frames
- Point cloud extraction uses `frozen_aligned_color` + `frozen_depth_frame` (same resolution, pixel-aligned)
- Eliminates manual `scale_x = w_depth / w_rgb` coordinate mapping in `get_object_depth_points()`
- Contour coordinates from RF-DETR (1920x1080) still need scaling to 848x480 for point cloud mask, but the depth lookup is now correct

---

## Files to Create

### 1. `packages/vision/src/aaa_vision/object_analyzer.py` (NEW - primary file)

**Data structures:**

```python
@dataclass
class PlaneInfo:
    model: np.ndarray        # [a, b, c, d] plane equation
    normal: np.ndarray       # unit normal vector
    centroid: np.ndarray     # [x, y, z] center of plane points
    inlier_points: np.ndarray  # Nx3 array of points on the plane
    area_estimate: float     # estimated area in m^2

@dataclass
class ShapeEstimate:
    shape_type: str          # "cylinder", "box", "sphere", "irregular"
    confidence: float        # 0-1 (inlier ratio from best RANSAC fit)
    dimensions: dict         # shape-specific: e.g. {"height": 0.15, "radius": 0.04}
    oriented_bbox: Any       # Open3D OrientedBoundingBox
    curvature_profile: dict  # {"flat_ratio": 0.3, "curved_ratio": 0.7, "mean_curvature": 0.05}
    fit_residual: float      # RMSE of best primitive fit

@dataclass
class ObjectAnalysis:
    centroid: np.ndarray            # [x, y, z] main body center
    shape: ShapeEstimate
    table_plane: Optional[PlaneInfo]
    top_plane: Optional[PlaneInfo]  # None if no flat top
    main_body_points: np.ndarray    # Nx3 core points (outliers removed)
    main_body_radius: float         # characteristic radius from centroid
    grasp_point: np.ndarray         # [x, y, z] recommended grasp location
    grasp_approach: np.ndarray      # [nx, ny, nz] approach direction
    grasp_width: float              # required gripper opening in meters
    graspable: bool                 # False if object too large/small for Lite6 gripper
    grasp_confidence: float         # 0.0-1.0 probability (weighted: 40% shape confidence, 20% point count, 40% visibility)
    num_points: int
```

**`ObjectAnalyzer` class methods:**

| Method | Purpose |
|--------|---------|
| `analyze(object_pcd, scene_pcd) -> ObjectAnalysis` | Full analysis pipeline |
| `analyze_from_file(path) -> ObjectAnalysis` | Load .npz/.ply and analyze |
| `_extract_table_plane(scene_pcd) -> PlaneInfo` | RANSAC on scene, validate near-vertical normal |
| `_detect_top_plane(object_pcd, table_plane) -> PlaneInfo` | RANSAC on upper ~20% of object points, validate horizontal |
| `_compute_curvature_profile(object_pcd) -> dict` | Mean curvature per point, classify flat vs curved |
| `_estimate_shape(object_pcd) -> ShapeEstimate` | Curvature pre-filter + RANSAC primitive fitting |
| `_characterize_main_body(object_pcd) -> (pcd, radius)` | Outlier removal + largest DBSCAN cluster |
| `_compute_grasp_point(analysis_parts) -> (point, approach, width)` | Shape-aware grasp location (see detailed heuristics below) |
| `_check_graspable(shape, grasp_width) -> bool` | Verify object fits Lite6 gripper constraints |

**New dependency:** `pyransac3d>=0.6.0` (add to `packages/vision/pyproject.toml`)

**Shape estimation algorithm (RANSAC + curvature hybrid):**

**Step 1: Curvature Analysis** (pre-filter, ~100-300ms for 2000-5000 points)
- Normals are already computed by `preprocess()` via `pcd.estimate_normals()`
- For each point, compute covariance of normals in its k-nearest neighborhood
- Smallest eigenvalue of normal covariance ≈ local curvature estimate
- **Use k=30** (not 15) to smooth out D435 depth noise (~2-4mm at tabletop range)
- Apply median filter on raw curvature values before classification to suppress noise spikes
- Classify each point: `flat` (curvature < 0.01) or `curved` (curvature >= 0.01)
- Compute `flat_ratio` and `curved_ratio` for the whole object

```python
# Vectorized KNN via scipy for batch query (much faster than per-point Open3D KNN)
from scipy.spatial import cKDTree

points = np.asarray(pcd.points)
normals = np.asarray(pcd.normals)
tree = cKDTree(points)
_, all_idx = tree.query(points, k=30)  # batch KNN, returns (N, 30) index array

# Vectorized curvature: compute normal covariance eigenvalues per neighborhood
curvature = np.zeros(len(points))
for i in range(len(points)):
    neighbor_normals = normals[all_idx[i]]
    cov = np.cov(neighbor_normals.T)
    curvature[i] = np.min(np.linalg.eigvalsh(cov))

# Median filter to suppress noise spikes from D435 depth quantization
from scipy.ndimage import median_filter
# Sort by spatial locality (KDTree order), apply 1D median, unsort
# Alternatively: for each point, replace curvature with median of its k-neighbors' curvatures
for i in range(len(points)):
    neighbor_curvatures = curvature[all_idx[i]]
    curvature[i] = np.median(neighbor_curvatures)
```

**Why k=30 and median filtering?** The D435 has ~2-4mm depth noise at typical tabletop distances (0.3-0.8m). With k=15, surface normals are noisy enough that flat surfaces can appear curved, leading to incorrect shape classification. Larger neighborhoods + median filtering produce stable curvature estimates on real sensor data. YCB mesh test data (clean geometry) will work with either setting, so the test script should also validate with synthetic noise added to YCB point clouds.

**Step 2: Candidate Selection** (based on curvature profile)
- Always compute OBB via `pcd.get_oriented_bounding_box()` for dimensions
- `flat_ratio > 0.6` → try **box** first (OBB + flat-face confirmation, see below)
- `curved_ratio > 0.6` → try **sphere** first (pyransac3d `Sphere().fit()`)
- Mixed flat + curved → try **cylinder** (custom: fit circle to 2D projection perpendicular to OBB longest axis)

**Step 3: Primitive Fitting** (~50-200ms, only on plausible candidates)
- **Sphere**: `pyransac3d.Sphere().fit(points, thresh=0.005)` → center, radius, inliers
- **Box** (OBB + flat-face confirmation, NOT pyransac3d `Cuboid().fit()`):
  - `pyransac3d.Cuboid().fit()` is unreliable on single-viewpoint data (needs 3+ visible faces; we typically see 1-2)
  - Instead: compute OBB, then RANSAC-fit planes to the visible faces
  1. Compute OBB axes (3 principal directions from `pcd.get_oriented_bounding_box()`)
  2. For each OBB axis, project points onto that axis and take the "near face" cluster (points within 10% of extent from the nearest OBB face)
  3. RANSAC plane fit on each face cluster; accept if inlier ratio > 50% and plane normal aligns with OBB axis (dot product > 0.9)
  4. Box confidence = (number of confirmed flat faces) / 3, scaled by mean face inlier ratio
  5. Dimensions from OBB extents directly
  - This approach works with 1-2 visible faces (typical single-viewpoint scenario)
- **Cylinder**: Custom approach (pyransac3d cylinder has known accuracy issues on real data):
  1. OBB longest axis = candidate cylinder axis
  2. Project all points onto plane perpendicular to that axis
  3. Fit circle to 2D projection using least-squares (`scipy.optimize.least_squares`)
  4. Inliers = points within threshold of fitted cylinder surface
- Each fit returns an **inlier_ratio** = `len(inliers) / len(points)`

**Step 4: Scoring & Selection**
- Best shape = highest `inlier_ratio` among attempted fits
- `confidence = inlier_ratio` (0-1)
- If best `inlier_ratio < 0.4` → classify as "irregular"
- Store `fit_residual` = mean distance of inliers to fitted surface

**Top plane detection:**
1. Get object points, sort by Y (camera Y axis = down, so min Y = top in camera frame)
2. Take upper 20% slice
3. RANSAC plane fit on that slice
4. Accept if: normal is roughly vertical AND inlier ratio > 30%

**Grasp point computation (`_compute_grasp_point`) -- per-shape heuristics:**

The Lite6 gripper has specific physical constraints that inform grasp planning:
- **Max opening**: ~66mm (configurable via `GRIPPER_MAX_OPENING_M = 0.066`)
- **Finger length**: ~45mm
- **Min graspable width**: ~5mm (below this, object slips)
- **Table clearance**: grasp point must be at least 15mm above table plane to avoid collision

| Shape | Grasp Point | Approach Direction | Grasp Width |
|-------|------------|-------------------|-------------|
| **Cylinder** | Centroid of main body, clamped to ≥15mm above table | Perpendicular to cylinder axis, from the visible side (camera-facing) | `2 * cylinder_radius` |
| **Box** | Center of the largest visible face; if face center is <15mm from table, shift up to 15mm clearance | Along face normal, toward the camera side | Extent of the face along the shorter of its two dimensions |
| **Sphere** | Centroid | From above (top-down, `-Y` in camera frame) if clearance allows; otherwise from the side with most clearance from table | `2 * sphere_radius` |
| **Irregular** | Centroid of main body cluster, clamped to ≥15mm above table | Top-down (`-Y` in camera frame) as safest default | Narrowest OBB extent (most likely to fit gripper) |

**Graspability check (`_check_graspable`):**
- `graspable = False` if `grasp_width > GRIPPER_MAX_OPENING_M` (object too wide)
- `graspable = False` if `grasp_width < GRIPPER_MIN_WIDTH_M` (object too small to hold)
- `graspable = False` if object height < 5mm (too flat to pick up)
- Otherwise `graspable = True`

**Grasp confidence assignment (0.0-1.0 probability):**

Computed as a weighted score: `0.4 * shape_score + 0.2 * point_score + 0.4 * visibility`
- **shape_score**: shape fitting confidence (0.1 for "irregular", otherwise the RANSAC inlier ratio)
- **point_score**: `min(1.0, num_points / 1000)` -- saturates at 1000 points
- **visibility**: estimated from point cloud spread vs OBB surface area

GUI display thresholds:
- `>= 0.7`: green, "Ready to grasp (X%)"
- `>= 0.4`: yellow, "Grasp possible (X%)"
- `< 0.4`: orange, "Uncertain grasp (X%)"

**Single-viewpoint limitation:** The D435 sees only one side of an object. A mug from the front looks like a cylinder; from the handle side, it's irregular. The grasp planner operates only on visible geometry and the `grasp_confidence` field reflects this uncertainty. Back-side geometry is unknown -- the approach vector always comes from the camera-visible side to avoid grasping into unseen obstacles. This is an inherent limitation of single-camera systems; future work could add a second viewpoint or rotate the arm for a look-around scan.

**Reuse from existing code:**
- `PointCloudProcessor.remove_plane()` for table plane RANSAC ([point_cloud.py:234-266](packages/vision/src/aaa_vision/point_cloud.py#L234-L266))
- `PointCloudProcessor.preprocess()` for outlier removal + downsampling ([point_cloud.py:145-192](packages/vision/src/aaa_vision/point_cloud.py#L145-L192))
- `PointCloudProcessor.extract_object()` for mask-based extraction ([point_cloud.py:268-333](packages/vision/src/aaa_vision/point_cloud.py#L268-L333))
- `PointCloudProcessor.cluster_objects()` for DBSCAN ([point_cloud.py:335-370](packages/vision/src/aaa_vision/point_cloud.py#L335-L370))
- `get_point_cloud_stats()` for basic centroid/bounds ([point_cloud.py:431-461](packages/vision/src/aaa_vision/point_cloud.py#L431-L461))

### 2. `scripts/test_object_analysis.py` (NEW - test script)

Standalone script that:
- Loads a saved point cloud (.npz or .ply) from `logs/pointclouds/` or `test_data/`
- Runs `ObjectAnalyzer.analyze()`
- Prints structured results (planes, shape, centroid, grasp point, grasp confidence %)
- Visualizes in Open3D: object colored by region (table=gray, top=blue, body=green, grasp point=red sphere)
- Auto-downloads test data if manifest is missing (calls `download_test_pointclouds.py`)

```bash
# Single file (positional argument)
python scripts/test_object_analysis.py test_data/ycb/025_mug.ply

# With Open3D visualization
python scripts/test_object_analysis.py test_data/ycb/025_mug.ply --visualize

# Batch test against manifest (validates shape classification)
python scripts/test_object_analysis.py --manifest test_data/manifest.json

# Test all files in default manifest
python scripts/test_object_analysis.py --all
```

### 3. `scripts/download_test_pointclouds.py` (NEW - data setup script)

Downloads and prepares test point clouds from multiple sources:

**Procedural Primitives** (reliable shape ground truth, no network dependency):
- `cylinder.ply`: radius=0.03m, height=0.10m (5000 points)
- `box.ply`: 0.06 x 0.04 x 0.08m (5000 points)
- `sphere.ply`: radius=0.035m (5000 points)
- Generated with Open3D, saved to `test_data/primitives/`

**YCB Objects** (real-world shapes for validating shape estimation):
- `025_mug` (cylinder+handle), `006_mustard_bottle` (cylinder), `003_cracker_box` (box), `004_sugar_box` (box), `055_baseball` (sphere), `036_wood_block` (box)
- Source: `.tgz` archives from `http://ycb-benchmarks.s3-website-us-east-1.amazonaws.com/data/google/`
- Extracts `nontextured.ply` mesh from archive, converts to point cloud via `mesh.sample_points_uniformly(5000)`
- Saves to `test_data/ycb/`

**Open3D builtins** (irregular shape ground truth):
- Stanford Bunny → "irregular" shape ground truth
- Generated via `o3d.data.BunnyMesh()`, saved to `test_data/builtins/`

Script creates `test_data/manifest.json` mapping each file to its expected shape, enabling automated accuracy testing in `test_object_analysis.py`. Called automatically by the test script if test data is missing.

### 4. `packages/vision/src/aaa_vision/__init__.py` (MODIFY)

Add `ObjectAnalyzer` and dataclasses to package exports.

---

## Files to Modify

### 5. `packages/gui/src/aaa_gui/flet/main_window.py` (MODIFY)

**Changes in `_on_object_selected()` (~line 1479):**
- After setting `self.selected_object`, immediately show "Analyzing..." state on the selected button
- Spawn a background thread to run analysis
- Store result in `self.object_analysis: Optional[ObjectAnalysis]`
- On completion: update button to show result state; on failure: show "Analysis failed" and log error

**New method `_analyze_selected_object()`:**
1. Set button text to "Analyzing..." with a distinct color (e.g., amber/orange) so the user knows the system is working
2. Build binary mask from `frozen_detections["contours"][selected_object]` (1920x1080 coords, resize to 848x480)
3. Create object point cloud via `PointCloudProcessor.extract_object(frozen_depth_frame, mask, frozen_aligned_color)` -- aligned pair, same resolution
4. Create scene point cloud via `PointCloudProcessor.create_from_depth(frozen_depth_frame, frozen_aligned_color)` -- aligned pair
5. Run `ObjectAnalyzer().analyze(object_pcd, scene_pcd)`
6. On success: store result, restore button text with checkmark ("cup ✓"), call `_update_frozen_frame_highlight()` to redraw with gripper icon
7. On failure (exception or too few points): set `self.object_analysis = None`, update button text to original + " (no depth)" or " (analysis failed)", log the error for debugging. Do NOT crash or leave the UI in an indeterminate state.

**Accessibility principle**: Never leave the user wondering if the system heard them. ALS users navigating with limited input (eye tracking, switches) need clear, immediate feedback that their selection was received and is being processed. The "Analyzing..." state should appear within 1 frame update (~33ms) of the button press.

**New method `_draw_gripper_icon(img, analysis)`:**
1. Project `analysis.grasp_point` from 3D camera coords to 2D pixel using depth intrinsics (`rs2_project_point_to_pixel`)
2. Scale from depth resolution (848x480) to display resolution (1920x1080) for overlay
3. Draw gripper outline at that location:
   - Two parallel rectangles (gripper fingers) flanking the grasp point
   - Oriented based on `analysis.grasp_approach` direction
   - **High-contrast rendering**: white outer border (3px) + colored inner fill (2px) for visibility against any background
   - Color based on `graspable` and `grasp_confidence` (0.0-1.0):
     - Graspable + confidence >= 0.7: bright green
     - Graspable + confidence >= 0.4: yellow
     - Graspable + confidence < 0.4: orange
     - Not graspable: red with "X" through gripper icon
   - User-friendly text label (large font, minimum 24px at 1080p) with confidence percentage:
     - Graspable: "Ready to grasp (85%)" (green), "Grasp possible (55%)" (yellow), "Uncertain grasp (25%)" (orange)
     - Not graspable: "Too large for gripper" / "Too small to grasp" (red, no percentage)
   - **Do NOT show** raw technical values like "cylinder 0.85" -- end users don't need shape classification details. Log those to console for debugging.
4. Called from `_update_frozen_frame_highlight()` when `self.object_analysis` is set

**3D -> 2D projection helper `_project_to_pixel(point_3d)`:**
- Uses stored RealSense depth intrinsics
- Falls back to default D435 intrinsics if unavailable
- Returns (pixel_x_rgb, pixel_y_rgb) in RGB frame coordinates

---

## Implementation Order

0. **Depth-RGB alignment** - Enable `rs.align()` and thread aligned frames through daemon/processor/GUI
   - `realsense_camera.py` → `camera_daemon_socket.py` → `daemon_image_processor.py` → `image_processor.py` → `main_window.py`
   - Test: freeze a frame, verify `frozen_aligned_color` is 848x480 and matches depth

1. **`object_analyzer.py`** - Core analysis class with all dataclasses
   - Curvature profile computation (from normals)
   - Shape estimation (curvature pre-filter + RANSAC fitting via pyransac3d)
   - Table plane extraction (reusing `remove_plane`)
   - Top plane detection (RANSAC on upper slice)
   - Main body characterization (DBSCAN + outlier removal)
   - Grasp point computation
   - `analyze_from_file()` for .npz/.ply loading

2. **`download_test_pointclouds.py`** - Download YCB objects + GraspNet scenes
   - Add `test_data/` to `.gitignore`
   - Create manifest with expected shape types

3. **`test_object_analysis.py`** - Test with downloaded + saved point clouds
   - Validate shape estimation against YCB ground truth
   - Tune curvature thresholds and RANSAC distance thresholds

4. **`main_window.py`** - GUI integration
   - Auto-trigger on selection
   - Gripper icon overlay
   - 3D->2D projection

5. **`__init__.py`** - Export new classes

---

## Verification

1. **Offline test**: Run `python scripts/test_object_analysis.py test_data/ycb/025_mug.ply` (or `--all` for full manifest)
   - Verify table plane is detected (normal ~vertical)
   - Verify shape classification is reasonable
   - Verify centroid is within object bounds
   - Visualize in Open3D to confirm

2. **Live test**: Run app with RealSense (`make run-with-daemon`)
   - Place objects: a mug (cylinder), a box, a ball (sphere)
   - "Find Objects" -> select each
   - Verify gripper icon appears at sensible location
   - Verify console prints analysis results

3. **Alignment verification**: Freeze frame, export point cloud of an object with clear edges.
   - Compare old (unaligned) vs new (aligned) -- edges should be cleaner, no table-depth bleeding into object
   - Visual check: aligned color should look slightly different from original RGB (different viewpoint)

4. **Edge cases**:
   - Object with no flat top (e.g., ball) -> `top_plane` should be `None`
   - Very small object (few points) -> graceful fallback, low `grasp_confidence` value
   - No depth data available -> skip analysis, no crash, button shows "(no depth)"
   - Webcam mode (no RealSense) -> alignment step is skipped, analysis unavailable
   - Object too large for gripper -> `graspable = False`, red icon with "Too large for gripper"
   - Object too small/flat -> `graspable = False`, red icon with "Too small to grasp"

---

## Downstream Requirements (Not In This Plan)

**Pre-grasp user confirmation (safety-critical):** Between "gripper icon displayed" and "arm moves," there MUST be an explicit user confirmation step in the eventual grasp execution flow. An ALS user accidentally triggering a grasp could be dangerous -- the arm moving unexpectedly near their body. The confirmation UX should be:
- A clearly labeled "Grasp" button that only appears after successful analysis
- Distinct from the object selection button (prevent accidental double-tap)
- Require a deliberate action (e.g., dwell time for eye tracking, or a separate switch press)
- Visual preview of the planned arm motion before execution

This plan covers analysis and visualization only. The grasp execution flow (arm motion planning, confirmation UX, safety stops) is a separate plan that builds on the `ObjectAnalysis` output.

---

## Bandwidth Optimization (Future)

The current design streams aligned color (848x480x3 = ~1.2MB) every frame through the daemon socket, even though it's only needed when analysis runs (~once per object selection). At 30fps this adds ~36MB/s of unnecessary bandwidth. This is acceptable for now (Unix sockets handle it easily), but a future optimization could:
- Send aligned frames only on demand: GUI sends a request message to daemon, daemon responds with a single aligned frame
- This requires a request/response mechanism in the daemon protocol (currently broadcast-only)
- Not worth the complexity for initial implementation, but worth noting for when we add more analysis features that increase per-frame payload
