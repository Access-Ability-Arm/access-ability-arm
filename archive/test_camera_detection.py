#!/usr/bin/env python3
"""Test script to verify camera detection and module availability"""

import sys

# Test imports
print("=== Testing Module Imports ===")

# Test RealSense
try:
    from realsense_camera import RealsenseCamera

    print("✓ RealSense module available")
    REALSENSE_AVAILABLE = True
except ImportError as e:
    print(f"✗ RealSense not available: {e}")
    REALSENSE_AVAILABLE = False

# Test Mask R-CNN
try:
    from mask_rcnn import MaskRCNN

    print("✓ Mask R-CNN module available")
    MASK_RCNN_AVAILABLE = True
except ImportError as e:
    print(f"✗ Mask R-CNN not available: {e}")
    MASK_RCNN_AVAILABLE = False

# Test MediaPipe
try:
    import mediapipe as mp

    print("✓ MediaPipe available")
except ImportError as e:
    print(f"✗ MediaPipe not available: {e}")
    sys.exit(1)

# Test OpenCV
try:
    import cv2

    print("✓ OpenCV available")

    # Test camera access
    camera = cv2.VideoCapture(0)
    if camera.isOpened():
        ret, frame = camera.read()
        if ret:
            print(
                f"✓ Webcam accessible (resolution: {frame.shape[1]}x{frame.shape[0]})"
            )
        else:
            print("✗ Webcam opened but failed to read frame")
        camera.release()
    else:
        print("✗ Could not open webcam")
except Exception as e:
    print(f"✗ OpenCV error: {e}")

print("\n=== Summary ===")
print(
    f"RealSense: {'Available' if REALSENSE_AVAILABLE else 'Not Available (will use webcam)'}"
)
print(
    f"Mask R-CNN: {'Available' if MASK_RCNN_AVAILABLE else 'Not Available (face tracking only)'}"
)
print(
    f"Recommended mode: {'Object Detection' if MASK_RCNN_AVAILABLE else 'Face Tracking'}"
)
print(
    f"Camera type: {'RealSense (with depth)' if REALSENSE_AVAILABLE else 'Standard Webcam (no depth)'}"
)
