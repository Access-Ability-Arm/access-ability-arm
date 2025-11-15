# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DE-GUI is a PyQt6-based GUI application for the Drane Engineering assistive robotic arm. It integrates:
- Intel RealSense camera for depth sensing (optional)
- **YOLOv11-seg** for real-time object detection and segmentation (recommended)
- Mask R-CNN for object detection (legacy, slower)
- MediaPipe for face landmark tracking
- Apple Metal GPU acceleration on M-series Macs
- Manual robotic arm controls (x, y, z, grip)

The application allows users to identify objects in the camera feed and enables the robot to differentiate and pick up those items, with both automated (computer vision) and manual control modes.

## Environment Setup

### Python Version Requirement
**This project requires Python 3.11**. MediaPipe (required dependency) does not support Python 3.14+.

### Virtual Environment
```bash
# Install Python 3.11 if needed (macOS with Homebrew)
brew install python@3.11

# Create virtual environment with Python 3.11
python3.11 -m venv venv
# Or on macOS with Homebrew:
/opt/homebrew/bin/python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

**Important**: `pyrealsense2` is commented out in requirements.txt and must be installed manually from source (v2.56.5). Follow the [Intel RealSense installation guide](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation.md).

### Jupyter Kernel Setup (for Zed editor)
```bash
./venv/bin/python -m ipykernel install --user --name de-gui-venv --display-name "Python (DE-GUI venv)"
```

## Running the Application

```bash
# Main application (RECOMMENDED - flexible camera support)
python main.py
```

### Application Features

**main.py (ONLY VERSION - RECOMMENDED):**
- **Camera**: Auto-detects RealSense OR standard webcam (MacBook FaceTime, USB webcam, Continuity Camera)
- **Required**: MediaPipe, Ultralytics (auto-installed via requirements.txt)
- **Optional**: pyrealsense2 (enables depth sensing with RealSense camera)
- **Object Detection**: YOLOv11-seg (auto-downloads ~6MB model on first run)
  - **GPU Acceleration**: Automatically uses Apple Metal (MPS) on M-series Macs, CUDA on NVIDIA, or CPU
  - Much faster and more accurate than legacy Mask R-CNN
  - Falls back to Mask R-CNN if YOLOv11-seg unavailable
- **Modes**: Automatically selects best mode based on available hardware:
  - RealSense + YOLO → Object detection with depth (fastest)
  - Webcam + YOLO → Object detection without depth
  - Webcam only → Face tracking
- **Toggle**: Press 'T' to switch between face tracking and object detection
- **Fixed Reference Point**: Red circle shows depth at position (250, 100) when RealSense is active
- Works on macOS, Windows, Linux

**Legacy versions (ARCHIVED):**
- `archive/main-rd.py` - RealSense-only monolithic version
- `archive/main_old.py` - Pre-refactoring monolithic version
- `archive/measure_object_distance.py` - Standalone distance measurement utility

## Architecture

### Project Structure (Refactored - November 2025)

The codebase follows a clean, modular architecture:

```
access-ability-arm/
├── main.py                    # Entry point (~40 lines)
├── config/
│   ├── __init__.py
│   └── settings.py            # Configuration & feature detection
├── gui/
│   ├── __init__.py
│   ├── main_window.py         # Main window & UI logic
│   └── draftGUI.ui            # Qt Designer UI file
├── hardware/
│   ├── __init__.py
│   ├── camera_manager.py      # Camera enumeration & switching
│   ├── button_controller.py   # Button press/hold detection
│   └── realsense_camera.py    # RealSense interface
├── vision/
│   ├── __init__.py
│   ├── detection_manager.py   # Detection mode orchestration
│   ├── face_detector.py       # MediaPipe face tracking
│   ├── yolov11_seg.py         # YOLOv11 segmentation
│   └── mask_rcnn.py           # Legacy Mask R-CNN
├── workers/
│   ├── __init__.py
│   └── image_processor.py     # Camera processing thread
├── models/
│   └── yolo11n-seg.pt         # YOLOv11 nano model (auto-downloaded)
├── docs/
│   ├── installation.md        # Detailed setup guide
│   └── refactoring.md         # Architecture documentation
└── archive/
    ├── main-rd.py             # Legacy RealSense-only version
    ├── main_old.py            # Pre-refactoring version
    ├── measure_object_distance.py  # Standalone utility
    └── old_modules/           # Duplicate module files
```

### Module Descriptions

#### config/
**settings.py** - Application configuration and capability detection
- `AppConfig`: Dataclass containing all application settings
- `detect_hardware_capabilities()`: Runtime detection of RealSense, YOLOv11, Mask R-CNN
- Centralizes feature flags and configuration

#### gui/
**main_window.py** - Main application window (PyQt6)
- `MainWindow`: Loads `gui/draftGUI.ui`, manages UI events
- Handles robotic arm buttons (x/y/z/grip pos/neg, grip state)
- Camera selection dropdown
- Keyboard shortcuts (T=toggle detection mode)
- Delegates to hardware/workers, pure UI logic

**draftGUI.ui** - Qt Designer UI file
- XML-based UI definition
- Loaded by main_window.py using `uic.loadUi()`
- Contains button layouts, camera feed display, labels

#### hardware/
**camera_manager.py** - Camera detection and enumeration
- `CameraManager`: Finds available cameras (checks indices 0-2 by default)
- Platform-specific naming: Windows (winsdk), macOS/Linux (generic)
- Camera switching support

**button_controller.py** - Button input handling
- `ButtonController`: Monitors button press duration in separate thread
- Differentiates press (<0.5s) vs hold (>0.5s)
- Thread-safe state management

**realsense_camera.py** - Intel RealSense interface
- `RealsenseCamera`: Configures pipeline for 1280x720 @ 30fps
- Streams aligned color (BGR8) and depth (Z16) frames
- Spatial filtering and hole-filling

#### vision/
**detection_manager.py** - Detection orchestration
- `DetectionManager`: Manages face tracking vs object detection modes
- Initializes appropriate models based on availability
- `toggle_mode()`: Switches between detection types
- Delegates to FaceDetector or segmentation models

**face_detector.py** - Face landmark tracking
- `FaceDetector`: MediaPipe face mesh for 20 mouth landmarks
- `detect_and_draw()`: Processes frame and visualizes landmarks
- Calculates mouth center point

**yolov11_seg.py** - Modern object segmentation (RECOMMENDED)
- `YOLOv11Seg`: YOLOv11 instance segmentation
- Auto-downloads models (~6MB nano) to `models/` directory
- Checks `models/yolo11n-seg.pt` first, then downloads if missing
- GPU acceleration: Metal (macOS), CUDA (Windows/Linux), CPU fallback
- Compatible interface with MaskRCNN for drop-in replacement
- Methods:
  - `detect_objects_mask()`: Returns boxes, classes, contours, centers
  - `draw_object_mask()`: Draws colored segmentation masks on frame
  - `draw_object_info()`: Overlays class names, depth measurements, crosshairs

**mask_rcnn.py** - Legacy object segmentation
- `MaskRCNN`: TensorFlow Mask R-CNN (2018 model, ~200MB)
- Manual model download required to `dnn/` directory
- Slower than YOLO, kept for compatibility
- Same interface as YOLOv11Seg for drop-in replacement

#### workers/
**image_processor.py** - Camera processing thread
- `ImageProcessor`: Main processing loop (QtCore.QThread)
- Camera capture (RealSense or webcam)
- Detection processing via DetectionManager
- Fixed reference point depth measurement at (250, 100)
- OpenCV to Qt image conversion
- Frame flipping and scaling
- Emits ImageUpdate signal for GUI
- Properties:
  - `reference_point`: Tuple (x, y) for fixed depth reading
  - `show_reference_point`: Boolean to enable/disable feature

### Computer Vision Modules

**hardware/realsense_camera.py - RealsenseCamera class**
- Configures RealSense pipeline for 1280x720 @ 30fps
- Streams aligned color (BGR8) and depth (Z16) frames
- Applies spatial filtering and hole-filling to depth data
- `get_frame_stream()` returns: (success, color_image, depth_image)

**vision/yolov11_seg.py - YOLOv11Seg class (RECOMMENDED)**
- Modern real-time instance segmentation using Ultralytics YOLOv11
- Model loading priority:
  1. Local file: `models/yolo11{size}-seg.pt`
  2. Auto-download from Ultralytics hub
- **GPU Acceleration**: Automatically detects and uses:
  - Apple Metal (MPS) on M-series Macs
  - NVIDIA CUDA on Windows/Linux
  - CPU fallback for compatibility
- Detection threshold: 0.5 (balanced precision/recall)
- 80 COCO classes (person, car, cup, etc.)
- Model sizes: nano (fastest), small, medium, large, xlarge (most accurate)

**vision/mask_rcnn.py - MaskRCNN class (LEGACY)**
- Loads TensorFlow Mask R-CNN model from `dnn/` directory:
  - `frozen_inference_graph_coco.pb` - Pre-trained model weights (~200MB)
  - `mask_rcnn_inception_v2_coco_2018_01_28.pbtxt` - Model configuration
  - `classes.txt` - COCO dataset class labels (80 classes)
- Detection threshold: 0.7, Mask threshold: 0.3
- Backend: Skips CUDA on macOS, tries Vulkan, falls back to CPU
- Slower than YOLOv11, kept for compatibility

### Downloading DNN Model Files (Optional - Legacy Only)

The `dnn/` directory with Mask R-CNN model files is **not included in the repository** and only needed if YOLOv11 is unavailable:

```bash
# Create dnn directory
mkdir dnn && cd dnn

# Download Mask R-CNN model archive
wget http://download.tensorflow.org/models/object_detection/mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
tar -xvf mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
mv mask_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb frozen_inference_graph_coco.pb

# Download config file
wget https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/mask_rcnn_inception_v2_coco_2018_01_28.pbtxt

# Download COCO classes
wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O classes.txt
```

**Note**: YOLOv11 auto-downloads and is preferred. DNN files only needed as fallback.

### Threading Architecture

The application uses PyQt6's QThread for concurrent operations:
1. **Main thread**: GUI event loop, button handling
2. **ImageProcessor thread** (`workers/image_processor.py`): Continuous camera capture and processing
3. **ButtonController thread** (`hardware/button_controller.py`): Started on button press, monitors hold duration

All camera processing happens in ImageProcessor thread to prevent GUI blocking. Updates are sent to main thread via Qt signals (ImageUpdate).

## Face Landmark Tracking

MediaPipe face mesh tracks 20 mouth landmark points:
```python
mouthPoints = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
```

Calculates center point from landmarks 13 and 14, displayed as yellow circle. All mouth points shown as green circles.

Reference: [MediaPipe canonical face model](https://raw.githubusercontent.com/google/mediapipe/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png)

## Fixed Reference Point Depth Measurement

When RealSense camera is active, a fixed reference point is displayed:
- Location: `(250, 100)` pixels from top-left
- Visual: Red circle (8px radius)
- Display: Distance in millimeters above the circle
- Configurable in `workers/image_processor.py`:
  - `self.reference_point = (x, y)`
  - `self.show_reference_point = True/False`

## Dependencies

Core dependencies (auto-installed via `requirements.txt`):
- PyQt6 >= 6.6.0 - GUI framework
- opencv-python >= 4.8.0 - Computer vision
- numpy >= 1.24.0 - Array operations
- mediapipe >= 0.10.0 - Face tracking
- ultralytics >= 8.0.0 - YOLOv11 segmentation
- torch >= 2.0.0 - Deep learning backend
- ipykernel >= 7.0.0 - Jupyter support (optional)

Optional dependencies (manual install):
- pyrealsense2 - RealSense camera (manual install, v2.56.5)

## Platform-Specific Notes

**Windows**: 
- Uses `winsdk.windows.devices.enumeration` for camera enumeration (VIDEO_DEVICES = 4)
- `sys.coinit_flags = 2` set to suppress COM initialization warnings

**macOS**:
- Supports built-in FaceTime HD camera, USB webcams, and Continuity Camera
- AVCaptureDeviceTypeExternal deprecation warning is harmless and can be ignored
- Continuity Camera (iPhone/iPad) may appear as Camera 1
- Apple Metal (MPS) GPU acceleration automatic on M-series chips

**Linux**:
- Uses Video4Linux (V4L2) for camera access
- Generic camera names assigned during enumeration

## Common Issues and Solutions

**"TypeError: 'NoneType' object is not iterable" on startup:**
- Fixed in latest version - macOS/Linux now properly return camera list

**"OpenCV: out device of bound" warnings:**
- Harmless - occurs when app checks for cameras beyond available count
- Reduced to checking only 3 cameras to minimize console spam

**Camera not detected:**
- Check system permissions (Settings > Privacy > Camera on macOS)
- Try different camera indices in dropdown
- Restart application after plugging in camera

**YOLOv11 model download fails:**
- Check internet connection
- Model will auto-download on first run
- Falls back to Mask R-CNN if download fails

**Slow performance:**
- Check console for GPU acceleration status
- YOLOv11 with GPU is much faster than Mask R-CNN
- Switch to face tracking mode for lighter processing

**DNN model files:**
- Not needed for main.py with YOLOv11
- Only required if YOLOv11 unavailable and using Mask R-CNN fallback
- See "Downloading DNN Model Files" section above

## Documentation

- [README.md](README.md) - Quick start and features
- [docs/installation.md](docs/installation.md) - Detailed setup instructions
- [docs/refactoring.md](docs/refactoring.md) - Architecture and refactoring notes

## Git Repository Structure

```
.gitignore           # Excludes: venv/, __pycache__/, *.pt, models/, archive/, dnn/*.pb
archive/             # Legacy code (not tracked)
models/              # YOLO weights (not tracked)
dnn/                 # Mask R-CNN models (not tracked, .gitignore inside)
```
