"""
Detection Manager
Manages switching between different detection modes (face tracking vs object detection)
"""

import os
import sys
from contextlib import contextmanager
from typing import Optional

import numpy as np
from aaa_core.config.console import status
from aaa_core.config.settings import app_config

from aaa_vision.face_detector import FaceDetector


@contextmanager
def suppress_output():
    """Suppress all output including system-level warnings"""
    # Save original file descriptors
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save copies of the original file descriptors
    with os.fdopen(os.dup(stdout_fd), 'w') as stdout_copy, \
         os.fdopen(os.dup(stderr_fd), 'w') as stderr_copy:

        # Redirect stdout and stderr to devnull
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stdout_fd)
            os.dup2(devnull, stderr_fd)
            yield
        finally:
            # Restore original file descriptors
            os.dup2(stdout_copy.fileno(), stdout_fd)
            os.dup2(stderr_copy.fileno(), stderr_fd)
            os.close(devnull)


class DetectionManager:
    """Manages detection mode and delegates to appropriate detector"""

    def __init__(self):
        """Initialize detection manager with available detectors"""
        status("Detection manager initialized")

        # Always initialize face detector (MediaPipe is always available)
        # Suppress TensorFlow Lite feedback manager warnings
        # Warnings appear during the first .process() call
        with suppress_output():
            self.face_detector = FaceDetector()
            # Make a dummy process call to trigger TFLite warnings
            # This ensures warnings are suppressed
            import numpy as np
            dummy_image = np.zeros((10, 10, 3), dtype=np.uint8)
            self.face_detector.mesh.process(dummy_image)

        # Initialize segmentation model if available
        self.segmentation_model = None
        if app_config.segmentation_available:
            self.segmentation_model = self._initialize_segmentation_model()

        # Set default detection mode
        # Modes: "face", "objects", "combined" (face + objects), "camera" (raw video)
        self.detection_mode = "objects" if self.segmentation_model else "face"
        status(f"Detection mode: {self.detection_mode}")

        # Temporal smoothing for object detection
        self.smoothing_enabled = True
        self.smoothing_alpha = 0.85  # Higher = more smoothing (0.0-1.0)
        self.prev_boxes = None
        self.prev_classes = None
        self.prev_centers = None
        self.prev_depths = None  # Track depth values for smoothing

    def _initialize_segmentation_model(self):
        """Initialize the appropriate segmentation model"""
        try:
            if app_config.segmentation_model == "rfdetr":
                from aaa_vision.rfdetr_seg import RFDETRSeg

                model = RFDETRSeg()
                print(f"✓ {app_config.segmentation_model.upper()} initialized")
                return model
            elif app_config.segmentation_model == "yolov11":
                from aaa_vision.yolov11_seg import YOLOv11Seg

                model = YOLOv11Seg(model_size=app_config.yolo_model_size)
                print(f"✓ YOLOv11-{app_config.yolo_model_size} initialized")
                return model
            elif app_config.segmentation_model == "maskrcnn":
                from aaa_vision.mask_rcnn import MaskRCNN

                model = MaskRCNN()
                print(f"✓ {app_config.segmentation_model} initialized")
                return model
        except Exception as e:
            print(f"✗ Segmentation model initialization failed: {e}")
            return None

    def process_frame(
        self, image: np.ndarray, depth_frame: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Process a frame using the current detection mode

        Args:
            image: RGB image array
            depth_frame: Optional depth frame for distance measurements

        Returns:
            Processed image with detections drawn
        """
        if self.detection_mode == "camera":
            # Camera only mode - return raw image
            return image
        elif self.detection_mode == "objects" and self.segmentation_model:
            return self._process_object_detection(image, depth_frame)
        elif self.detection_mode == "combined" and self.segmentation_model:
            return self._process_combined_detection(image, depth_frame)
        else:
            return self._process_face_detection(image)

    def _process_object_detection(
        self, image: np.ndarray, depth_frame: Optional[np.ndarray]
    ) -> np.ndarray:
        """Process frame with object detection"""
        # Get object masks
        (boxes, classes,
         contours, centers) = self.segmentation_model.detect_objects_mask(
            image
        )

        # Extract depth values at object centers (before smoothing)
        depths = None
        if depth_frame is not None and len(centers) > 0:
            depths = self._extract_depths(centers, depth_frame)

        # Apply temporal smoothing to stabilize detections
        if self.smoothing_enabled and len(boxes) > 0:
            boxes, centers, depths = self._smooth_detections(
                boxes, classes, centers, depths
            )

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, boxes, classes, contours
        )

        # Draw object info with smoothed depths
        image = self._draw_object_info_with_smoothed_depth(
            image, boxes, classes, centers, depths
        )

        return image

    def _smooth_detections(self, boxes, classes, centers, depths=None):
        """
        Apply temporal smoothing to detection boxes, centers, and depths
        Uses exponential moving average to reduce jitter

        Args:
            boxes: Current frame bounding boxes
            classes: Current frame class labels
            centers: Current frame object centers
            depths: Optional depth values at centers

        Returns:
            Smoothed boxes, centers, and depths
        """
        if self.prev_boxes is None or len(self.prev_boxes) == 0:
            # First frame or no previous detections - use current as-is
            self.prev_boxes = boxes
            self.prev_classes = classes
            self.prev_centers = centers
            self.prev_depths = depths
            return boxes, centers, depths

        # Match current detections with previous ones
        smoothed_boxes = []
        smoothed_centers = []
        smoothed_depths = [] if depths is not None else None

        for i, (box, class_name, center) in enumerate(zip(boxes, classes, centers)):
            # Find best match in previous frame (by IoU and class)
            best_match_idx = self._find_best_match(box, class_name, i)

            if best_match_idx is not None:
                # Smooth with previous detection
                prev_box = self.prev_boxes[best_match_idx]
                prev_center = self.prev_centers[best_match_idx]

                # Exponential moving average: new = alpha * prev + (1-alpha) * current
                smoothed_box = [
                    int(self.smoothing_alpha * prev_box[0] + (1 - self.smoothing_alpha) * box[0]),
                    int(self.smoothing_alpha * prev_box[1] + (1 - self.smoothing_alpha) * box[1]),
                    int(self.smoothing_alpha * prev_box[2] + (1 - self.smoothing_alpha) * box[2]),
                    int(self.smoothing_alpha * prev_box[3] + (1 - self.smoothing_alpha) * box[3])
                ]

                smoothed_center = (
                    int(self.smoothing_alpha * prev_center[0] + (1 - self.smoothing_alpha) * center[0]),
                    int(self.smoothing_alpha * prev_center[1] + (1 - self.smoothing_alpha) * center[1])
                )

                # Smooth depth if available
                if depths is not None and self.prev_depths is not None:
                    current_depth = depths[i]
                    prev_depth = self.prev_depths[best_match_idx]

                    # Only smooth if both depths are valid (> 0)
                    if current_depth > 0 and prev_depth > 0:
                        smoothed_depth = int(
                            self.smoothing_alpha * prev_depth +
                            (1 - self.smoothing_alpha) * current_depth
                        )
                    else:
                        # Use current depth if previous was invalid
                        smoothed_depth = current_depth
                else:
                    smoothed_depth = depths[i] if depths is not None else None
            else:
                # New detection - use current values
                smoothed_box = box
                smoothed_center = center
                smoothed_depth = depths[i] if depths is not None else None

            smoothed_boxes.append(smoothed_box)
            smoothed_centers.append(smoothed_center)
            if smoothed_depths is not None:
                smoothed_depths.append(smoothed_depth)

        # Update previous detections
        self.prev_boxes = smoothed_boxes
        self.prev_classes = classes
        self.prev_centers = smoothed_centers
        self.prev_depths = smoothed_depths

        return smoothed_boxes, smoothed_centers, smoothed_depths

    def _find_best_match(self, box, class_name, current_idx):
        """
        Find best matching detection from previous frame

        Args:
            box: Current bounding box [x1, y1, x2, y2]
            class_name: Current object class
            current_idx: Index in current detections

        Returns:
            Index of best match in previous frame, or None
        """
        if self.prev_boxes is None or len(self.prev_boxes) == 0:
            return None

        best_iou = 0.3  # Minimum IoU threshold for matching
        best_idx = None

        for i, (prev_box, prev_class) in enumerate(zip(self.prev_boxes, self.prev_classes)):
            # Only match same class
            if prev_class != class_name:
                continue

            # Calculate IoU (Intersection over Union)
            iou = self._calculate_iou(box, prev_box)

            if iou > best_iou:
                best_iou = iou
                best_idx = i

        return best_idx

    def _calculate_iou(self, box1, box2):
        """
        Calculate Intersection over Union between two boxes

        Args:
            box1, box2: Bounding boxes as [x1, y1, x2, y2]

        Returns:
            IoU score (0.0 to 1.0)
        """
        # Intersection rectangle
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        # No intersection
        if x2 < x1 or y2 < y1:
            return 0.0

        # Intersection area
        intersection = (x2 - x1) * (y2 - y1)

        # Union area
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = box1_area + box2_area - intersection

        return intersection / union if union > 0 else 0.0

    def _extract_depths(self, centers, depth_frame):
        """
        Extract depth values at object centers

        Args:
            centers: List of (cx, cy) center points
            depth_frame: Depth frame (H x W)

        Returns:
            List of depth values in millimeters
        """
        depths = []
        h_depth, w_depth = depth_frame.shape[:2]

        for cx, cy in centers:
            if 0 <= cy < h_depth and 0 <= cx < w_depth:
                depth = depth_frame[cy, cx]
                depths.append(int(depth))
            else:
                depths.append(0)  # Invalid depth

        return depths

    def _draw_object_info_with_smoothed_depth(
        self, frame, boxes, classes, centers, depths
    ):
        """
        Draw labels with smoothed depth information

        Args:
            frame: Input BGR image
            boxes: List of bounding boxes
            classes: List of class names
            centers: List of center points
            depths: List of smoothed depth values (or None)

        Returns:
            frame: Frame with labels drawn
        """
        import cv2

        for i, (box, class_name, center) in enumerate(
            zip(boxes, classes, centers)
        ):
            x, y, w, h = box
            cx, cy = center

            # Draw center point and crosshair
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.drawMarker(
                frame,
                (cx, cy),
                (0, 255, 255),
                cv2.MARKER_CROSS,
                20,
                2
            )

            # Prepare label
            label = class_name

            # Add smoothed depth if available
            if depths is not None and i < len(depths):
                depth = depths[i]
                if depth > 0:
                    label += f" {depth}mm"

            # Draw label background (semi-transparent black)
            (label_w, label_h), baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                2
            )
            # Position label near center point
            label_x = cx - label_w // 2
            label_y = cy - 15
            cv2.rectangle(
                frame,
                (label_x - 5, label_y - label_h - 5),
                (label_x + label_w + 5, label_y + 5),
                (0, 0, 0),
                -1
            )

            # Draw label text in white
            cv2.putText(
                frame,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        return frame

    def _process_face_detection(self, image: np.ndarray) -> np.ndarray:
        """Process frame with face landmark detection"""
        return self.face_detector.detect_and_draw(image)

    def _process_combined_detection(
        self, image: np.ndarray, depth_frame: Optional[np.ndarray]
    ) -> np.ndarray:
        """Process frame with both object detection and face tracking"""
        # First, run object detection (includes person segmentation)
        (boxes, classes,
         contours, centers) = self.segmentation_model.detect_objects_mask(
            image
        )

        # Extract depth values at object centers (before smoothing)
        depths = None
        if depth_frame is not None and len(centers) > 0:
            depths = self._extract_depths(centers, depth_frame)

        # Apply temporal smoothing to stabilize detections
        if self.smoothing_enabled and len(boxes) > 0:
            boxes, centers, depths = self._smooth_detections(
                boxes, classes, centers, depths
            )

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, boxes, classes, contours
        )

        # Draw object info with smoothed depths
        image = self._draw_object_info_with_smoothed_depth(
            image, boxes, classes, centers, depths
        )

        # Then overlay face landmarks on top
        image = self.face_detector.detect_and_draw(image)

        return image

    def toggle_mode(self):
        """Toggle between detection modes: objects -> combined -> face -> camera -> objects"""
        if self.segmentation_model:
            if self.detection_mode == "objects":
                self.detection_mode = "combined"
                print("✓ Switched to combined mode (face + objects)")
            elif self.detection_mode == "combined":
                self.detection_mode = "face"
                print("✓ Switched to face tracking mode")
            elif self.detection_mode == "face":
                self.detection_mode = "camera"
                print("✓ Switched to camera only mode")
            else:  # camera
                self.detection_mode = "objects"
                print("✓ Switched to object detection mode")
        else:
            # No segmentation model - toggle between face and camera only
            if self.detection_mode == "face":
                self.detection_mode = "camera"
                print("✓ Switched to camera only mode")
            else:  # camera
                self.detection_mode = "face"
                print("✓ Switched to face tracking mode")

    @property
    def has_object_detection(self) -> bool:
        """Check if object detection is available"""
        return self.segmentation_model is not None
