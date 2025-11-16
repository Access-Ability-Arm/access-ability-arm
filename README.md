# Access Ability Arm

AI-powered GUI for the Drane Engineering assistive robotic arm, featuring real-time object detection, face tracking, and depth sensing.

## Features

- **RF-DETR Seg Object Detection**: State-of-the-art real-time segmentation (44.3 mAP, Nov 2025)
- **GPU Acceleration**: Automatic support for Apple Metal, NVIDIA CUDA, or CPU
- **Face Tracking**: Multi-region facial landmark detection with MediaPipe
- **Depth Sensing**: Intel RealSense support for distance measurement (optional)
- **Flexible Camera Support**: Auto-detects RealSense, webcams, or Continuity Camera
- **Manual Controls**: Direct robotic arm control (x, y, z, grip)
- **Toggle Modes**: Press 'T' to cycle between face tracking, object detection, and combined modes
- **Monorepo Architecture**: Clean package structure for maintainability and reusability

## Quick Start

### Installation

See [docs/installation.md](docs/installation.md) for detailed setup instructions.

**Quick version:**
```bash
# Create virtual environment with Python 3.11
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install all packages (monorepo)
pip install -r requirements.txt

# Or use Makefile
make install
```

### Running the Application

**Flet GUI (Modern Cross-Platform):**
```bash
source venv/bin/activate  # Activate virtual environment
python main.py

# Or run as web app
python main.py --web --port 8550

# Or use Makefile
make run      # Desktop
make web      # Web browser
```

The application will automatically:
- Detect available cameras (RealSense → webcam → Continuity Camera)
- Enable GPU acceleration (Apple Metal, CUDA, or CPU)
- Download RF-DETR Seg model on first run (~130MB, stored in `data/models/`)

### Controls

- **Camera Selection**: Choose camera from dropdown menu
- **Detection Mode**: Press 'T' to cycle through modes (Object → Combined → Face → Object...)
- **Robotic Arm**: Use GUI buttons for manual control (x±, y±, z±, grip)

### Configuration

**Interactive Setup (Recommended):**
```bash
python scripts/setup_config.py
```

This will guide you through setting:
- Lite6 arm IP address and connection settings
- Camera preferences
- Detection thresholds
- Movement step sizes and speeds
- Display dimensions

**Manual Configuration:**
```bash
# Copy template and edit
cp config.yaml.template config.yaml
# Edit config.yaml with your settings
```

The application uses RF-DETR Seg for object detection with automatic fallback support for YOLOv11-seg and Mask R-CNN. All settings can be customized in `config.yaml` without modifying code.

## System Requirements

- **Python**: 3.11 (required - MediaPipe does not support 3.14+)
- **Camera**: Any webcam, or Intel RealSense D400-series for depth sensing
- **OS**: macOS, Windows, or Linux
- **GPU** (optional): Apple Silicon (Metal), NVIDIA (CUDA), or CPU

## Detection Modes

Press **'T'** to cycle through detection modes:

### 1. Object Detection (Default)
- RF-DETR Seg instance segmentation for 80 COCO object classes
- Real-time colored segmentation masks with labels (no bounding boxes)
- State-of-the-art accuracy (44.3 mAP@50:95, Nov 2025)
- Consistent colors per object class
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

## Monorepo Architecture

The codebase is organized as a Python monorepo with three separate packages:

```
access-ability-arm/
├── packages/
│   ├── core/           # aaa-core: Config, hardware, workers
│   ├── vision/         # aaa-vision: RF-DETR, YOLO, face detection
│   └── gui/            # aaa-gui: Flet interface
├── data/
│   ├── models/         # Model weights (RF-DETR, YOLO)
│   └── dnn/            # Legacy Mask R-CNN models
├── docs/               # Documentation
├── main.py             # Flet GUI entry point
└── requirements.txt    # Package installation
```

### Packages

**aaa-core** (`packages/core/`)
- Application configuration and feature detection
- Camera management and enumeration
- Button controllers and hardware interfaces
- RealSense camera support (optional)
- Image processing workers

**aaa-vision** (`packages/vision/`)
- RF-DETR Seg segmentation (state-of-the-art)
- YOLOv11 segmentation (fast, accurate)
- Mask R-CNN (legacy fallback)
- MediaPipe face detection
- Detection mode orchestration

**aaa-gui** (`packages/gui/`)
- Modern Flet cross-platform interface
- Desktop, web, and mobile support
- Material Design UI
- Responsive layout

See [docs/monorepo.md](docs/monorepo.md) for detailed architecture information.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Monorepo Guide](docs/monorepo.md) - Package architecture and structure
- [Refactoring Guide](docs/refactoring.md) - Code organization details
- [CLAUDE.md](CLAUDE.md) - Developer reference for AI assistants

## Development

### Makefile Commands

```bash
make help            # Show all commands
make install         # Install monorepo packages
make run             # Run desktop application
make web             # Run web application
make clean           # Remove build artifacts
make lint            # Check code style
make format          # Format code
make info            # Show project information
```

### Package Installation

```bash
# Install all packages
pip install -r requirements.txt

# Or install individually
pip install -e packages/core
pip install -e packages/vision
pip install -e "packages/gui[flet]"
```

## Troubleshooting

**Camera not found:**
- Check camera permissions in system settings
- Try different camera indices in dropdown

**Slow performance:**
- Ensure GPU acceleration is enabled (check console output)
- Try switching to face tracking mode (lighter processing)

**Import errors:**
- Verify virtual environment is activated
- Reinstall packages: `pip install -r requirements.txt`

**Model files:**
- RF-DETR and YOLO models auto-download to `data/models/`
- Mask R-CNN requires manual download to `data/dnn/` (see CLAUDE.md)

For more help, see [docs/installation.md](docs/installation.md#troubleshooting).

## About

Developed for Drane Engineering's assistive robotic arm project.

**Website**: [draneengineering.com](https://www.draneengineering.com/)

## License

See [LICENSE.txt](LICENSE.txt) for details.
