"""
Application Configuration and Feature Detection
Handles hardware/software availability detection and app settings
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aaa_core.config.console import error, success, underline

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


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
    lite6_auto_connect: bool = True  # Auto-connect on startup
    lite6_available: bool = False

    # Movement settings
    tap_step_size: int = 10  # mm for short button press
    hold_step_size: int = 50  # mm for long button press
    movement_speed: int = 100  # mm/s
    gripper_speed: int = 5000  # pulse/s

    # Camera settings
    max_cameras_to_check: int = 3
    default_camera: int = 0

    # Video display settings
    display_width: int = 800
    display_height: int = 650
    window_width: int = 1230
    window_height: int = 695


def load_user_config() -> dict:
    """
    Load user configuration from config.yaml if it exists

    Returns:
        Dictionary of user configuration values, empty dict if no config file
    """
    if not YAML_AVAILABLE:
        return {}

    # Find project root (go up from this file location)
    current_file = Path(__file__)
    # Navigate up: settings.py -> config/ -> aaa_core/ -> src/ ->
    # core/ -> packages/ -> project_root
    project_root = current_file.parent.parent.parent.parent.parent.parent

    config_path = project_root / "config.yaml"

    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            user_config = yaml.safe_load(f)
            success(f"Loaded user configuration from {config_path}")
            return user_config or {}
    except Exception as e:
        error(f"Error loading config.yaml: {e}")
        return {}


def apply_user_config(config: AppConfig, user_config: dict):
    """Apply user configuration values to AppConfig"""
    if not user_config:
        return

    # Arm settings
    if 'arm' in user_config:
        arm = user_config['arm']
        if 'ip' in arm:
            config.lite6_ip = arm['ip']
        if 'port' in arm:
            config.lite6_port = arm['port']
        if 'auto_connect' in arm:
            config.lite6_auto_connect = arm['auto_connect']

    # Camera settings
    if 'camera' in user_config:
        camera = user_config['camera']
        if 'max_cameras_to_check' in camera:
            config.max_cameras_to_check = camera['max_cameras_to_check']
        if 'default_camera' in camera:
            config.default_camera = camera['default_camera']

    # Detection settings
    if 'detection' in user_config:
        detection = user_config['detection']
        if 'threshold' in detection:
            config.detection_threshold = detection['threshold']
        if 'yolo_model_size' in detection:
            config.yolo_model_size = detection['yolo_model_size']

    # Control settings
    if 'controls' in user_config:
        controls = user_config['controls']
        if 'button_hold_threshold' in controls:
            config.button_hold_threshold = controls['button_hold_threshold']
        if 'tap_step_size' in controls:
            config.tap_step_size = controls['tap_step_size']
        if 'hold_step_size' in controls:
            config.hold_step_size = controls['hold_step_size']
        if 'movement_speed' in controls:
            config.movement_speed = controls['movement_speed']
        if 'gripper_speed' in controls:
            config.gripper_speed = controls['gripper_speed']

    # Display settings
    if 'display' in user_config:
        display = user_config['display']
        if 'width' in display:
            config.display_width = display['width']
        if 'height' in display:
            config.display_height = display['height']
        if 'window_width' in display:
            config.window_width = display['window_width']
        if 'window_height' in display:
            config.window_height = display['window_height']


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

    # Load and apply user configuration
    user_config = load_user_config()
    apply_user_config(config, user_config)

    return config


# Global configuration instance (initialized on import)
app_config = detect_hardware_capabilities()
