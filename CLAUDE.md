# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Access Ability Arm is a Python monorepo for an assistive robotic arm (UFactory Lite6) that uses computer vision to help ALS patients interact with objects.

**Current Focus**: Implementing grasp planning with Open3D + AnyGrasp/GraspNet. See [docs/grasp_planning_report.md](docs/grasp_planning_report.md).

**Key Technologies**: RF-DETR Seg (segmentation), MediaPipe (face tracking), Flet (GUI), RealSense D435 (depth), xArm SDK (robot control)

## Quick Start

```bash
# Python 3.11 required (MediaPipe constraint)
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python main.py              # Desktop (webcam)
python main.py --web        # Web browser
make run-with-daemon        # RealSense depth (macOS, requires sudo)
```

## Monorepo Structure

```
packages/
├── core/         # aaa-core: config, hardware, workers, daemon
├── vision/       # aaa-vision: RF-DETR, face detection
├── gui/          # aaa-gui: Flet interface
└── lite6_driver/ # aaa-lite6-driver: UFactory Lite6 arm
```

## Critical Implementation Notes

### RF-DETR Seg
- **DO NOT** call `model.optimize_for_inference()` - breaks mask output
- **API**: `predict(pil_image)` takes single PIL image, NOT a list
- **Class IDs**: 1-indexed `{1: 'person', 2: 'bicycle', ...}`
- **Confidence**: 0.3 threshold (in `packages/vision/src/aaa_vision/rfdetr_seg.py`)

### Button Controller
- **Start once** in `_setup_components()`, NOT on every button press
- Multiple `start()` calls raise `RuntimeError: threads can only be started once`

### RealSense Camera
- RGB: 1920×1080 @ 30fps, Depth: 848×480 @ 30fps
- macOS requires daemon for depth (sudo USB access issue)
- Visual presets: Default, High Accuracy, Medium Density, High Density
- See [docs/hardware/realsense-d435-specs.md](docs/hardware/realsense-d435-specs.md)

## Camera Daemon (macOS RealSense Only)

macOS requires `sudo` for RealSense USB, but GUI breaks with sudo. Solution: daemon with Unix socket IPC.

```bash
make daemon-start      # Start daemon (sudo)
make run               # Run GUI (no sudo) - auto-detects daemon
make daemon-stop       # Stop daemon
```

Socket: `/tmp/aaa_camera.sock` | Format: `[sizes][rgb][depth][json_metadata]`

Full architecture: [docs/archive/decisions/daemon-architecture-implementation-plan.md](docs/archive/decisions/daemon-architecture-implementation-plan.md)

## Key Modules

| Module | Path | Purpose |
|--------|------|---------|
| Settings | `aaa_core.config.settings` | Loads `config/config.yaml` |
| Camera Manager | `aaa_core.hardware.camera_manager` | Camera enumeration |
| Image Processor | `aaa_core.workers.image_processor` | Camera processing thread |
| Daemon Processor | `aaa_core.workers.daemon_image_processor` | Reads from daemon socket |
| RF-DETR | `aaa_vision.rfdetr_seg` | Object segmentation |
| Face Detector | `aaa_vision.face_detector` | MediaPipe face mesh |
| Main Window | `aaa_gui.flet.main_window` | Flet GUI |
| Lite6 Arm | `aaa_lite6_driver.lite6_arm` | Robot control (xArm SDK) |

## Detection Modes

Press **T** to cycle:
1. **Object Detection**: RF-DETR for 80 COCO classes
2. **Face Tracking**: MediaPipe mouth landmarks
3. **Combined**: Both simultaneously

## Common Commands

```bash
make install         # Install packages
make run             # Desktop app
make web             # Web app (localhost:8550)
make lint            # Check style
make format          # Format code

# Config
python scripts/setup_config.py    # First-time wizard
python scripts/update_config.py   # Quick updates
```

## Documentation

- [docs/README.md](docs/README.md) - Documentation index
- [docs/installation.md](docs/installation.md) - Setup guide
- [docs/grasp_planning_report.md](docs/grasp_planning_report.md) - Current project plan
- [docs/hardware/](docs/hardware/) - RealSense, sensors, platforms
- [docs/research/](docs/research/) - Exploration and analysis

## API Documentation

Before modifying third-party library calls (Flet, PyRealsense2, xArm SDK), verify the API using Context7 or official docs. Incorrect APIs cause runtime errors.
