# DE-GUI
This will track the progress as the GUI for the Drane Engineering assistive arm is devloped

The goal for this is to leverage OpenCV and a RealSense camera to allow the user to pick out items in an image (on the GUI) and for the robot to be able to differentiate and pick up those items. Additionally, there will be basic controls (think up, down, left, right) on the GUI to allow the user to control the robot manually.

## Installation

### Setting Up the Virtual Environment

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Note:** `pyrealsense2` is commented out in `requirements.txt` as it requires manual installation from source (v2.56.5). Follow the [Intel RealSense installation guide](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation.md) for your platform.

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

## About

If you are interested in becoming a part of this project, please check out Drane Engineering:

Link to Drane Engineering website: https://www.draneengineering.com/
