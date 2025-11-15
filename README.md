# DE-GUI
This will track the progress as the GUI for the Drane Engineering assistive arm is devloped

The goal for this is to leverage OpenCV and a RealSense camera to allow the user to pick out items in an image (on the GUI) and for the robot to be able to differentiate and pick up those items. Additionally, there will be basic controls (think up, down, left, right) on the GUI to allow the user to control the robot manually.

## Features

**Two Application Versions:**
- `main.py` - Face landmark tracking with standard webcam (works on MacBook, Windows, Linux)
- `main-rd.py` - Object detection with Intel RealSense camera (requires RealSense hardware + DNN models)

## Installation

### Setting Up the Virtual Environment

**Python Version Requirement:** This project requires **Python 3.11** (mediapipe does not support Python 3.14+).

1. **Install Python 3.11 (if not already installed):**
   - On macOS with Homebrew:
     ```bash
     brew install python@3.11
     ```
   - On Windows/Linux: Download from [python.org](https://www.python.org/downloads/)

2. **Create a virtual environment with Python 3.11:**
   ```bash
   python3.11 -m venv venv
   # Or on macOS with Homebrew:
   /opt/homebrew/bin/python3.11 -m venv venv
   ```

3. **Activate the virtual environment:**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Note:** `pyrealsense2` is commented out in `requirements.txt` as it requires manual installation from source (v2.56.5). Follow the [Intel RealSense installation guide](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation.md) for your platform.

### Required Model Files for Object Detection (main-rd.py only)

If you plan to use `main-rd.py` with object detection, you need to download the Mask R-CNN model files:

1. **Create the `dnn/` directory:**
   ```bash
   mkdir dnn
   ```

2. **Download the required files:**
   - `frozen_inference_graph_coco.pb` - Pre-trained Mask R-CNN model weights
   - `mask_rcnn_inception_v2_coco_2018_01_28.pbtxt` - Model configuration
   - `classes.txt` - COCO dataset class labels

   Download from the [TensorFlow Model Zoo](https://github.com/tensorflow/models/blob/master/research/object_detection/g3doc/tf1_detection_zoo.md):
   - Model: `mask_rcnn_inception_v2_coco`
   
   Or use these direct links:
   ```bash
   cd dnn
   # Download model archive
   wget http://download.tensorflow.org/models/object_detection/mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
   tar -xvf mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
   mv mask_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb frozen_inference_graph_coco.pb
   
   # Download config file
   wget https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/mask_rcnn_inception_v2_coco_2018_01_28.pbtxt
   
   # Download COCO classes
   wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O classes.txt
   ```

3. **Verify the files:**
   ```bash
   ls dnn/
   # Should show:
   # - frozen_inference_graph_coco.pb
   # - mask_rcnn_inception_v2_coco_2018_01_28.pbtxt
   # - classes.txt
   ```

**Note:** These model files are large (~200MB) and not included in the repository. They are only required for `main-rd.py` with object detection. `main.py` (face tracking) does not need these files.

### Configuring Zed Editor (Optional)

If you're using Zed editor with Jupyter notebook support:

1. **Register the venv as a Jupyter kernel:**
   ```bash
   ./venv/bin/python -m ipykernel install --user --name de-gui-venv --display-name "Python (DE-GUI venv)"
   ```

2. **In Zed:**
   - Open the command palette (Cmd+Shift+P)
   - Run: `repl: refresh kernelspecs`
   - Select "Python (DE-GUI venv)" from the kernel selector

## Running the Application

### Face Tracking Mode (Standard Webcam)
```bash
source venv/bin/activate  # Activate virtual environment
python main.py
```
- Works with MacBook FaceTime camera, external USB webcams, or Continuity Camera
- Tracks 20 facial landmarks around the mouth using MediaPipe
- No additional model files required

### Object Detection Mode (RealSense Camera)
```bash
source venv/bin/activate  # Activate virtual environment
python main-rd.py
```
- Requires Intel RealSense D400-series camera
- Requires DNN model files in `dnn/` directory (see installation section above)
- Provides object detection, segmentation, and depth measurement

### Troubleshooting

**Camera enumeration warnings on macOS:**
- The warning about `AVCaptureDeviceTypeExternal` is harmless and can be ignored
- Camera detection will still work correctly

**"OpenCV: out device of bound" errors:**
- These occur when the app searches for cameras beyond what's available
- Harmless - the app will use the available cameras (typically 0 and 1)

**macOS Continuity Camera:**
- If your iPhone appears as Camera 1, it's using Continuity Camera
- Select Camera 0 from the dropdown to use the built-in FaceTime camera

## About

If you are interested in becoming a part of this project, please check out Drane Engineering:

Link to Drane Engineering website: https://www.draneengineering.com/
