"""
Detection Manager
Manages switching between different detection modes (face tracking vs object detection)
"""

from typing import Optional

import numpy as np

from config.settings import app_config
from vision.face_detector import FaceDetector


class DetectionManager:
    """Manages detection mode and delegates to appropriate detector"""

    def __init__(self):
        """Initialize detection manager with available detectors"""
        print("Detection manager initialized")

        # Always initialize face detector (MediaPipe is always available)
        self.face_detector = FaceDetector()

        # Initialize segmentation model if available
        self.segmentation_model = None
        if app_config.segmentation_available:
            self.segmentation_model = self._initialize_segmentation_model()

        # Set default detection mode
        self.detection_mode = "objects" if self.segmentation_model else "face"
        print(f"Detection mode: {self.detection_mode}")

    def _initialize_segmentation_model(self):
        """Initialize the appropriate segmentation model"""
        try:
            if app_config.segmentation_model == "yolov12":
                from vision.yolov12_seg import YOLOv12Seg

                model = YOLOv12Seg(model_size="n")  # nano = fastest
                print(f"✓ {app_config.segmentation_model} initialized")
                return model
            elif app_config.segmentation_model == "maskrcnn":
                from vision.mask_rcnn import MaskRCNN

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
        else:
            return self._process_face_detection(image)

    def _process_object_detection(
        self, image: np.ndarray, depth_frame: Optional[np.ndarray]
    ) -> np.ndarray:
        """Process frame with object detection"""
        # Get object masks
        boxes, classes, contours, centers = self.segmentation_model.detect_objects_mask(
            image
        )

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(image)

        # Show depth info if available
        if depth_frame is not None:
            self.segmentation_model.draw_object_info(image, depth_frame)

        return image

    def _process_face_detection(self, image: np.ndarray) -> np.ndarray:
        """Process frame with face landmark detection"""
        return self.face_detector.detect_and_draw(image)

    def toggle_mode(self):
        """Toggle between face tracking and object detection modes"""
        if self.segmentation_model:
            if self.detection_mode == "face":
                self.detection_mode = "objects"
                print("✓ Switched to object detection mode")
            else:
                self.detection_mode = "face"
                print("✓ Switched to face tracking mode")
        else:
            print("✗ Object detection not available - No segmentation model loaded")

    @property
    def has_object_detection(self) -> bool:
        """Check if object detection is available"""
        return self.segmentation_model is not None
