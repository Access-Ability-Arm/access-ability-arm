"""
Application Configuration and Feature Detection
Handles hardware/software availability detection and app settings
"""

from dataclasses import dataclass
from typing import Optional

from aaa_core.config.console import error, success, underline


@dataclass
class AppConfig:
    """Application configuration and feature flags"""

    # Hardware availability
    realsense_available: bool = False

    # Segmentation model availability
    segmentation_available: bool = False
    segmentation_model: Optional[str] = None  # 'rfdetr', 'yolov11', 'maskrcnn'

    # YOLOv11 model configuration
    # 'n' (nano), 's' (small), 'm' (medium), 'l' (large), 'x' (xlarge)
    yolo_model_size: str = "x"
    # XLarge (x) provides best accuracy for assistive robotics
    # Better at detecting small objects and reducing false positives
    # Sizes: nano (~6MB), small (~22MB), medium (~50MB),
    # large (~100MB), xlarge (~200MB)

    # Detection settings
    # Balance between detecting small objects and avoiding false positives
    detection_threshold: float = 0.5

    # Button behavior
    button_hold_threshold: float = 0.5  # seconds

    # Robotic arm settings
    lite6_ip: str = "192.168.1.203"  # Default IP for UFactory Lite6
    lite6_port: int = 502  # Modbus TCP port
    lite6_available: bool = False

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
        from aaa_core.hardware.realsense_camera import RealsenseCamera  # noqa: F401

        config.realsense_available = True
        success(f"{underline('RealSense camera')} support available")
    except ImportError:
        error(
            "RealSense camera not available - using standard webcam only"
        )

    # Try to detect Lite6 arm driver
    try:
        from aaa_lite6_driver import Lite6Arm  # noqa: F401

        config.lite6_available = True
        success(f"{underline('Lite6 arm driver')} available")
    except ImportError:
        error("Lite6 arm driver not available")

    # Try RF-DETR first (SOTA 2025), fallback to YOLOv11, then Mask R-CNN
    # Note: optimize_for_inference() breaks mask output, so we skip optimization
    try:
        from aaa_vision.rfdetr_seg import RFDETRSeg  # noqa: F401
        config.segmentation_available = True
        config.segmentation_model = "rfdetr"
        success(
            f"{underline('RF-DETR Seg')} object detection available "
            "(SOTA Nov 2025, 44.3 mAP)"
        )
    except ImportError as e:
        error(f"RF-DETR not available: {e}")
        try:
            from aaa_vision.yolov11_seg import YOLOv11Seg  # noqa: F401

            config.segmentation_available = True
            config.segmentation_model = "yolov11"
            success(
                f"{underline('YOLOv11-seg')} object detection available "
                "(good)"
            )
        except ImportError as e2:
            error(f"YOLOv11-seg not available: {e2}")
            try:
                from aaa_vision.mask_rcnn import MaskRCNN  # noqa: F401

                config.segmentation_available = True
                config.segmentation_model = "maskrcnn"
                success("Mask R-CNN object detection available (legacy)")
            except ImportError:
                error("No segmentation model available - face tracking only")

    return config


# Global configuration instance (initialized on import)
app_config = detect_hardware_capabilities()
