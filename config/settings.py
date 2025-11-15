"""
Application Configuration and Feature Detection
Handles hardware/software availability detection and app settings
"""

from dataclasses import dataclass
from typing import Optional

from config.console import error, success, underline


@dataclass
class AppConfig:
    """Application configuration and feature flags"""

    # Hardware availability
    realsense_available: bool = False

    # Segmentation model availability
    segmentation_available: bool = False
    segmentation_model: Optional[str] = None  # 'yolov11' or 'maskrcnn'

    # YOLOv11 model configuration
    yolo_model_size: str = "x"  # 'n' (nano), 's' (small), 'm' (medium), 'l' (large), 'x' (xlarge)
    # XLarge (x) provides best accuracy for critical assistive robotics applications
    # Better at detecting small objects (cups) and reducing false positives
    # Model sizes: nano (~6MB), small (~22MB), medium (~50MB), large (~100MB), xlarge (~200MB)

    # Detection settings
    detection_threshold: float = 0.5  # Balance between detecting small objects and avoiding false positives

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
        success(f"{underline('RealSense camera')} support available")
    except ImportError:
        error("RealSense camera not available - using standard webcam only")

    # Try YOLOv11-seg first (preferred), fallback to Mask R-CNN
    try:
        from vision.yolov11_seg import YOLOv11Seg

        config.segmentation_available = True
        config.segmentation_model = "yolov11"
        success(f"{underline('YOLOv11-seg')} object detection available (recommended)")
    except ImportError as e:
        error(f"YOLOv11-seg not available: {e}")
        try:
            from vision.mask_rcnn import MaskRCNN

            config.segmentation_available = True
            config.segmentation_model = "maskrcnn"
            success("Mask R-CNN object detection available (legacy)")
        except ImportError:
            error("No segmentation model available - face tracking only")

    return config


# Global configuration instance (initialized on import)
app_config = detect_hardware_capabilities()
