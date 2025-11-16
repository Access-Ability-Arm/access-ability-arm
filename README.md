# Access Ability Arm

AI-powered GUI for the Drane Engineering assistive robotic arm, featuring real-time object detection, face tracking, and depth sensing.

## Features

- **UFactory Lite6 Integration**: Direct control of UFactory Lite6 collaborative robotic arm
- **RF-DETR Seg Object Detection**: State-of-the-art real-time segmentation (44.3 mAP, Nov 2025)
- **GPU Acceleration**: Automatic support for Apple Metal, NVIDIA CUDA, or CPU
- **Face Tracking**: Multi-region facial landmark detection with MediaPipe
- **Depth Sensing**: Intel RealSense support for distance measurement (optional)
- **Flexible Camera Support**: Auto-detects RealSense, webcams, or Continuity Camera
- **Manual Controls**: Direct robotic arm control (x, y, z, grip)
- **Toggle Modes**: Press 'T' to cycle between face tracking, object detection, and combined modes
- **Easy Configuration**: Interactive setup for arm IP, speeds, and all settings
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

### UFactory Lite6 Setup

Before using the arm with this application, you need to:

1. **Install UFactory Studio** to find your arm's IP address
2. **Configure the arm** (home position, safety settings)
3. **Find the IP address** for the Access Ability Arm configuration

See [docs/ufactory_studio.md](docs/ufactory_studio.md) for detailed setup instructions.

### Configuration

All settings can be customized in `config/config.yaml` without modifying code.

**First-Time Setup (Recommended):**
```bash
python scripts/setup_config.py
```

Interactive wizard that guides you through:
- Lite6 arm IP address and connection settings (with connection testing)
- Camera preferences
- Detection thresholds
- Movement step sizes and speeds
- Display dimensions

**Quick Updates (When IP changes, etc.):**
```bash
python scripts/update_config.py
```

Interactive menu for common changes:
1. **Arm IP address** - Change IP and test connection before saving
2. **Default camera** - Switch which camera is used on startup
3. **Movement speeds** - Adjust tap/hold step sizes, arm speed, gripper speed
4. **Detection threshold** - Fine-tune object detection sensitivity
5. **View configuration** - See all current settings
6. **Run full setup** - Launch the complete setup wizard

No manual file editing required!

**Manual Configuration (Advanced):**
```bash
# Copy template and edit
cp config/config.yaml.template config/config.yaml
# Edit config/config.yaml with your preferred text editor
```

The application uses RF-DETR Seg for object detection with automatic fallback support for YOLOv11-seg and Mask R-CNN.

## System Requirements

- **Python**: 3.11 (required - MediaPipe does not support 3.14+)
- **Camera**: Any webcam (RealSense optional but complex on macOS - see below)
- **OS**: macOS, Windows, or Linux
- **GPU** (optional): Apple Silicon (Metal), NVIDIA (CUDA), or CPU

### Intel RealSense Support (Optional)

**⚠️ Important for macOS Users:**

RealSense depth cameras provide enhanced 3D sensing but require significant setup on macOS:
- ❌ Must build librealsense from source (2+ hours)
- ❌ Specific USB cable required (original Intel cable or Thunderbolt 3/4)
- ❌ Firmware slow-insertion bug causes USB 2.0 fallback with most cables

**Solution: Camera Daemon Architecture**
- ✅ Daemon runs with `sudo` to access RealSense
- ✅ GUI runs as regular user (no sudo needed!)
- ✅ Frames streamed via Unix socket (zero-copy IPC)
- ✅ Full depth data + object detection at 25-30 fps

**Usage:**
```bash
# Start RealSense daemon (runs with sudo)
make daemon-start

# Run GUI (no sudo needed!)
make run

# Or combined
make run-with-daemon
```

**The app works great with regular webcams!** Only install RealSense if you specifically need depth sensing.

📖 See [docs/realsense-setup.md](docs/realsense-setup.md) for complete installation guide

## Monorepo Architecture

The codebase is organized as a Python monorepo with four separate packages:

```
access-ability-arm/
├── packages/
│   ├── core/           # aaa-core: Config, hardware, workers
│   ├── vision/         # aaa-vision: RF-DETR, YOLO, face detection
│   ├── gui/            # aaa-gui: Flet & PyQt6 interfaces
│   └── lite6_driver/   # aaa-lite6-driver: UFactory Lite6 arm control
├── config/
│   ├── config.yaml.template  # Configuration template
│   └── config.yaml     # User config (git-ignored)
├── data/
│   ├── models/         # Model weights (RF-DETR, YOLO)
│   └── dnn/            # Legacy Mask R-CNN models
├── scripts/            # Setup and configuration scripts
├── docs/               # Documentation
├── main.py             # Flet GUI entry point
└── requirements.txt    # Package installation
```

### Packages

**aaa-core** (`packages/core/`)
- Application configuration and feature detection (loads from `config/config.yaml`)
- Camera management and enumeration
- Button controllers and hardware interfaces
- RealSense camera support (optional)
- Image processing workers
- Arm controller workers (PyQt6 and Flet variants)

**aaa-vision** (`packages/vision/`)
- RF-DETR Seg segmentation (state-of-the-art, 44.3 mAP)
- YOLOv11 segmentation (fast, accurate fallback)
- Mask R-CNN (legacy fallback)
- MediaPipe face detection with landmark tracking
- Detection mode orchestration and management

**aaa-gui** (`packages/gui/`)
- Modern Flet cross-platform interface (desktop, web, mobile)
- Traditional PyQt6 desktop interface
- Material Design UI
- Responsive layout
- Arm control integration

**aaa-lite6-driver** (`packages/lite6_driver/`)
- UFactory Lite6 robotic arm driver using xArm Python SDK
- 6-DOF position control (x, y, z, roll, pitch, yaw)
- Gripper control (open, close, set position)
- Safety features (home, emergency stop)
- Context manager support

See [docs/monorepo.md](docs/monorepo.md) for detailed architecture information.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Monorepo Guide](docs/monorepo.md) - Package architecture and structure
- [UFactory Studio Setup](docs/ufactory_studio.md) - Lite6 arm setup and configuration
- [Application Builds](docs/application-builds.md) - Packaging for distribution
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
