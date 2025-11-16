# AAA Vision Package

Computer vision modules for the Access Ability Arm project.

## Features

- RF-DETR Segmentation (state-of-the-art, 44.3 mAP)
- YOLOv11 Segmentation (fast, accurate)
- Mask R-CNN (legacy fallback)
- MediaPipe Face Detection
- Detection Manager for orchestrating different detection modes

## Installation

From the repository root:

```bash
pip install -e packages/vision
```

## Usage

```python
from aaa_vision.rfdetr_seg import RFDETRSeg
from aaa_vision.detection_manager import DetectionManager

# Initialize detector
detector = RFDETRSeg()

# Process frame
boxes, classes, contours, centers = detector.detect_objects_mask(frame)
```
