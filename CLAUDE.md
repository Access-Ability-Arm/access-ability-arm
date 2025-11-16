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
│   ├── core/        # aaa-core: config, hardware, workers
│   ├── vision/      # aaa-vision: RF-DETR, face detection
│   └── gui/         # aaa-gui: Flet interface
├── data/
│   └── models/      # Auto-downloaded model weights
├── main.py          # Entry point
└── requirements.txt # Installs all 3 packages
```

## Key Modules

**aaa_core:**
- `config.settings` - Configuration & feature detection
- `hardware.camera_manager` - Camera enumeration
- `hardware.button_controller` - Button input (start once, not per press!)
- `workers.image_processor` - Camera processing thread

**aaa_vision:**
- `rfdetr_seg` - RF-DETR (0.3 confidence threshold)
- `face_detector` - MediaPipe face mesh
- `detection_manager` - Mode orchestration

**aaa_gui:**
- `flet.main_window` - Material Design UI

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

## Documentation

- [README.md](README.md) - Quick start
- [docs/installation.md](docs/installation.md) - Detailed setup
- [docs/monorepo.md](docs/monorepo.md) - Architecture details

## Platform Notes

- **macOS**: Metal GPU auto-enabled on M-series, Continuity Camera supported
- **Windows**: CUDA GPU auto-enabled on NVIDIA cards
- **Linux**: V4L2 camera access
