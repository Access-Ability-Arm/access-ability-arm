# Monorepo Structure

This repository is organized as a Python monorepo with three separate packages:

## Package Structure

```
access-ability-arm/
├── packages/
│   ├── core/           # Core functionality (config, hardware, workers)
│   ├── vision/         # Computer vision modules
│   └── gui/            # GUI implementations (Flet, PyQt6)
├── data/
│   ├── models/         # Model weights (YOLO, etc.)
│   └── dnn/            # Legacy Mask R-CNN models
├── main.py             # Flet GUI entry point
└── pyproject.toml      # Workspace configuration
```

## Packages

### aaa-core (`packages/core/`)
Core modules for configuration, hardware interfaces, and worker threads.

**Modules:**
- `aaa_core.config.settings` - Application configuration
- `aaa_core.config.console` - Console output utilities
- `aaa_core.hardware.camera_manager` - Camera enumeration
- `aaa_core.hardware.button_controller` - Button input handling
- `aaa_core.hardware.realsense_camera` - RealSense interface
- `aaa_core.workers.image_processor` - Camera processing thread

### aaa-vision (`packages/vision/`)
Computer vision modules for object detection and face tracking.

**Modules:**
- `aaa_vision.rfdetr_seg` - RF-DETR segmentation (SOTA, 44.3 mAP)
- `aaa_vision.yolov11_seg` - YOLOv11 segmentation
- `aaa_vision.mask_rcnn` - Legacy Mask R-CNN
- `aaa_vision.face_detector` - MediaPipe face tracking
- `aaa_vision.detection_manager` - Detection orchestration

### aaa-gui (`packages/gui/`)
GUI implementations for desktop, web, and mobile.

**Modules:**
- `aaa_gui.flet.main_window` - Modern cross-platform Flet GUI
- `aaa_gui.pyqt.main_window` - Traditional PyQt6 desktop GUI

## Installation

### Quick Start (All Packages)
```bash
# From repository root
pip install -e .
```

### Individual Packages
```bash
# Core package (required by others)
pip install -e packages/core

# Vision package
pip install -e packages/vision

# GUI package (Flet)
pip install -e "packages/gui[flet]"

# GUI package (PyQt6)
pip install -e "packages/gui[pyqt]"

# GUI package (both)
pip install -e "packages/gui[all]"
```

### Development Mode
```bash
# Install all packages with dev dependencies
pip install -e ".[dev]"
```

## Running the Application

```bash
# Flet GUI (desktop)
python main.py

# Flet GUI (web browser)
python main.py --web --port 8550
```

## Data Directory

### models/
Auto-downloaded model weights:
- `yolo11n-seg.pt` - YOLOv11 nano segmentation model (~6MB)
- `yolo11m-seg.pt` - YOLOv11 medium model (~45MB)
- Additional YOLO variants as needed

RF-DETR models are cached by the Roboflow library (typically in `~/.cache/roboflow/`).

### dnn/
Legacy Mask R-CNN models (manual download required):
- `frozen_inference_graph_coco.pb` (~200MB)
- `mask_rcnn_inception_v2_coco_2018_01_28.pbtxt`
- `classes.txt`

## Package Dependencies

```
aaa-core
  └── opencv-python, numpy

aaa-vision
  ├── aaa-core
  ├── mediapipe
  ├── ultralytics (YOLO)
  ├── torch
  └── rfdetr

aaa-gui
  ├── aaa-core
  ├── aaa-vision
  ├── flet (optional)
  └── PyQt6 (optional)
```

## Import Examples

```python
# Core
from aaa_core.config.settings import app_config
from aaa_core.hardware.camera_manager import CameraManager

# Vision
from aaa_vision.rfdetr_seg import RFDETRSeg
from aaa_vision.detection_manager import DetectionManager

# GUI
from aaa_gui.flet.main_window import FletMainWindow
```

## Benefits of Monorepo Structure

1. **Separation of Concerns**: Clear boundaries between vision, GUI, and core
2. **Independent Versioning**: Each package can be versioned separately
3. **Reusability**: Vision package could be used standalone
4. **Better Testing**: Each package can be tested in isolation
5. **Clear Dependencies**: Explicit dependency graph
6. **Flexible Installation**: Install only what you need

## Migration from Legacy Structure

The old flat structure has been reorganized:
- `vision/` → `packages/vision/src/aaa_vision/`
- `gui/`, `flet_gui/` → `packages/gui/src/aaa_gui/`
- `config/`, `hardware/`, `workers/` → `packages/core/src/aaa_core/`
- `models/` → `data/models/`
- `dnn/` → `data/dnn/`

All imports have been updated to use the new `aaa_*` package names.
