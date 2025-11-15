"""
Application Configuration and Feature Detection
Handles hardware/software availability detection and app settings
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    """Application configuration and feature flags"""

    # Hardware availability
    realsense_available: bool = False

    # Segmentation model availability
    segmentation_available: bool = False
    segmentation_model: Optional[str] = None  # 'yolov11' or 'maskrcnn'

    # Detection settings
    detection_threshold: float = 0.5

    # Button behavior
    button_hold_threshold: float = 0.5  # seconds

    # Camera settings
    max_cameras_to_check: int = 3

    # Video display settings
    display_width: int = 800
    display_height: int = 650


def detect_hardware_capabilities() -> AppConfig:
    """
    Detect available hardware and software capabilities

    Returns:
        AppConfig with detected capabilities
    """
    config = AppConfig()

    # Try to detect RealSense camera support
    try:
        from hardware.realsense_camera import RealsenseCamera

        config.realsense_available = True
        print("✓ RealSense camera support available")
    except ImportError:
        print("✗ RealSense camera not available - using standard webcam only")

    # Try YOLOv11-seg first (preferred), fallback to Mask R-CNN
    try:
        from vision.yolov11_seg import YOLOv11Seg

        config.segmentation_available = True
        config.segmentation_model = "yolov11"
        print("✓ YOLOv11-seg object detection available (recommended)")
    except ImportError as e:
        print(f"✗ YOLOv11-seg not available: {e}")
        try:
            from vision.mask_rcnn import MaskRCNN

            config.segmentation_available = True
            config.segmentation_model = "maskrcnn"
            print("✓ Mask R-CNN object detection available (legacy)")
        except ImportError:
            print("✗ No segmentation model available - face tracking only")

    return config


# Global configuration instance (initialized on import)
app_config = detect_hardware_capabilities()
