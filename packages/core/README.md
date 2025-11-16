# AAA Core Package

Core modules for the Access Ability Arm project.

## Features

- **Configuration**: Application settings and hardware capability detection
- **Hardware**: Camera management, button controllers, RealSense interface
- **Workers**: Image processing threads, arm controller (Flet and PyQt6 variants)

## Installation

From the repository root:

```bash
pip install -e packages/core
```

## Optional Dependencies

For Intel RealSense camera support:
```bash
pip install -e "packages/core[realsense]"
```

Note: `pyrealsense2` requires manual installation from source. See installation guide.

## Modules

- `aaa_core.config.settings` - Application configuration
- `aaa_core.hardware.camera_manager` - Camera enumeration and switching
- `aaa_core.hardware.button_controller` - Button press/hold detection
- `aaa_core.hardware.realsense_camera` - RealSense camera interface
- `aaa_core.workers.image_processor` - Camera processing thread
- `aaa_core.workers.arm_controller` - PyQt6-based arm controller
- `aaa_core.workers.arm_controller_flet` - Flet-compatible arm controller (callback-based)
