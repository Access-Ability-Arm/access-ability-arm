# Installation Guide

## Requirements

**Python Version:** This project requires **Python 3.11** (MediaPipe does not support Python 3.14+).

**Disk Space:** ~500MB (Python packages + RF-DETR model)

**Hardware:**
- **UFactory Lite6 robotic arm** (optional - app works without arm)
- **Waveshare SC Servo Gripper** (optional - replaces Lite6 built-in gripper)
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

For depth sensing capabilities with RealSense cameras, see the comprehensive setup guide:

**📖 [RealSense Setup Guide](realsense-setup.md)**

This guide covers:
- Building librealsense from source on macOS
- Installing Python bindings
- Updating camera firmware
- macOS-specific USB permission issues
- Troubleshooting and testing

**Quick Summary:**
- ⚠️ **macOS requires building from source** (~2 hours, no pre-built packages)
- ⚠️ **Requires `sudo` for all camera operations** (macOS Monterey+ limitation)
- ⚠️ **Specific USB cable required** - Original Intel cable or Thunderbolt 3/4 only
- ⚠️ **Firmware bug causes USB 2.0 fallback** with most generic cables
- ✅ Firmware update recommended (5.17.0.10+)
- ✅ Test script included: `scripts/test_realsense.py`

**Note:** The application works perfectly with standard webcams (no RealSense needed for basic operation).

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

## UFactory Lite6 Arm Setup

### Option 1: Physical Arm

For setup with a real UFactory Lite6 arm, see [UFactory Studio Setup Guide](ufactory_studio.md) for:
- Installing UFactory Studio
- Finding your arm's IP address
- Initial configuration and homing

### Option 2: Docker Simulation (UFSim)

**No physical arm needed!** Run a simulated Lite6 in Docker on macOS, Linux, or Windows.

**Requirements:**
- Docker Desktop ([docker.com](https://www.docker.com/products/docker-desktop/))
- **Alternative for macOS:** [UTM](https://mac.getutm.app/) can run Linux VMs with Docker if you prefer a VM-based approach

**Setup:**
```bash
# Pull the simulation image
docker pull danielwang123321/uf-ubuntu-docker

# Run the simulation (all platforms: macOS/Linux/Windows)
docker run -it --name uf_software -p 18333:18333 -p 502:502 -p 503:503 -p 504:504 -p 30000:30000 -p 30001:30001 -p 30002:30002 -p 30003:30003 danielwang123321/uf-ubuntu-docker

# Inside the container, start Lite6 simulation
/xarm_scripts/xarm_start.sh 6 9

# Access 3D visualization in browser: http://localhost:18333
```

**Configure for simulation:**
```bash
# Set arm IP to localhost
python scripts/update_config.py
# Select option 1: Update arm IP address
# Enter: 127.0.0.1
```

**Note for Apple Silicon Macs:** You may see a platform warning (linux/amd64 vs arm64) - this is normal and the simulation will work correctly via Rosetta 2 emulation.

## Optional: Waveshare SC Servo Gripper

The project includes a driver for Waveshare SC series servos (SC09/SC15) connected via the Bus Servo Adapter (A). This provides an alternative gripper with force control capabilities.

**Hardware Required:**
- [Waveshare Bus Servo Adapter (A)](https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A))
- SC series servo (SC09, SC15, etc.)
- USB cable (adapter to computer)
- External 6-8V power supply for the servo

**Setup:**

The gripper driver package is included and installed automatically with `pip install -r requirements.txt`.

**Testing the Connection:**

```bash
source venv/bin/activate

# Find your serial port
ls /dev/cu.usbserial-* 2>/dev/null  # macOS
ls /dev/ttyUSB* 2>/dev/null          # Linux

# Test connection (replace XXX with your port)
python packages/gripper_driver/examples/test_connection.py --port /dev/cu.usbserial-XXX

# Interactive testing and calibration
python packages/gripper_driver/examples/interactive.py --port /dev/cu.usbserial-XXX
```

**Available Test Scripts:**
- `test_connection.py` - Verify servo communication
- `test_positions.py` - Test preset positions (open, close, etc.)
- `test_force.py` - Test grip force levels
- `test_modes.py` - Test point and push modes
- `interactive.py` - Interactive CLI for manual testing and calibration

See [Gripper Integration Plan](gripper_integration_plan.md) for detailed documentation.

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
✓ SC Servo gripper driver available
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

See the [RealSense Setup Guide](realsense-setup.md#troubleshooting) for detailed troubleshooting.

Quick checks:
- On macOS: Use `sudo` to run RealSense applications
- Verify camera is detected: `system_profiler SPUSBDataType | grep -i realsense`
- The app will fall back to webcam if RealSense is unavailable

### Camera enumeration warnings on macOS

The `AVCaptureDeviceTypeExternal` warning is harmless and can be ignored. Camera detection will still work correctly.

## Next Steps

Once installation is complete, see [README.md](../README.md) for usage instructions.
