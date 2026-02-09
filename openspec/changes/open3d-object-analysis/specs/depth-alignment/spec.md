## ADDED Requirements

### Requirement: Aligned color-depth frame production
The RealSense camera SHALL produce a pixel-aligned 848x480 color frame alongside the native 848x480 depth frame using `rs.align(rs.stream.depth)`. The 1920x1080 RGB feed SHALL continue to be produced for video display. Both frames SHALL be available on every capture cycle.

#### Scenario: Aligned frame has correct resolution
- **WHEN** the RealSense camera captures a frame
- **THEN** the aligned color frame SHALL be 848x480x3 (BGR, uint8) matching the depth frame resolution exactly

#### Scenario: Pixel correspondence between aligned color and depth
- **WHEN** an aligned color-depth pair is produced
- **THEN** pixel (x, y) in the aligned color frame SHALL correspond to the same physical point as pixel (x, y) in the depth frame, with no coordinate scaling required

#### Scenario: Original RGB feed unchanged
- **WHEN** alignment is enabled
- **THEN** the 1920x1080 RGB frame SHALL still be produced at full resolution for video display and RF-DETR detection

### Requirement: Aligned frames threaded through daemon protocol
The camera daemon socket protocol SHALL include the aligned color frame as a fourth segment, transmitted on every frame alongside RGB, depth, and metadata.

#### Scenario: Daemon protocol format
- **WHEN** the daemon broadcasts a frame
- **THEN** the message format SHALL be: `[rgb_size:u32, depth_size:u32, aligned_rgb_size:u32, metadata_size:u32]` header (16 bytes) followed by `rgb_bytes + depth_bytes + aligned_rgb_bytes + metadata_bytes`

#### Scenario: Backward-compatible header detection
- **WHEN** a daemon client receives a message
- **THEN** the client SHALL detect protocol version from header size (12 bytes = legacy 3-segment, 16 bytes = new 4-segment) and handle both gracefully

### Requirement: Aligned frames available in image processors
Both `ImageProcessor` (direct RealSense) and `DaemonImageProcessor` (daemon socket) SHALL store the latest aligned color frame and expose it for retrieval.

#### Scenario: Direct RealSense processor stores aligned color
- **WHEN** `ImageProcessor` captures a frame from RealSense
- **THEN** the aligned color frame SHALL be stored and accessible via a property

#### Scenario: Daemon processor parses aligned color
- **WHEN** `DaemonImageProcessor` receives a 4-segment daemon message
- **THEN** the aligned color frame SHALL be parsed and stored alongside the RGB and depth frames

#### Scenario: Webcam mode graceful fallback
- **WHEN** the system runs with a webcam (no RealSense)
- **THEN** the aligned color frame SHALL be `None` and no errors SHALL occur

### Requirement: Frozen aligned frame capture
When the GUI freezes the video feed for object detection, the aligned color frame at freeze time SHALL be captured and stored alongside the existing frozen RGB and depth frames.

#### Scenario: Freeze captures aligned frame
- **WHEN** the user clicks "Find Objects" to freeze the frame
- **THEN** `frozen_aligned_color` (848x480) SHALL be stored alongside `frozen_depth_frame` (848x480) for point cloud generation

#### Scenario: Point cloud uses aligned pair
- **WHEN** point cloud extraction runs on a frozen frame
- **THEN** it SHALL use `frozen_aligned_color` and `frozen_depth_frame` (same resolution, pixel-aligned) instead of scaling from 1920x1080 RGB coordinates
