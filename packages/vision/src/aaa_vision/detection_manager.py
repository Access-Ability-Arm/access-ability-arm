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

from aaa_vision.detection_logger import DetectionLogger
from aaa_vision.face_detector import FaceDetector
from aaa_vision.object_tracker import ObjectTracker


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

        # Initialize advanced object tracker with Kalman filter and multi-frame consensus
        # Optimized for stationary home assistant objects (cups, books, etc. on table)
        self.object_tracker = ObjectTracker(
            iou_threshold=0.35,        # Minimum IoU for matching objects across frames
            min_frames_to_show=3,      # Objects must appear in N consecutive frames (lower for stationary objects)
            max_frames_missing=15,     # Keep showing for N frames after disappear (high for detector inconsistency)
            smoothing_alpha=0.9        # Reserved for future depth smoothing if needed
        )

        # Initialize detection logger (disabled by default, enable with toggle_logging())
        self.logger = DetectionLogger(enabled=False)

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

        # Extract depth values at object centers
        depths = None
        if depth_frame is not None and len(centers) > 0:
            depths = self._extract_depths(centers, depth_frame)

        # Update tracker with new detections (applies Kalman filter + multi-frame consensus)
        tracked_objects = self.object_tracker.update(boxes, classes, centers, depths)

        # Log detections for analysis (if logging enabled)
        if self.logger.enabled:
            raw_detections = [(cls, tuple(center)) for cls, center in zip(classes, centers)]
            tracked_detections = [(obj.class_name, tuple(obj.center)) for obj in tracked_objects]
            self.logger.log_frame(raw_detections, tracked_detections, boxes,
                                [obj.box for obj in tracked_objects])

        # Extract data from tracked objects for drawing
        if len(tracked_objects) > 0:
            # Get contours for tracked objects by matching centers
            tracked_boxes = [obj.box for obj in tracked_objects]
            tracked_classes = [obj.class_name for obj in tracked_objects]
            tracked_centers = [obj.center for obj in tracked_objects]
            tracked_depths = [obj.smoothed_depth for obj in tracked_objects]

            # Match contours to tracked objects
            tracked_contours = []
            for tracked_center in tracked_centers:
                # Find matching contour from original detections
                best_match_idx = None
                best_dist = float('inf')
                for i, center in enumerate(centers):
                    dist = ((tracked_center[0] - center[0])**2 +
                           (tracked_center[1] - center[1])**2)**0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_match_idx = i

                if best_match_idx is not None and best_dist < 50:  # Within 50 pixels
                    tracked_contours.append(contours[best_match_idx])
                else:
                    tracked_contours.append([])  # No matching contour
        else:
            tracked_boxes = []
            tracked_classes = []
            tracked_contours = []
            tracked_centers = []
            tracked_depths = []

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, tracked_boxes, tracked_classes, tracked_contours
        )

        # Draw object info with tracked positions and depths
        image = self._draw_object_info_with_smoothed_depth(
            image, tracked_boxes, tracked_classes, tracked_centers, tracked_depths
        )

        return image



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

            # Add smoothed depth if available (convert mm to cm with 1 decimal)
            if depths is not None and i < len(depths):
                depth = depths[i]
                if depth is not None and depth > 0:
                    depth_cm = depth / 10.0
                    label += f" {depth_cm:.1f}cm"

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

        # Extract depth values at object centers
        depths = None
        if depth_frame is not None and len(centers) > 0:
            depths = self._extract_depths(centers, depth_frame)

        # Update tracker with new detections (applies Kalman filter + multi-frame consensus)
        tracked_objects = self.object_tracker.update(boxes, classes, centers, depths)

        # Log detections for analysis (if logging enabled)
        if self.logger.enabled:
            raw_detections = [(cls, tuple(center)) for cls, center in zip(classes, centers)]
            tracked_detections = [(obj.class_name, tuple(obj.center)) for obj in tracked_objects]
            self.logger.log_frame(raw_detections, tracked_detections, boxes,
                                [obj.box for obj in tracked_objects])

        # Extract data from tracked objects for drawing
        if len(tracked_objects) > 0:
            tracked_boxes = [obj.box for obj in tracked_objects]
            tracked_classes = [obj.class_name for obj in tracked_objects]
            tracked_centers = [obj.center for obj in tracked_objects]
            tracked_depths = [obj.smoothed_depth for obj in tracked_objects]

            # Match contours to tracked objects
            tracked_contours = []
            for tracked_center in tracked_centers:
                best_match_idx = None
                best_dist = float('inf')
                for i, center in enumerate(centers):
                    dist = ((tracked_center[0] - center[0])**2 +
                           (tracked_center[1] - center[1])**2)**0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_match_idx = i

                if best_match_idx is not None and best_dist < 50:
                    tracked_contours.append(contours[best_match_idx])
                else:
                    tracked_contours.append([])
        else:
            tracked_boxes = []
            tracked_classes = []
            tracked_contours = []
            tracked_centers = []
            tracked_depths = []

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, tracked_boxes, tracked_classes, tracked_contours
        )

        # Draw object info with tracked positions and depths
        image = self._draw_object_info_with_smoothed_depth(
            image, tracked_boxes, tracked_classes, tracked_centers, tracked_depths
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

    def toggle_logging(self):
        """Toggle detection logging for stability analysis"""
        if self.logger.enabled:
            self.logger.disable()
            print("✓ Detection logging disabled")
        else:
            self.logger.enable()
            print("✓ Detection logging enabled")

    @property
    def has_object_detection(self) -> bool:
        """Check if object detection is available"""
        return self.segmentation_model is not None
