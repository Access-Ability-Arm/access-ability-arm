# Model Files

This directory contains deep learning model weights for object detection and segmentation.

## Models

### YOLOv11 Segmentation Models
- `yolo11n-seg.pt` - Nano model (~6MB, fastest)
- `yolo11s-seg.pt` - Small model
- `yolo11m-seg.pt` - Medium model (~45MB)
- `yolo11l-seg.pt` - Large model (~56MB)
- `yolo11x-seg.pt` - Extra large model (~125MB, most accurate)

These models are auto-downloaded by Ultralytics on first use.

### RF-DETR Segmentation Models
RF-DETR models (e.g., `RFDETRSegPreview`) are automatically downloaded and cached by the Roboflow library on first use. They are stored in the Roboflow cache directory (typically `~/.cache/roboflow/` on Unix systems).

## Model Selection

The application automatically selects the best available model in this order:
1. RF-DETR Seg (state-of-the-art, 44.3 mAP, November 2025)
2. YOLOv11 Segmentation (fast, accurate)
3. Mask R-CNN (legacy fallback, requires manual download)

## Git Tracking

Model files (*.pt, *.pb) are excluded from git tracking via `.gitignore` to keep the repository size manageable.
