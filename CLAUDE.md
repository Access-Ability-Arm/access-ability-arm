# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DE-GUI is a PyQt6-based GUI application for the Drane Engineering assistive robotic arm. It integrates:
- Intel RealSense camera for depth sensing
- Mask R-CNN for object detection and segmentation
- MediaPipe for face landmark tracking
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
# Main application with face tracking (requires standard webcam)
python main.py

# RealSense version with object detection (requires RealSense camera + Mask R-CNN models)
python main-rd.py

# Standalone object distance measurement (requires RealSense camera)
python measure_object_distance.py
```

### Application Requirements

**main.py (Face Tracking):**
- Standard webcam (MacBook FaceTime, USB webcam, or Continuity Camera)
- MediaPipe library (auto-installed via requirements.txt)
- No additional model files needed
- Works on macOS, Windows, Linux

**main-rd.py (Object Detection):**
- Intel RealSense D400-series camera
- pyrealsense2 library (manual installation required)
- DNN model files in `dnn/` directory (must be downloaded separately)
- Mask R-CNN models (~200MB)

## Architecture

### Main Application Structure

**Two Main Versions:**
1. `Main.py` - Uses standard webcam with MediaPipe face landmark tracking
2. `Main-rd.py` - Uses RealSense camera with Mask R-CNN object detection

Both share the same core PyQt6 GUI structure loaded from `draftGUI.ui`.

### Key Components

**MainWindow (PyQt6.QtWidgets.QMainWindow)**
- Loads Qt Designer GUI from `draftGUI.ui`
- Manages robotic arm control buttons (x_pos/neg, y_pos/neg, z_pos/neg, grip_pos/neg, grip_state)
- Connects button signals to `Button_Action()` handler
- Initializes camera tracking and image monitoring threads

**button_monitor (QtCore.QThread)**
- Monitors button press/hold duration
- Differentiates between press (<0.5s) and hold (>0.5s) actions
- Runs continuously while button is pressed

**imageMonitor (QtCore.QThread)**
- Main.py: Processes webcam feed with MediaPipe face mesh tracking
  - Tracks mouth landmarks (20 specific points)
  - Calculates and displays center of mouth
- Main-rd.py: Processes RealSense depth + color frames
  - Integrates with RealsenseCamera and MaskRCNN classes
  - Displays object detection masks and depth information
- Converts OpenCV frames to PyQt6 QImage format
- Emits ImageUpdate signal to update GUI label

**camera_tracker**
- Enumerates available cameras on Windows, macOS, and Linux
- Windows: Uses `winsdk.windows.devices.enumeration` to get detailed camera names
- macOS/Linux: Uses generic camera names (e.g., "Camera 0", "Camera 1")
- Checks up to 3 camera indices by default to minimize startup errors
- main-rd.py has most camera enumeration code commented out

### Computer Vision Modules

**realsense_camera.py - RealsenseCamera class**
- Configures RealSense pipeline for 1280x720 @ 30fps
- Streams aligned color (BGR8) and depth (Z16) frames
- Applies spatial filtering and hole-filling to depth data
- `get_frame_stream()` returns: (success, color_image, depth_image)

**mask_rcnn.py - MaskRCNN class**
- Loads TensorFlow Mask R-CNN model from `dnn/` directory:
  - `frozen_inference_graph_coco.pb` - Pre-trained model weights (~200MB)
  - `mask_rcnn_inception_v2_coco_2018_01_28.pbtxt` - Model configuration
  - `classes.txt` - COCO dataset class labels (80 classes)
- Detection threshold: 0.7, Mask threshold: 0.3
- Uses CUDA backend if available
- `detect_objects_mask()`: Returns boxes, classes, contours, centers
- `draw_object_mask()`: Draws colored segmentation masks on frame
- `draw_object_info()`: Overlays class names, depth measurements, crosshairs

### Downloading DNN Model Files

The `dnn/` directory with Mask R-CNN model files is **not included in the repository** and must be downloaded separately:

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

**Note**: These files are only required for `main-rd.py`. The `main.py` version (face tracking) does not need them.

### Threading Architecture

The application uses PyQt6's QThread for concurrent operations:
1. Main thread: GUI event loop, button handling
2. imageMonitor thread: Continuous camera capture and processing
3. button_monitor thread: Started on button press, monitors hold duration

All camera processing happens in imageMonitor thread to prevent GUI blocking. Updates are sent to main thread via Qt signals (ImageUpdate).

## Face Landmark Tracking (Main.py)

MediaPipe face mesh tracks 20 mouth landmark points:
```python
mouthPoints = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
```

Calculates center point from landmarks 13 and 14, displayed as yellow circle. All mouth points shown as green circles.

Reference: [MediaPipe canonical face model](https://raw.githubusercontent.com/google/mediapipe/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png)

## Dependencies

- PyQt6 >= 6.6.0 - GUI framework
- opencv-python >= 4.8.0 - Computer vision
- numpy >= 1.24.0 - Array operations
- mediapipe >= 0.10.0 - Face tracking (Main.py)
- pyrealsense2 - RealSense camera (manual install, v2.56.5)
- ipykernel >= 7.0.0 - Jupyter support

## Platform-Specific Notes

**Windows**: 
- Uses `winsdk.windows.devices.enumeration` for camera enumeration (VIDEO_DEVICES = 4)
- `sys.coinit_flags = 2` set to suppress COM initialization warnings

**macOS**:
- Supports built-in FaceTime HD camera, USB webcams, and Continuity Camera
- AVCaptureDeviceTypeExternal deprecation warning is harmless and can be ignored
- Continuity Camera (iPhone/iPad) may appear as Camera 1

**Linux**:
- Uses Video4Linux (V4L2) for camera access
- Generic camera names assigned during enumeration

## Common Issues and Solutions

**"TypeError: 'NoneType' object is not iterable" on startup:**
- Fixed in latest version - macOS/Linux now properly return camera list

**"OpenCV: out device of bound" warnings:**
- Harmless - occurs when app checks for cameras beyond available count
- Reduced to checking only 3 cameras to minimize console spam

**Camera enumeration:**
- main.py: Fully functional on all platforms
- main-rd.py: Most camera enumeration code commented out

**DNN model files:**
- Not included in repository (~200MB total)
- Must be downloaded separately for main-rd.py
- See "Downloading DNN Model Files" section above

**Face landmark tracking:**
- Only available in main.py
- Code commented out in main-rd.py (replaced with object detection)
