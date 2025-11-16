# AAA GUI Package

GUI implementations for the Access Ability Arm project.

## Features

- **Flet GUI**: Modern cross-platform web-based interface
- **PyQt6 GUI**: Traditional desktop Qt-based interface

Both GUIs provide:
- Real-time camera feed with object detection/segmentation
- Face landmark tracking
- Manual robotic arm controls (X, Y, Z, Grip)
- Camera selection
- Detection mode toggling

## Installation

### Flet GUI (recommended)
```bash
pip install -e "packages/gui[flet]"
```

### PyQt6 GUI
```bash
pip install -e "packages/gui[pyqt]"
```

### Both GUIs
```bash
pip install -e "packages/gui[all]"
```

## Usage

See main repository entry points (`main.py` for Flet, `main_pyqt.py` for PyQt6).
