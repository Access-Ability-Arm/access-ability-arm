## Context

The Access Ability Arm has a working detection-to-selection pipeline: RF-DETR segments objects, the user selects one via GUI buttons, and depth points can be exported. However, there is no analysis of the selected object's 3D geometry -- the system doesn't know the object's shape, where to grasp it, or whether the Lite6 gripper can physically hold it.

The existing `PointCloudProcessor` class (`point_cloud.py`) already provides RANSAC plane removal, DBSCAN clustering, outlier removal, and depth-to-point-cloud conversion. The new `ObjectAnalyzer` builds on these primitives to add shape estimation and grasp planning.

A prerequisite issue: depth-RGB alignment is currently disabled in `realsense_camera.py` (line ~116, `self.align = None`). The D435's RGB and depth sensors are ~50mm apart, so without alignment, RF-DETR mask coordinates map to wrong depth pixels at object edges, corrupting point clouds with table-depth bleed.

## Goals / Non-Goals

**Goals:**

- Fix depth-RGB alignment so point clouds accurately represent segmented objects
- Classify selected objects as cylinder, box, sphere, or irregular using curvature analysis + RANSAC primitive fitting
- Compute grasp points with approach direction and gripper width, respecting Lite6 physical constraints
- Show a color-coded gripper overlay on the frozen frame with user-friendly status text
- Provide immediate "Analyzing..." feedback when an object is selected (critical for ALS users with limited input)
- Support offline testing via saved point cloud files

**Non-Goals:**

- Arm motion planning or grasp execution (separate downstream plan)
- Multi-viewpoint scanning or look-around strategies
- Real-time continuous analysis (only runs once per object selection on frozen frame)
- User confirmation UX for grasping (downstream safety-critical work)
- Daemon protocol optimization (streaming aligned frames every frame is acceptable for now)

## Decisions

### 1. Align color TO depth (not depth TO color)

**Decision:** Use `rs.align(rs.stream.depth)` to produce an 848x480 aligned color frame that shares the depth grid.

**Alternatives considered:**
- *Align depth TO color (`rs.align(rs.stream.color)`)*: Upscales depth to 1920x1080, wasting memory (~3.9MB vs ~1.2MB per frame) and introducing interpolation artifacts in depth values. Rejected.
- *Keep unaligned, scale coordinates*: Current approach. Works for rough bounding boxes but fails at object edges where depth bleeds from table to object. Rejected for analysis use cases.

**Rationale:** Aligning color to depth keeps depth values at native resolution (no interpolation artifacts) and produces a compact 848x480 pair where every pixel has pixel-perfect color+depth correspondence. The 1920x1080 RGB is still streamed separately for video display.

### 2. Stream aligned color through daemon on every frame

**Decision:** Add aligned color (848x480x3 BGR) as a fourth segment in the daemon socket protocol. Send every frame.

**Alternatives considered:**
- *On-demand request/response*: GUI sends a request, daemon responds with one aligned frame. Lower bandwidth but requires a bidirectional protocol (currently broadcast-only). Too much complexity for initial implementation.
- *Compute alignment on the GUI side*: Would require sending raw RealSense framesets, which isn't possible through the daemon's numpy-based protocol.

**Rationale:** ~1.2MB extra per frame at 30fps = ~36MB/s over Unix socket. This is well within Unix socket throughput. Simplicity wins over optimization at this stage. The on-demand approach is noted as a future optimization.

**Protocol change:**
```
Before: [rgb_size:u32, depth_size:u32, metadata_size:u32] + rgb + depth + metadata
After:  [rgb_size:u32, depth_size:u32, aligned_rgb_size:u32, metadata_size:u32] + rgb + depth + aligned_rgb + metadata
```

### 3. Curvature pre-filter + RANSAC hybrid for shape estimation

**Decision:** Compute per-point curvature first to narrow down candidate shapes, then run RANSAC primitive fitting only on plausible candidates.

**Alternatives considered:**
- *RANSAC-only (try all primitives)*: Wastes time fitting sphere to a box. Also, pyransac3d's `Cuboid().fit()` is unreliable with single-viewpoint data (needs 3+ visible faces).
- *Deep learning shape classification*: Requires training data, adds model dependency, overkill for 4 categories.
- *Curvature-only (no RANSAC)*: Can distinguish flat vs curved but can't measure specific dimensions or fit parameters needed for grasp width.

**Rationale:** Curvature analysis (k=30 neighborhood, median-filtered) classifies points as flat or curved in ~100-300ms. This narrows RANSAC to 1-2 candidate shapes instead of 3, and provides the `flat_ratio`/`curved_ratio` that drives candidate selection. The hybrid approach is both faster and more accurate than either method alone.

### 4. OBB-based box detection instead of pyransac3d Cuboid

**Decision:** Detect boxes using Oriented Bounding Box + RANSAC flat-face confirmation, not `pyransac3d.Cuboid().fit()`.

**Alternatives considered:**
- *pyransac3d Cuboid fitting*: Requires 3+ visible faces to reliably fit. With a single camera viewpoint, we typically see 1-2 faces. Rejected as unreliable.

**Rationale:** Compute OBB axes, then for each axis project nearby points onto the face and RANSAC-fit a plane. Accept if inlier ratio > 50% and normal aligns with OBB axis. Works with 1-2 visible faces. Box confidence scales with number of confirmed faces.

### 5. Custom cylinder fitting (not pyransac3d)

**Decision:** Fit cylinders by projecting points perpendicular to OBB longest axis, then fitting a circle to the 2D projection with `scipy.optimize.least_squares`.

**Alternatives considered:**
- *pyransac3d Cylinder fitting*: Known accuracy issues on real sensor data with noise.

**Rationale:** The OBB longest axis is a reliable cylinder axis estimate. Circle fitting in 2D is well-conditioned and fast. Inliers = points within threshold of the fitted cylinder surface.

### 6. Analysis runs in background thread, triggered on object selection

**Decision:** When the user selects an object button, immediately show "Analyzing..." (amber) on the button and spawn a background thread for analysis. On completion, update button to show result and draw gripper overlay.

**Alternatives considered:**
- *Synchronous analysis on main thread*: Blocks UI for 200-500ms. Unacceptable for ALS users who need immediate feedback.
- *Pre-analyze all objects at freeze time*: Wastes compute on unselected objects. Most users select 1 of N detected objects.

**Rationale:** Background thread with immediate visual feedback is the standard pattern for responsive UI with compute-heavy operations. The "Analyzing..." state appears within one frame update (~33ms).

### 7. Grasp approach from camera-visible side only

**Decision:** The grasp approach vector always comes from the camera-facing direction. Never suggest grasping from the back side of the object.

**Rationale:** Single-viewpoint limitation -- we have no geometry data for the back of the object. Approaching from an unseen direction risks collision with unknown obstacles (e.g., a mug handle). The `grasp_confidence` field reflects this uncertainty.

### 8. Build on existing PointCloudProcessor methods

**Decision:** `ObjectAnalyzer` delegates to `PointCloudProcessor` for point cloud creation, preprocessing, plane removal, and clustering rather than reimplementing.

**Rationale:** These methods are already tested and handle D435 noise characteristics. `remove_plane()` provides RANSAC plane segmentation, `preprocess()` handles outlier removal + normal estimation, `extract_object()` creates masked point clouds, and `cluster_objects()` provides DBSCAN. No reason to duplicate.

## Risks / Trade-offs

**Single-viewpoint shape ambiguity** → `grasp_confidence` field communicates uncertainty. A mug from the front looks like a cylinder; from the handle side, it's irregular. The system is transparent about this limitation rather than presenting uncertain results as definitive. Mitigation: always approach from the visible side.

**D435 depth noise at edges** → Even with alignment, D435 depth has ~2-4mm noise at tabletop range (0.3-0.8m) and flying pixels at depth discontinuities. Mitigation: `preprocess()` statistical outlier removal + DBSCAN largest-cluster selection in `_characterize_main_body()`.

**Breaking daemon protocol change** → Existing daemon clients will fail to parse the new 4-segment format. Mitigation: daemon and client are always deployed together (monorepo), so version skew is unlikely. But the daemon client should detect format version from header size (12 bytes = old, 16 bytes = new) for graceful degradation.

**Shape estimation accuracy on small objects** → Objects with <200 points after downsampling may not have enough geometry for reliable shape fitting. Mitigation: `grasp_confidence = "low"` when point count is insufficient, and `graspable` still computed from OBB dimensions as fallback.

**pyransac3d dependency** → Adds a new dependency. It's a small pure-Python package with no heavy transitive dependencies. Risk is low. Used only for sphere fitting; box and cylinder use custom approaches.

**Thread safety for analysis results** → Analysis runs in a background thread and writes `self.object_analysis` which the GUI thread reads for overlay drawing. Mitigation: use a simple flag (`self.analysis_complete`) set after result is fully written; GUI checks flag before reading. Python's GIL makes single-attribute writes atomic.
