"""
Temporal Tracker Module

Provides ByteTrack-based object tracking with exponential moving average
for stable, smooth object positions across frames.

Based on research from docs/segmentation-smoothing-robotics.md Section 1
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class TrackedObject:
    """Represents a tracked object with smoothed position"""
    track_id: int
    class_name: str
    box: List[int]  # [x, y, w, h]
    center: Tuple[int, int]  # (cx, cy)
    contour: np.ndarray
    confidence: float
    smoothed_depth: Optional[int] = None
    age: int = 0  # Number of frames this object has been tracked


class TemporalTracker:
    """
    Real-time temporal tracking for segmentation stability using ByteTrack

    Performance: 1-2ms overhead
    Benefits:
    - Reduces identity switches by 30-50%
    - Maintains object identity through brief occlusions
    - Exponential moving average smooths positions
    - Optimized for stationary objects
    """

    def __init__(
        self,
        track_thresh: float = 0.6,
        track_buffer: int = 60,
        match_thresh: float = 0.7,
        frame_rate: int = 30,
        smoothing_alpha: float = 0.97,
        enabled: bool = True
    ):
        """
        Initialize temporal tracker

        Args:
            track_thresh: High-confidence detection threshold (default 0.6)
                         Higher for stationary objects reduces false positives
            track_buffer: Frames to keep lost tracks (default 60 = 2 sec @ 30fps)
                         High value compensates for detector inconsistency
            match_thresh: IoU threshold for matching detections (default 0.7)
            frame_rate: Video frame rate (default 30)
            smoothing_alpha: EMA smoothing factor (default 0.97)
                            High value (0.95-0.98) for stationary scenes
                            Lower value (0.8-0.9) for moving objects
            enabled: Enable/disable tracking (default True)
        """
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.frame_rate = frame_rate
        self.smoothing_alpha = smoothing_alpha
        self.enabled = enabled

        # Initialize ByteTrack tracker
        self.tracker = None
        if enabled:
            try:
                from boxmot import ByteTrack
                self.tracker = ByteTrack(
                    track_thresh=track_thresh,
                    track_buffer=track_buffer,
                    match_thresh=match_thresh,
                    frame_rate=frame_rate
                )
            except ImportError:
                print("[TemporalTracker] Warning: boxmot not installed, tracking disabled")
                self.enabled = False

        # Smoothed positions for each track ID
        # {track_id: {'center': (cx, cy), 'box': [x, y, w, h], 'depth': d}}
        self._smoothed_positions: Dict[int, dict] = {}

    def update(
        self,
        boxes: List[List[int]],
        classes: List[str],
        contours: List[np.ndarray],
        centers: List[Tuple[int, int]],
        confidences: Optional[List[float]] = None,
        depths: Optional[List[int]] = None
    ) -> List[TrackedObject]:
        """
        Update tracker with new detections

        Args:
            boxes: List of bounding boxes [x, y, w, h]
            classes: List of class names
            contours: List of segmentation contours
            centers: List of center points (cx, cy)
            confidences: Optional list of detection confidences
            depths: Optional list of depth values (mm)

        Returns:
            List of TrackedObject with smoothed positions
        """
        if not self.enabled or self.tracker is None:
            # Pass-through without tracking
            return self._create_untracked_objects(
                boxes, classes, contours, centers, confidences, depths
            )

        if len(boxes) == 0:
            return []

        # Convert detections to format expected by ByteTrack
        # ByteTrack expects: [x1, y1, x2, y2, conf, cls]
        detections = []
        for i, (box, class_name) in enumerate(zip(boxes, classes)):
            x, y, w, h = box
            conf = confidences[i] if confidences else 0.9
            # Note: ByteTrack doesn't use class ID for tracking, but we include it
            cls = hash(class_name) % 80  # Map to 0-79 range
            detections.append([x, y, x + w, y + h, conf, cls])

        detections = np.array(detections, dtype=np.float32)

        # Dummy image (ByteTrack needs image shape but doesn't use pixels)
        # Use first box to estimate frame size, or use default
        if len(boxes) > 0:
            max_x = max(box[0] + box[2] for box in boxes)
            max_y = max(box[1] + box[3] for box in boxes)
            img_shape = (max(max_y + 100, 480), max(max_x + 100, 640), 3)
        else:
            img_shape = (480, 640, 3)

        dummy_img = np.zeros(img_shape, dtype=np.uint8)

        # Update ByteTrack
        # Returns: [x1, y1, x2, y2, track_id, conf, cls, det_idx]
        try:
            tracks = self.tracker.update(detections, dummy_img)
        except Exception as e:
            print(f"[TemporalTracker] ByteTrack update failed: {e}")
            # Fallback to untracked
            return self._create_untracked_objects(
                boxes, classes, contours, centers, confidences, depths
            )

        # Process tracked objects
        tracked_objects = []

        if len(tracks) > 0:
            for track in tracks:
                x1, y1, x2, y2, track_id, conf, cls_id, det_idx = track
                track_id = int(track_id)
                det_idx = int(det_idx)

                # Get original detection data
                if det_idx >= len(boxes):
                    continue

                box = boxes[det_idx]
                class_name = classes[det_idx]
                contour = contours[det_idx]
                center = centers[det_idx]
                depth = depths[det_idx] if depths and det_idx < len(depths) else None

                # Apply exponential moving average smoothing
                smoothed_center, smoothed_box, smoothed_depth = self._smooth_position(
                    track_id, center, box, depth
                )

                # Create tracked object
                tracked_obj = TrackedObject(
                    track_id=track_id,
                    class_name=class_name,
                    box=smoothed_box,
                    center=smoothed_center,
                    contour=contour,
                    confidence=float(conf),
                    smoothed_depth=smoothed_depth,
                    age=self._get_track_age(track_id)
                )
                tracked_objects.append(tracked_obj)

        # Clean up lost tracks
        self._cleanup_lost_tracks(tracked_objects)

        return tracked_objects

    def _smooth_position(
        self,
        track_id: int,
        center: Tuple[int, int],
        box: List[int],
        depth: Optional[int]
    ) -> Tuple[Tuple[int, int], List[int], Optional[int]]:
        """
        Apply exponential moving average to smooth positions

        Formula: smoothed = alpha * smoothed_prev + (1 - alpha) * current

        Args:
            track_id: Track ID
            center: Current center (cx, cy)
            box: Current box [x, y, w, h]
            depth: Current depth value

        Returns:
            (smoothed_center, smoothed_box, smoothed_depth)
        """
        if track_id not in self._smoothed_positions:
            # First observation - initialize
            self._smoothed_positions[track_id] = {
                'center': center,
                'box': box.copy(),
                'depth': depth,
                'age': 1
            }
            return center, box, depth

        # Get previous smoothed values
        prev = self._smoothed_positions[track_id]
        alpha = self.smoothing_alpha

        # Smooth center
        smoothed_cx = int(alpha * prev['center'][0] + (1 - alpha) * center[0])
        smoothed_cy = int(alpha * prev['center'][1] + (1 - alpha) * center[1])
        smoothed_center = (smoothed_cx, smoothed_cy)

        # Smooth box
        smoothed_box = [
            int(alpha * prev['box'][0] + (1 - alpha) * box[0]),  # x
            int(alpha * prev['box'][1] + (1 - alpha) * box[1]),  # y
            int(alpha * prev['box'][2] + (1 - alpha) * box[2]),  # w
            int(alpha * prev['box'][3] + (1 - alpha) * box[3])   # h
        ]

        # Smooth depth if available
        smoothed_depth = None
        if depth is not None and prev['depth'] is not None:
            smoothed_depth = int(alpha * prev['depth'] + (1 - alpha) * depth)
        elif depth is not None:
            smoothed_depth = depth

        # Update stored values
        self._smoothed_positions[track_id] = {
            'center': smoothed_center,
            'box': smoothed_box,
            'depth': smoothed_depth,
            'age': prev['age'] + 1
        }

        return smoothed_center, smoothed_box, smoothed_depth

    def _get_track_age(self, track_id: int) -> int:
        """Get number of frames this track has been alive"""
        if track_id in self._smoothed_positions:
            return self._smoothed_positions[track_id]['age']
        return 1

    def _cleanup_lost_tracks(self, active_tracks: List[TrackedObject]):
        """Remove smoothed positions for tracks that no longer exist"""
        active_ids = {obj.track_id for obj in active_tracks}
        lost_ids = set(self._smoothed_positions.keys()) - active_ids
        for track_id in lost_ids:
            del self._smoothed_positions[track_id]

    def _create_untracked_objects(
        self,
        boxes: List[List[int]],
        classes: List[str],
        contours: List[np.ndarray],
        centers: List[Tuple[int, int]],
        confidences: Optional[List[float]],
        depths: Optional[List[int]]
    ) -> List[TrackedObject]:
        """Create TrackedObject list without tracking (passthrough mode)"""
        objects = []
        for i, (box, class_name, contour, center) in enumerate(
            zip(boxes, classes, contours, centers)
        ):
            conf = confidences[i] if confidences and i < len(confidences) else 0.9
            depth = depths[i] if depths and i < len(depths) else None

            obj = TrackedObject(
                track_id=-1,  # No tracking ID
                class_name=class_name,
                box=box,
                center=center,
                contour=contour,
                confidence=conf,
                smoothed_depth=depth,
                age=1
            )
            objects.append(obj)

        return objects

    def reset(self):
        """Reset tracker state"""
        if self.tracker is not None:
            try:
                self.tracker.reset()
            except:
                pass
        self._smoothed_positions.clear()

    def set_enabled(self, enabled: bool):
        """Enable or disable tracking"""
        self.enabled = enabled
        if not enabled:
            self.reset()

    def get_config(self) -> dict:
        """Get current configuration"""
        return {
            'enabled': self.enabled,
            'track_thresh': self.track_thresh,
            'track_buffer': self.track_buffer,
            'match_thresh': self.match_thresh,
            'frame_rate': self.frame_rate,
            'smoothing_alpha': self.smoothing_alpha,
            'active_tracks': len(self._smoothed_positions)
        }
