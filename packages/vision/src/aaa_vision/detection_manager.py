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
        # Modes: "face", "objects", "combined" (face + objects simultaneously)
        self.detection_mode = "objects" if self.segmentation_model else "face"
        status(f"Detection mode: {self.detection_mode}")

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
        if self.detection_mode == "objects" and self.segmentation_model:
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

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, boxes, classes, contours
        )

        # Draw object info (labels, depth if available)
        image = self.segmentation_model.draw_object_info(
            image, boxes, classes, centers, depth_frame
        )

        return image

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

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(
            image, boxes, classes, contours
        )

        # Draw object info (labels, depth)
        image = self.segmentation_model.draw_object_info(
            image, boxes, classes, centers, depth_frame
        )

        # Then overlay face landmarks on top
        image = self.face_detector.detect_and_draw(image)

        return image

    def toggle_mode(self):
        """Toggle between face tracking, object detection, and combined modes"""
        if self.segmentation_model:
            if self.detection_mode == "face":
                self.detection_mode = "objects"
                print("✓ Switched to object detection mode")
            elif self.detection_mode == "objects":
                self.detection_mode = "combined"
                print("✓ Switched to combined mode (face + objects)")
            else:  # combined
                self.detection_mode = "face"
                print("✓ Switched to face tracking mode")
        else:
            print(
                "✗ Object detection not available - "
                "No segmentation model loaded"
            )

    @property
    def has_object_detection(self) -> bool:
        """Check if object detection is available"""
        return self.segmentation_model is not None
