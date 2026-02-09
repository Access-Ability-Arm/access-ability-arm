## ADDED Requirements

### Requirement: Auto-trigger analysis on object selection
When the user selects an object button on the frozen frame, the system SHALL automatically trigger 3D object analysis in a background thread without requiring any additional user action.

#### Scenario: Object selected triggers analysis
- **WHEN** the user clicks an object selection button
- **THEN** object analysis SHALL begin automatically in a background thread

#### Scenario: Re-selecting same object toggles off
- **WHEN** the user clicks the already-selected object button
- **THEN** the selection SHALL be cleared and any in-progress analysis SHALL be discarded

### Requirement: Immediate analyzing feedback
The selected object button SHALL show an "Analyzing..." state with a distinct color (amber/orange) within one frame update (~33ms) of the button press, before analysis completes.

#### Scenario: Button shows analyzing state
- **WHEN** the user selects an object and analysis begins
- **THEN** the button SHALL immediately display "Analyzing..." with an amber/orange background color

#### Scenario: Analysis completes successfully
- **WHEN** background analysis finishes successfully
- **THEN** the button text SHALL update to show the object name with a checkmark (e.g., "cup ✓")

#### Scenario: Analysis fails
- **WHEN** background analysis fails (exception, too few points, no depth data)
- **THEN** the button text SHALL update to show the failure reason (e.g., "cup (no depth)" or "cup (analysis failed)") and the UI SHALL NOT crash or enter an indeterminate state

### Requirement: Gripper icon overlay on frozen frame
When analysis completes, the system SHALL draw a gripper outline on the frozen frame at the projected grasp point location, color-coded by graspability and confidence.

#### Scenario: Graspable with high confidence
- **WHEN** analysis result has `graspable = True` and `grasp_confidence = "high"`
- **THEN** the gripper icon SHALL be bright green with the label "Ready to grasp"

#### Scenario: Graspable with medium confidence
- **WHEN** analysis result has `graspable = True` and `grasp_confidence = "medium"`
- **THEN** the gripper icon SHALL be yellow with the label "Grasp possible"

#### Scenario: Graspable with low confidence
- **WHEN** analysis result has `graspable = True` and `grasp_confidence = "low"`
- **THEN** the gripper icon SHALL be orange with the label "Uncertain grasp"

#### Scenario: Not graspable - too large
- **WHEN** analysis result has `graspable = False` due to object exceeding gripper max opening
- **THEN** the gripper icon SHALL be red with an "X" overlay and the label "Too large for gripper"

#### Scenario: Not graspable - too small
- **WHEN** analysis result has `graspable = False` due to object being below minimum graspable width
- **THEN** the gripper icon SHALL be red with an "X" overlay and the label "Too small to grasp"

### Requirement: High-contrast gripper rendering
The gripper icon SHALL use high-contrast rendering for visibility against any background: white outer border (3px) with colored inner fill (2px). Text labels SHALL be minimum 24px at 1080p resolution.

#### Scenario: Gripper visible on dark background
- **WHEN** the gripper icon is drawn over a dark region of the frame
- **THEN** the white outer border SHALL make the icon clearly visible

#### Scenario: Gripper visible on bright background
- **WHEN** the gripper icon is drawn over a bright region of the frame
- **THEN** the colored inner fill and white border SHALL make the icon clearly visible

### Requirement: 3D to 2D grasp point projection
The system SHALL project the 3D grasp point from camera coordinates to 2D pixel coordinates using RealSense depth intrinsics, then scale from depth resolution (848x480) to display resolution (1920x1080) for overlay rendering.

#### Scenario: Successful projection
- **WHEN** a 3D grasp point in camera coordinates is projected
- **THEN** the resulting 2D pixel coordinates SHALL correctly map to the corresponding location on the 1920x1080 display frame

#### Scenario: Intrinsics unavailable
- **WHEN** RealSense depth intrinsics are not available
- **THEN** the system SHALL fall back to default D435 intrinsics for projection

### Requirement: No technical details in user-facing display
The gripper overlay SHALL NOT display raw technical values (shape type, confidence scores, inlier ratios) to the end user. Technical analysis details SHALL be logged to console for debugging only.

#### Scenario: User sees friendly labels only
- **WHEN** the gripper overlay is displayed
- **THEN** only user-friendly labels (e.g., "Ready to grasp", "Too large for gripper") SHALL be shown, not values like "cylinder 0.85" or "confidence: 0.72"

#### Scenario: Technical details logged
- **WHEN** analysis completes
- **THEN** shape type, confidence score, dimensions, and fit details SHALL be logged to the console at debug level
