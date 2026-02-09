## ADDED Requirements

### Requirement: Shape-aware grasp point computation
The system SHALL compute a grasp point, approach direction, and required gripper width based on the object's estimated shape, using per-shape heuristics.

#### Scenario: Cylinder grasp
- **WHEN** an object is classified as "cylinder"
- **THEN** the grasp point SHALL be the centroid of the main body (clamped to >= 15mm above table), the approach direction SHALL be perpendicular to the cylinder axis from the camera-facing side, and the grasp width SHALL be `2 * cylinder_radius`

#### Scenario: Box grasp
- **WHEN** an object is classified as "box"
- **THEN** the grasp point SHALL be the center of the largest visible face (shifted up if < 15mm from table), the approach direction SHALL be along the face normal toward the camera side, and the grasp width SHALL be the shorter extent of that face

#### Scenario: Sphere grasp
- **WHEN** an object is classified as "sphere"
- **THEN** the grasp point SHALL be the centroid, the approach direction SHALL be top-down (-Y in camera frame) if clearance allows or from the side with most table clearance otherwise, and the grasp width SHALL be `2 * sphere_radius`

#### Scenario: Irregular shape grasp
- **WHEN** an object is classified as "irregular"
- **THEN** the grasp point SHALL be the centroid of the main body cluster (clamped to >= 15mm above table), the approach direction SHALL be top-down (-Y in camera frame), and the grasp width SHALL be the narrowest OBB extent

### Requirement: Table clearance enforcement
All grasp points SHALL maintain a minimum clearance of 15mm above the detected table plane to avoid gripper-table collision.

#### Scenario: Grasp point near table surface
- **WHEN** the computed grasp point is less than 15mm above the table plane
- **THEN** the grasp point SHALL be shifted upward to maintain at least 15mm clearance

### Requirement: Graspability checking against Lite6 constraints
The system SHALL determine whether an object is graspable based on the Lite6 gripper's physical constraints: max opening ~66mm, min graspable width ~5mm, and minimum object height 5mm.

#### Scenario: Object too wide for gripper
- **WHEN** the required grasp width exceeds 66mm (GRIPPER_MAX_OPENING_M)
- **THEN** `graspable` SHALL be `False`

#### Scenario: Object too small to hold
- **WHEN** the required grasp width is less than 5mm (GRIPPER_MIN_WIDTH_M)
- **THEN** `graspable` SHALL be `False`

#### Scenario: Object too flat to pick up
- **WHEN** the object height is less than 5mm
- **THEN** `graspable` SHALL be `False`

#### Scenario: Object within gripper range
- **WHEN** the grasp width is between 5mm and 66mm and the object height is >= 5mm
- **THEN** `graspable` SHALL be `True`

### Requirement: Grasp confidence assessment
The system SHALL assign a grasp confidence level ("high", "medium", "low") based on shape estimation quality and point cloud coverage.

#### Scenario: High confidence grasp
- **WHEN** shape confidence > 0.7 AND estimated surface visibility > 60%
- **THEN** grasp_confidence SHALL be "high"

#### Scenario: Medium confidence grasp
- **WHEN** shape confidence is 0.4-0.7 OR estimated surface visibility is 30-60%
- **THEN** grasp_confidence SHALL be "medium"

#### Scenario: Low confidence grasp
- **WHEN** shape is "irregular" OR point count < 200 OR estimated visibility < 30%
- **THEN** grasp_confidence SHALL be "low"

### Requirement: Camera-visible approach direction only
The grasp approach vector SHALL always come from the camera-visible side of the object. The system SHALL NOT suggest approaching from the unseen back side.

#### Scenario: Approach from visible side
- **WHEN** a grasp approach direction is computed
- **THEN** the approach vector SHALL point from the camera-facing side of the object, never from behind or from an occluded direction
