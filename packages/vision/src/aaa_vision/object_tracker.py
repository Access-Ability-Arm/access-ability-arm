"""
Object Tracker with Kalman Filtering and Multi-Frame Consensus

Reduces jitter and flickering in object detection by:
1. Kalman filtering for smooth position prediction
2. Multi-frame consensus (objects must appear N times before showing)
3. Disappearance grace period (keep showing for N frames after lost)
"""

import cv2
import numpy as np


class TrackedObject:
    """Represents a tracked object with Kalman filter and frame counting"""

    def __init__(self, box, class_name, center, depth=None):
        """
        Initialize tracked object

        Args:
            box: Bounding box [x, y, w, h]
            class_name: Object class label
            center: Center point (cx, cy)
            depth: Depth value in mm (optional)
        """
        self.class_name = class_name
        self.box = box
        self.center = center
        self.depth = depth

        # Depth smoothing with exponential moving average
        self.smoothed_depth = depth
        self.depth_alpha = 0.05  # Lower = more smoothing (0.0-1.0, default: 0.05 for ultra-smooth)

        # Frame counting for consensus
        self.frames_seen = 1  # Number of consecutive frames detected
        self.frames_missing = 0  # Number of consecutive frames not detected

        # Kalman filter for position tracking (optimized for stationary objects)
        self.kalman = cv2.KalmanFilter(4, 2)  # 4 state vars (x, y, vx, vy), 2 measurements (x, y)

        # Measurement matrix: we measure x and y directly
        self.kalman.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], np.float32)

        # Transition matrix: position + velocity model
        self.kalman.transitionMatrix = np.array([
            [1, 0, 1, 0],  # x = x + vx
            [0, 1, 0, 1],  # y = y + vy
            [0, 0, 1, 0],  # vx = vx (no external acceleration)
            [0, 0, 0, 1]   # vy = vy
        ], np.float32)

        # Process noise covariance - OPTIMIZED FOR STATIONARY OBJECTS
        # Objects barely move, so very low process noise
        # Higher noise on velocity to make it decay quickly to zero
        self.kalman.processNoiseCov = np.array([
            [0.001, 0,     0,    0   ],  # x: very small (objects don't move much)
            [0,     0.001, 0,    0   ],  # y: very small
            [0,     0,     0.01, 0   ],  # vx: higher (velocity decays to zero)
            [0,     0,     0,    0.01]   # vy: higher (velocity decays to zero)
        ], np.float32)

        # Measurement noise covariance - TRUST DETECTOR (we have TTA now)
        # Lower values = trust measurements more
        self.kalman.measurementNoiseCov = np.array([
            [0.5, 0  ],  # x measurement noise (detector + TTA is reliable)
            [0,   0.5]   # y measurement noise
        ], np.float32)

        # Initialize state with current position and zero velocity
        self.kalman.statePre = np.array([
            [center[0]],
            [center[1]],
            [0],  # vx = 0 (stationary)
            [0]   # vy = 0 (stationary)
        ], np.float32)

        self.kalman.statePost = self.kalman.statePre.copy()

    def predict(self):
        """Predict next position using Kalman filter"""
        prediction = self.kalman.predict()
        predicted_x = int(prediction[0])
        predicted_y = int(prediction[1])
        return (predicted_x, predicted_y)

    def update(self, box, center, depth=None):
        """
        Update tracked object with new detection

        Args:
            box: New bounding box
            center: New center point
            depth: New depth value
        """
        # Update Kalman filter
        measurement = np.array([[np.float32(center[0])], [np.float32(center[1])]])
        self.kalman.correct(measurement)

        # Update properties
        self.box = box
        self.center = center

        # Smooth depth with exponential moving average
        if depth is not None and depth > 0:
            self.depth = depth
            if self.smoothed_depth is None:
                self.smoothed_depth = depth
            else:
                # EMA: new_value = alpha * measurement + (1 - alpha) * old_value
                # Lower alpha = more smoothing
                self.smoothed_depth = self.depth_alpha * depth + (1 - self.depth_alpha) * self.smoothed_depth

        # Update frame counts
        self.frames_seen += 1
        self.frames_missing = 0

    def mark_missing(self):
        """Mark this object as not detected in current frame"""
        self.frames_missing += 1
        self.frames_seen = 0

    def is_confirmed(self, min_frames):
        """Check if object has appeared enough times to show"""
        return self.frames_seen >= min_frames

    def should_keep(self, max_missing_frames):
        """Check if object should still be kept despite being missing"""
        return self.frames_missing <= max_missing_frames


class ObjectTracker:
    """
    Manages multiple tracked objects with Kalman filtering and consensus
    """

    def __init__(
        self,
        iou_threshold=0.35,
        min_frames_to_show=2,
        max_frames_missing=3,
        smoothing_alpha=0.9
    ):
        """
        Initialize object tracker

        Args:
            iou_threshold: Minimum IoU for matching objects across frames
            min_frames_to_show: Object must appear N consecutive frames before showing
            max_frames_missing: Keep object N frames after last detection
            smoothing_alpha: EMA smoothing factor for box coordinates
        """
        self.iou_threshold = iou_threshold
        self.min_frames_to_show = min_frames_to_show
        self.max_frames_missing = max_frames_missing
        self.smoothing_alpha = smoothing_alpha

        self.tracked_objects = []

    def update(self, boxes, classes, centers, depths=None):
        """
        Update tracker with new detections

        Args:
            boxes: List of bounding boxes [x, y, w, h]
            classes: List of class labels
            centers: List of center points (cx, cy)
            depths: Optional list of depth values

        Returns:
            Tuple of (filtered_boxes, filtered_classes, filtered_centers, filtered_depths)
            Only returns objects that pass consensus and are still visible
        """
        # Match new detections to existing tracked objects
        matched_detections = set()
        matched_objects = set()

        for obj_idx, tracked_obj in enumerate(self.tracked_objects):
            best_iou = 0
            best_det_idx = None

            # Predict where object should be
            predicted_center = tracked_obj.predict()

            # Find best matching detection
            for det_idx, (box, class_name, center) in enumerate(zip(boxes, classes, centers)):
                if det_idx in matched_detections:
                    continue

                # Only match same class
                if class_name != tracked_obj.class_name:
                    continue

                # Calculate IoU
                iou = self._calculate_iou(tracked_obj.box, box)

                if iou > best_iou and iou > self.iou_threshold:
                    best_iou = iou
                    best_det_idx = det_idx

            # Update tracked object if match found
            if best_det_idx is not None:
                depth = depths[best_det_idx] if depths is not None else None
                tracked_obj.update(boxes[best_det_idx], centers[best_det_idx], depth)
                matched_detections.add(best_det_idx)
                matched_objects.add(obj_idx)
            else:
                # No match - mark as missing
                tracked_obj.mark_missing()

        # Add new detections as new tracked objects
        for det_idx, (box, class_name, center) in enumerate(zip(boxes, classes, centers)):
            if det_idx not in matched_detections:
                depth = depths[det_idx] if depths is not None else None
                new_obj = TrackedObject(box, class_name, center, depth)
                self.tracked_objects.append(new_obj)

        # Remove objects that have been missing too long
        self.tracked_objects = [
            obj for obj in self.tracked_objects
            if obj.should_keep(self.max_frames_missing)
        ]

        # Build output list (only confirmed objects)
        confirmed_objects = [
            obj for obj in self.tracked_objects
            if obj.is_confirmed(self.min_frames_to_show)
        ]

        return confirmed_objects

    def _calculate_iou(self, box1, box2):
        """
        Calculate Intersection over Union between two boxes

        Args:
            box1, box2: Bounding boxes as [x, y, w, h]

        Returns:
            IoU score (0.0 to 1.0)
        """
        # Convert to [x1, y1, x2, y2]
        box1_x2 = box1[0] + box1[2]
        box1_y2 = box1[1] + box1[3]
        box2_x2 = box2[0] + box2[2]
        box2_y2 = box2[1] + box2[3]

        # Intersection rectangle
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1_x2, box2_x2)
        y2 = min(box1_y2, box2_y2)

        # No intersection
        if x2 < x1 or y2 < y1:
            return 0.0

        # Intersection area
        intersection = (x2 - x1) * (y2 - y1)

        # Union area
        box1_area = box1[2] * box1[3]
        box2_area = box2[2] * box2[3]
        union = box1_area + box2_area - intersection

        return intersection / union if union > 0 else 0.0
