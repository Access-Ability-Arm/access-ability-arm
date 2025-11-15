# Access Ability Arm

AI-powered GUI for the Drane Engineering assistive robotic arm, featuring real-time object detection, face tracking, and depth sensing.

## Features

- **YOLOv11 Object Detection**: Real-time segmentation with Apple Metal GPU acceleration
- **Face Tracking**: 20-point facial landmark detection with MediaPipe
- **Depth Sensing**: Intel RealSense support for distance measurement (optional)
- **Flexible Camera Support**: Auto-detects RealSense, webcams, or Continuity Camera
- **Manual Controls**: Direct robotic arm control (x, y, z, grip)
- **Toggle Modes**: Press 'T' to switch between face tracking and object detection

## Quick Start

### Installation

See [docs/installation.md](docs/installation.md) for detailed setup instructions.

**Quick version:**
```bash
# Create virtual environment with Python 3.11
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

**Default (Flet - Modern Cross-Platform):**
```bash
source venv/bin/activate  # Activate virtual environment
python main.py
# Or run as web app: python main.py --web
```

**Legacy PyQt6 Version (To Be Deprecated):**
```bash
source venv/bin/activate  # Activate virtual environment
python main_pyqt.py
```

The application will automatically:
- Detect available cameras (RealSense → webcam → Continuity Camera)
- Enable GPU acceleration (Apple Metal, CUDA, or CPU)
- Download YOLOv11-medium model on first run (~50MB)

> **Note**: The default Flet version offers a modern Material Design UI and can run in web browsers. The PyQt version is maintained for compatibility but will be removed in a future release. See [flet_gui/README.md](flet_gui/README.md) for details.

### Controls

- **Camera Selection**: Choose camera from dropdown menu
- **Detection Mode**: Press 'T' to cycle through modes (Object → Combined → Face → Object...)
- **Robotic Arm**: Use GUI buttons for manual control (x±, y±, z±, grip)

### Configuration

You can customize the YOLO model size in `config/settings.py`:
```python
yolo_model_size: str = "m"  # Options: 'n' (nano, ~6MB), 's' (small, ~24MB), 
                             #          'm' (medium, ~50MB, default), 
                             #          'l' (large, ~65MB), 'x' (xlarge, ~140MB)
```
- **Nano (n)**: Fastest, good accuracy, real-time on mobile
- **Small (s)**: Very fast, better accuracy
- **Medium (m)**: Great accuracy, real-time on desktop (default)
- **Large (l)**: Excellent accuracy
- **XLarge (x)**: Best accuracy, slower

## System Requirements

- **Python**: 3.11 (required - MediaPipe does not support 3.14+)
- **Camera**: Any webcam, or Intel RealSense D400-series for depth sensing
- **OS**: macOS, Windows, or Linux
- **GPU** (optional): Apple Silicon (Metal), NVIDIA (CUDA), or CPU

## Detection Modes

Press **'T'** to cycle through detection modes:

### 1. Object Detection (Default)
- YOLOv11 instance segmentation for 80 COCO object classes
- Real-time colored segmentation masks with labels
- Confidence scores with temporal smoothing
- Distance measurement with RealSense camera (optional)
- Fixed reference point depth indicator

### 2. Face Tracking
- MediaPipe face mesh with multiple landmark groups
- Mouth (20 points), eyes, eyebrows, nose, ears
- Color-coded visualization for each feature
- Center point calculation
- Works with any standard webcam

### 3. Combined Mode (Face + Objects)
- Simultaneous object detection and face tracking
- Segmentation masks for all objects (including persons)
- Face landmarks overlaid on detected persons
- Best for complex assistive tasks requiring both awareness types
- Runs both models concurrently (~25-33 FPS on Apple Silicon)

## GUI Options

Two GUI implementations are available:

| Feature | PyQt6 | Flet |
|---------|-------|------|
| **Interface** | Traditional desktop | Modern Material Design |
| **Platforms** | Desktop only | Desktop + Web + Mobile* |
| **Entry Point** | `main.py` | `main_flet.py` |
| **UI Definition** | Qt Designer (.ui file) | Python code |
| **Web Support** | ✗ | ✓ |

*Mobile support planned for future releases

## Architecture

The application uses a modular architecture for maintainability:

```
access-ability-arm/
├── config/       # Configuration & feature detection
├── gui/          # PyQt6 main window & UI
├── flet_gui/     # Flet alternative GUI
├── hardware/     # Camera & button controllers
├── vision/       # Computer vision (YOLO, face detection)
├── workers/      # Image processing thread
├── main.py       # PyQt6 entry point
└── main_flet.py  # Flet entry point
```

See [docs/refactoring.md](docs/refactoring.md) for architecture details.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Refactoring Guide](docs/refactoring.md) - Architecture and code organization
- [CLAUDE.md](CLAUDE.md) - Developer reference for AI assistants

## Troubleshooting

**Camera not found:**
- Check camera permissions in system settings
- Try different camera indices in dropdown

**Slow performance:**
- Ensure GPU acceleration is enabled (check console output)
- Try switching to face tracking mode (lighter processing)

**Import errors:**
- Verify virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

For more help, see [docs/installation.md](docs/installation.md#troubleshooting).

## About

Developed for Drane Engineering's assistive robotic arm project.

**Website**: [draneengineering.com](https://www.draneengineering.com/)

## License

See [LICENSE.txt](LICENSE.txt) for details.
