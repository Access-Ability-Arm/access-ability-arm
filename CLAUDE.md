# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: API Documentation Verification

**BEFORE making ANY changes to third-party library APIs (Flet, PyQt, YOLO, etc.):**

1. **ALWAYS use Context7** to check the official API documentation
2. **Verify correct API syntax, parameter names, and capitalization**
3. **Never guess or assume API signatures** - incorrect APIs cause runtime errors

## Project Overview

Access Ability Arm is a Python monorepo application for the Drane Engineering assistive robotic arm.

**Key Technologies:**
- **RF-DETR Seg**: State-of-the-art segmentation (44.3 mAP, Nov 2025, ~130MB)
- **MediaPipe**: Face landmark tracking
- **Flet**: Cross-platform GUI (desktop + web)
- **RealSense**: Optional depth sensing
- **GPU**: Apple Metal, NVIDIA CUDA, or CPU

## Environment

**Python 3.11 required** (MediaPipe does not support 3.14+)

```bash
# Setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python main.py              # Desktop
python main.py --web        # Web browser
```

## Monorepo Structure

```
access-ability-arm/
├── packages/
│   ├── core/         # aaa-core: config, hardware, workers
│   ├── vision/       # aaa-vision: RF-DETR, face detection
│   ├── gui/          # aaa-gui: Flet interface
│   └── lite6_driver/ # aaa-lite6-driver: UFactory Lite6 arm
├── config/
│   ├── config.yaml.template  # Config template
│   └── config.yaml   # User config (git-ignored)
├── data/
│   └── models/       # Auto-downloaded model weights
├── scripts/
│   ├── setup_config.py   # Interactive config wizard
│   └── update_config.py  # Quick config updates
├── main.py           # Entry point
└── requirements.txt  # Installs all 4 packages
```

## Key Modules

**aaa_core:**
- `config.settings` - Configuration (loads from `config/config.yaml`)
- `hardware.camera_manager` - Camera enumeration
- `hardware.button_controller` - Button input (start once, not per press!)
- `workers.image_processor` - Camera processing thread
- `workers.daemon_image_processor` - Daemon-based processing (reads from socket)
- `workers.arm_controller_flet` - Flet arm controller (callbacks)
- `daemon.camera_daemon_socket` - RealSense daemon (runs with sudo)
- `daemon.camera_client_socket` - Client (connects to daemon via Unix socket)

**aaa_vision:**
- `rfdetr_seg` - RF-DETR (0.3 confidence threshold)
- `face_detector` - MediaPipe face mesh
- `detection_manager` - Mode orchestration

**aaa_gui:**
- `flet.main_window` - Material Design UI

**aaa_lite6_driver:**
- `lite6_arm` - UFactory Lite6 6-DOF arm control (xArm SDK)

## Camera Daemon Architecture (RealSense on macOS)

**Problem**: macOS Monterey+ requires `sudo` for RealSense USB access, but running GUI with `sudo` breaks Flet/PyQt.

**Solution**: Unix domain socket IPC for cross-user communication:

```
┌─────────────────────────────────────────┐
│  User Context (no sudo)                 │
│  ┌───────────────────────────────────┐  │
│  │  Flet GUI (main_window.py)        │  │
│  │  • Auto-detects daemon            │  │
│  │  • Fallback to webcam if no daemon│  │
│  └──────────┬────────────────────────┘  │
│             │                            │
│  ┌──────────▼────────────────────────┐  │
│  │  DaemonImageProcessor             │  │
│  │  • Reads from CameraClientSocket  │  │
│  │  • 30 fps processing              │  │
│  │  • Full detection support         │  │
│  └──────────┬────────────────────────┘  │
│             │                            │
│  ┌──────────▼────────────────────────┐  │
│  │  CameraClientSocket               │  │
│  │  • Connects to /tmp/aaa_camera.sock│ │
│  └──────────┬────────────────────────┘  │
└─────────────┼────────────────────────────┘
              │
      ═══════════════════
      ║  Unix Socket   ║
      ║  (mode 0666)   ║
      ═══════════════════
              │
┌─────────────┼────────────────────────────┐
│  Root Context (sudo)                     │
│  ┌──────────▼────────────────────────┐  │
│  │  CameraDaemonSocket               │  │
│  │  • Captures RealSense at 25-30fps │  │
│  │  • Broadcasts to all clients      │  │
│  │  • Frame format: header + RGB +   │  │
│  │    depth + metadata (JSON)        │  │
│  └──────────┬────────────────────────┘  │
│             │                            │
│  ┌──────────▼────────────────────────┐  │
│  │  RealsenseCamera                  │  │
│  │  • 1280×720 @ 30fps               │  │
│  │  • Aligned RGB + depth            │  │
│  └───────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Usage:**
```bash
# Start daemon (runs with sudo)
make daemon-start

# Run GUI (no sudo needed)
make run

# Or combined
make run-with-daemon

# Daemon management
make daemon-stop
make daemon-restart
make daemon-status
```

**Implementation Details:**
- Socket path: `/tmp/aaa_camera.sock` (permissions: 0666)
- Frame format: `[rgb_size: uint32][depth_size: uint32][metadata_size: uint32][rgb_data][depth_data][json_metadata]`
- Zero-copy within daemon, single copy on client receive (~2-3ms overhead)
- Multi-client support (daemon broadcasts to all connected GUIs)
- GUI auto-detects daemon by checking socket existence

**Why Unix Sockets (not shared memory)?**
- macOS POSIX shared memory doesn't support cross-user access
- Unix sockets work perfectly for root→user IPC
- Performance: 25-30 fps with <5ms latency (same as shared memory would be)

## Critical Implementation Notes

### RF-DETR Seg
- **DO NOT** call `model.optimize_for_inference()` - breaks mask output!
- **API**: Pass single PIL image: `predict(pil_image)` NOT `predict([pil_image])`
- **Class IDs**: 1-indexed dictionary `{1: 'person', 2: 'bicycle', ...}`
- **Model location**: Auto-downloads to `data/models/rf-detr-seg-preview.pt`
- **Confidence**: 0.3 (configurable in `packages/vision/src/aaa_vision/rfdetr_seg.py`)

### Button Controller
- **Start once** in `_setup_components()`, NOT on every button press
- Calling `start()` multiple times raises `RuntimeError: threads can only be started once`

### Model Paths
- RF-DETR models: `data/models/`
- All model loading uses project root detection (5 levels up from module files)

### Detection Modes
Press 'T' to cycle:
1. **Object Detection** (default): RF-DETR for 80 COCO classes
2. **Face Tracking**: MediaPipe 20 mouth landmarks
3. **Combined**: Both simultaneously

## Installation & Development

```bash
# Install packages
make install         # or: pip install -r requirements.txt

# Run application
make run             # Desktop
make web             # Web browser

# Code quality
make lint            # Check style
make format          # Format code
make clean           # Remove artifacts
```

## Common Issues

**Camera not detected:** Check system permissions, try different indices

**Model download fails:** Check internet, models auto-download to `data/models/`

**Import errors:** Verify venv activated, reinstall: `pip install -r requirements.txt`

**Button thread error:** Start thread once in setup, not per button press

**Slow performance:** Check GPU acceleration in console, switch to face tracking mode

## Configuration

Use interactive scripts (no manual editing required):
```bash
python scripts/setup_config.py    # First-time setup wizard
python scripts/update_config.py   # Quick updates (IP, speeds, etc.)
```

## Documentation

- [README.md](README.md) - Quick start
- [docs/installation.md](docs/installation.md) - Detailed setup
- [docs/monorepo.md](docs/monorepo.md) - Architecture details
- [docs/ufactory_studio.md](docs/ufactory_studio.md) - Lite6 arm setup

## Platform Notes

- **macOS**: Metal GPU auto-enabled on M-series, Continuity Camera supported
- **Windows**: CUDA GPU auto-enabled on NVIDIA cards
- **Linux**: V4L2 camera access
