## ADDED Requirements

### Requirement: Table plane extraction
The ObjectAnalyzer SHALL extract the dominant table plane from a scene point cloud using RANSAC plane segmentation, returning the plane equation, normal vector, centroid, inlier points, and estimated area.

#### Scenario: Flat table detected
- **WHEN** a scene point cloud containing a table surface is analyzed
- **THEN** the table plane SHALL be detected with a near-vertical normal (dot product with gravity axis > 0.8) and inlier points representing the table surface

#### Scenario: No table plane found
- **WHEN** no dominant horizontal plane exists in the scene
- **THEN** table_plane SHALL be `None` and analysis SHALL continue without it

### Requirement: Top plane detection
The ObjectAnalyzer SHALL detect a flat top surface on an object by RANSAC-fitting a plane to the upper ~20% of object points (sorted by vertical axis).

#### Scenario: Flat-topped object
- **WHEN** an object with a flat top (e.g., a box, mug) is analyzed
- **THEN** top_plane SHALL be detected with a roughly horizontal normal and inlier ratio > 30%

#### Scenario: Rounded object without flat top
- **WHEN** an object without a flat top (e.g., a ball) is analyzed
- **THEN** top_plane SHALL be `None`

### Requirement: Curvature profile computation
The ObjectAnalyzer SHALL compute per-point curvature using normal covariance in a k=30 neighborhood, with median filtering to suppress D435 depth noise, classifying each point as flat (curvature < 0.01) or curved (curvature >= 0.01).

#### Scenario: Curvature computed for object
- **WHEN** curvature analysis runs on a preprocessed point cloud with normals
- **THEN** the result SHALL include `flat_ratio`, `curved_ratio`, and `mean_curvature` values

#### Scenario: Noise robustness
- **WHEN** point cloud data has D435-typical depth noise (~2-4mm)
- **THEN** median-filtered curvature SHALL produce stable flat/curved classification (flat surfaces SHALL NOT be misclassified as curved due to noise)

### Requirement: Shape estimation via curvature pre-filter and RANSAC
The ObjectAnalyzer SHALL classify objects into one of four shape types: "cylinder", "box", "sphere", or "irregular". Curvature profile SHALL determine which RANSAC primitive fits to attempt. The result SHALL include shape type, confidence (inlier ratio), dimensions, oriented bounding box, curvature profile, and fit residual.

#### Scenario: Predominantly flat object classified as box
- **WHEN** an object has `flat_ratio > 0.6`
- **THEN** box fitting (OBB + RANSAC flat-face confirmation) SHALL be attempted first

#### Scenario: Predominantly curved object classified as sphere
- **WHEN** an object has `curved_ratio > 0.6`
- **THEN** sphere fitting (`pyransac3d.Sphere().fit()`) SHALL be attempted first

#### Scenario: Mixed flat and curved classified as cylinder
- **WHEN** an object has mixed flat and curved regions
- **THEN** cylinder fitting (2D circle projection via least-squares) SHALL be attempted

#### Scenario: Poor fit classified as irregular
- **WHEN** the best RANSAC fit has inlier ratio < 0.4
- **THEN** shape_type SHALL be "irregular"

#### Scenario: Box detection with limited viewpoint
- **WHEN** only 1-2 faces of a box-shaped object are visible
- **THEN** OBB-based box detection with flat-face confirmation SHALL still produce a valid box classification (confidence scales with number of confirmed faces)

### Requirement: Main body characterization
The ObjectAnalyzer SHALL extract the main body of an object by removing outliers and selecting the largest DBSCAN cluster, returning the cleaned point cloud and a characteristic radius from centroid.

#### Scenario: Object with noise points
- **WHEN** an object point cloud contains outlier points (e.g., table edge bleed)
- **THEN** outlier removal and DBSCAN clustering SHALL isolate the main body cluster

### Requirement: Analyze from file
The ObjectAnalyzer SHALL support loading and analyzing point clouds from .npz and .ply files for offline testing.

#### Scenario: Load NPZ file
- **WHEN** `analyze_from_file()` is called with a .npz file path
- **THEN** the point cloud SHALL be loaded and full analysis SHALL run, returning an ObjectAnalysis result

#### Scenario: Load PLY file
- **WHEN** `analyze_from_file()` is called with a .ply file path
- **THEN** the point cloud SHALL be loaded and full analysis SHALL run, returning an ObjectAnalysis result

### Requirement: Full analysis pipeline
The `analyze()` method SHALL orchestrate all analysis steps (table plane extraction, main body characterization, curvature computation, shape estimation, top plane detection, grasp computation) and return a complete ObjectAnalysis dataclass.

#### Scenario: Complete analysis result
- **WHEN** `analyze(object_pcd, scene_pcd)` is called with valid point clouds
- **THEN** the result SHALL contain centroid, shape estimate, table_plane, top_plane, main_body_points, main_body_radius, grasp_point, grasp_approach, grasp_width, graspable, grasp_confidence, and num_points

#### Scenario: Too few points for analysis
- **WHEN** the object point cloud has too few points after preprocessing
- **THEN** analysis SHALL still complete with `grasp_confidence = "low"` and dimensions estimated from OBB as fallback
