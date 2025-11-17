"""
Application Configuration and Feature Detection
Handles hardware/software availability detection and app settings
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

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

    # Spatial smoothing settings (morphological operations)
    spatial_smoothing_enabled: bool = True
    spatial_smoothing_kernel_shape: str = "ellipse"
    spatial_smoothing_small_kernel: int = 3
    spatial_smoothing_medium_kernel: int = 5
    spatial_smoothing_large_kernel: int = 7
    spatial_smoothing_iterations: int = 2

    # Temporal tracking settings (ByteTrack)
    temporal_tracking_enabled: bool = True
    temporal_tracking_thresh: float = 0.6
    temporal_tracking_buffer: int = 60
    temporal_tracking_match: float = 0.7
    temporal_smoothing_alpha: float = 0.97

    # Depth validation settings (RealSense)
    depth_validation_enabled: bool = True
    depth_discontinuity_threshold: float = 0.03
    depth_min_confidence: float = 0.5
    depth_edge_dilation: int = 1
    depth_use_bilateral_filter: bool = True

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
    skip_cameras: List[str] = field(default_factory=list)  # Camera name patterns to skip

    # Video display settings
    display_width: int = 800
    display_height: int = 650
    window_width: int = 1230
    window_height: int = 960
    window_left: int = 100
    window_top: int = 100


def get_config_path() -> Path:
    """Get the path to the user config file"""
    current_file = Path(__file__)
    # Navigate up: settings.py -> config/ -> aaa_core/ -> src/ ->
    # core/ -> packages/ -> project_root
    project_root = current_file.parent.parent.parent.parent.parent.parent
    return project_root / "config" / "config.yaml"


def load_user_config() -> dict:
    """
    Load user configuration from config.yaml if it exists

    Returns:
        Dictionary of user configuration values, empty dict if no config file
    """
    if not YAML_AVAILABLE:
        return {}

    config_path = get_config_path()

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


def save_window_geometry(width: int, height: int, left: int, top: int):
    """
    Save window geometry to config file

    Args:
        width: Window width in pixels
        height: Window height in pixels
        left: Window left position in pixels
        top: Window top position in pixels
    """
    if not YAML_AVAILABLE:
        return

    config_path = get_config_path()

    # Load existing config (suppress success message during save)
    if config_path.exists():
        try:
            with open(config_path) as f:
                user_config = yaml.safe_load(f) or {}
        except Exception as e:
            error(f"Error loading config.yaml: {e}")
            return
    else:
        user_config = {}

    # Update display settings
    if 'display' not in user_config:
        user_config['display'] = {}

    user_config['display']['window_width'] = width
    user_config['display']['window_height'] = height
    user_config['display']['window_left'] = left
    user_config['display']['window_top'] = top

    # Save back to file
    try:
        with open(config_path, 'w') as f:
            yaml.dump(user_config, f, default_flow_style=False, sort_keys=False)
        print(f"ℹ Window geometry saved: {width}x{height} at ({left}, {top})")
    except Exception as e:
        error(f"Error saving window geometry to config: {e}")


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
        if 'skip_cameras' in camera:
            config.skip_cameras = camera['skip_cameras'] or []

    # Detection settings
    if 'detection' in user_config:
        detection = user_config['detection']
        if 'threshold' in detection:
            config.detection_threshold = detection['threshold']
        if 'yolo_model_size' in detection:
            config.yolo_model_size = detection['yolo_model_size']

        # Spatial smoothing settings
        if 'spatial_smoothing' in detection:
            smoothing = detection['spatial_smoothing']
            if 'enabled' in smoothing:
                config.spatial_smoothing_enabled = smoothing['enabled']
            if 'kernel_shape' in smoothing:
                config.spatial_smoothing_kernel_shape = smoothing['kernel_shape']
            if 'small_object_kernel' in smoothing:
                config.spatial_smoothing_small_kernel = smoothing['small_object_kernel']
            if 'medium_object_kernel' in smoothing:
                config.spatial_smoothing_medium_kernel = smoothing['medium_object_kernel']
            if 'large_object_kernel' in smoothing:
                config.spatial_smoothing_large_kernel = smoothing['large_object_kernel']
            if 'iterations' in smoothing:
                config.spatial_smoothing_iterations = smoothing['iterations']

        # Temporal tracking settings
        if 'temporal_tracking' in detection:
            tracking = detection['temporal_tracking']
            if 'enabled' in tracking:
                config.temporal_tracking_enabled = tracking['enabled']
            if 'track_thresh' in tracking:
                config.temporal_tracking_thresh = tracking['track_thresh']
            if 'track_buffer' in tracking:
                config.temporal_tracking_buffer = tracking['track_buffer']
            if 'match_thresh' in tracking:
                config.temporal_tracking_match = tracking['match_thresh']
            if 'smoothing_alpha' in tracking:
                config.temporal_smoothing_alpha = tracking['smoothing_alpha']

        # Depth validation settings
        if 'depth_validation' in detection:
            depth_val = detection['depth_validation']
            if 'enabled' in depth_val:
                config.depth_validation_enabled = depth_val['enabled']
            if 'discontinuity_threshold' in depth_val:
                config.depth_discontinuity_threshold = depth_val['discontinuity_threshold']
            if 'min_confidence' in depth_val:
                config.depth_min_confidence = depth_val['min_confidence']
            if 'edge_dilation' in depth_val:
                config.depth_edge_dilation = depth_val['edge_dilation']
            if 'use_bilateral_filter' in depth_val:
                config.depth_use_bilateral_filter = depth_val['use_bilateral_filter']

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
        if 'window_left' in display:
            config.window_left = display['window_left']
        if 'window_top' in display:
            config.window_top = display['window_top']


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
