# Installation Guide

## Requirements

**Python Version:** This project requires **Python 3.11** (MediaPipe does not support Python 3.14+).

**Disk Space:** ~500MB (Python packages + RF-DETR model)

**Hardware:**
- **UFactory Lite6 robotic arm** (optional - app works without arm)
- **Intel RealSense camera** (optional - app works with standard webcams)
- **Any webcam** for basic operation

## Setting Up the Virtual Environment

### 1. Install Python 3.11

- **macOS with Homebrew:**
  ```bash
  brew install python@3.11
  ```
- **Windows/Linux:** Download from [python.org](https://www.python.org/downloads/)

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
# Or on macOS with Homebrew:
/opt/homebrew/bin/python3.11 -m venv venv
```

### 3. Activate Virtual Environment

- **macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** `pyrealsense2` is commented out in `requirements.txt` as it requires manual installation from source (v2.56.5). See [Intel RealSense Installation](#optional-intel-realsense-camera-support) below.

## Model Files

### RF-DETR Seg (Recommended - State-of-the-art, Nov 2025)

**No setup required!** The RF-DETR model downloads automatically on first run (~130MB).
- Stored in `data/models/`
- Best accuracy: 44.3 mAP@50:95
- Automatic GPU acceleration (Metal/CUDA/CPU)

### YOLOv11 (Fallback)

**No setup required!** Auto-downloads if RF-DETR unavailable (~6MB for nano model).

### Mask R-CNN (Legacy)

**No longer recommended.** The legacy Mask R-CNN is slower and less accurate than RF-DETR and YOLOv11. If you still need it:

#### 1. Create dnn Directory

```bash
mkdir dnn && cd dnn
```

#### 2. Download Model Files

```bash
# Download model archive
wget http://download.tensorflow.org/models/object_detection/mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
tar -xvf mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
mv mask_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb frozen_inference_graph_coco.pb

# Download config file
wget https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/mask_rcnn_inception_v2_coco_2018_01_28.pbtxt

# Download COCO classes
wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O classes.txt

# Clean up
rm mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
cd ..
```

#### 3. Verify Installation

```bash
ls dnn/
# Should show:
# - frozen_inference_graph_coco.pb
# - mask_rcnn_inception_v2_coco_2018_01_28.pbtxt
# - classes.txt
```

**Note:** These files are large (~200MB) and only required if using Mask R-CNN fallback.

## Optional: Intel RealSense Camera Support

For depth sensing capabilities, install RealSense SDK:

### macOS/Linux

Follow the official guide: [Intel RealSense Installation](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation.md)

After installing the SDK:
```bash
pip install pyrealsense2
```

### Windows

1. Download and install [Intel RealSense SDK 2.0](https://github.com/IntelRealSense/librealsense/releases)
2. Install Python wrapper:
   ```bash
   pip install pyrealsense2
   ```

**Note:** The application works without RealSense using standard webcams (no depth sensing).

## Application Packaging (Optional)

To build distributable applications for desktop, mobile, or web platforms, see [Application Builds](application-builds.md).

**Not needed for development** - You can run the app directly with `python main.py`.

## Optional: Zed Editor Integration

For Jupyter notebook support in Zed editor:

### 1. Register Jupyter Kernel

```bash
./venv/bin/python -m ipykernel install --user --name de-gui-venv --display-name "Python (DE-GUI venv)"
```

### 2. Configure Zed

- Open command palette (Cmd+Shift+P / Ctrl+Shift+P)
- Run: `repl: refresh kernelspecs`
- Select "Python (DE-GUI venv)" from kernel selector

## Configuration

After installation, configure your arm and settings:

```bash
# Interactive setup (recommended for first-time)
python scripts/setup_config.py

# Quick updates (change IP, speeds, etc.)
python scripts/update_config.py
```

See [README.md Configuration section](../README.md#configuration) for details.

## Verifying Installation

Test that everything is installed correctly:

```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -c "from aaa_core.config.settings import app_config; print('✓ Installation successful')"
```

You should see:
```
✓ RealSense camera support available  (or ✗ if not installed)
✓ Lite6 arm driver available  (or ✗ if not installed)
✓ RF-DETR Seg object detection available (SOTA Nov 2025, 44.3 mAP)
✓ Installation successful
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'mediapipe'"

Ensure you've activated the virtual environment and installed dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### RealSense camera not detected

- Ensure RealSense SDK is installed
- Install pyrealsense2: `pip install pyrealsense2`
- The app will fall back to webcam if RealSense is unavailable

### Camera enumeration warnings on macOS

The `AVCaptureDeviceTypeExternal` warning is harmless and can be ignored. Camera detection will still work correctly.

## Next Steps

Once installation is complete, see [README.md](../README.md) for usage instructions.
