"""
Face Landmark Detection
Uses MediaPipe to track facial landmarks, specifically mouth points
"""

import os
import sys
from contextlib import contextmanager

import cv2
import numpy as np

from config.console import status

# Suppress TensorFlow Lite warnings from MediaPipe
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'
os.environ['GLOG_logtostderr'] = '0'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# Suppress ABSL warnings (includes feedback manager warnings from inference_feedback_manager.cc)
os.environ['ABSL_MINLOGLEVEL'] = '2'  # 0=INFO, 1=WARNING, 2=ERROR - suppress INFO and WARNING


@contextmanager
def suppress_output():
    """Suppress all output including system-level warnings"""
    # Save original file descriptors
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save copies of the original file descriptors
    with os.fdopen(os.dup(stdout_fd), 'w') as stdout_copy, \
         os.fdopen(os.dup(stderr_fd), 'w') as stderr_copy:

        # Redirect stdout and stderr to devnull
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stdout_fd)
            os.dup2(devnull, stderr_fd)
            yield
        finally:
            # Restore original file descriptors
            os.dup2(stdout_copy.fileno(), stdout_fd)
            os.dup2(stderr_copy.fileno(), stderr_fd)
            os.close(devnull)


# MediaPipe import is fine - warnings come from first .process() call, not import
import mediapipe as mp


class FaceDetector:
    """Detects and tracks facial landmarks using MediaPipe"""

    # Facial landmark indices from MediaPipe face mesh
    # Reference: https://raw.githubusercontent.com/google/mediapipe/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png

    # Mouth landmarks
    MOUTH_POINTS = [
        78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
        308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
    ]

    # Left eye landmarks
    LEFT_EYE_POINTS = [
        33, 160, 158, 133, 153, 144, 163, 7,
    ]

    # Right eye landmarks
    RIGHT_EYE_POINTS = [
        263, 387, 385, 362, 380, 373, 390, 249,
    ]

    # Left eyebrow landmarks
    LEFT_EYEBROW_POINTS = [
        70, 63, 105, 66, 107,
    ]

    # Right eyebrow landmarks
    RIGHT_EYEBROW_POINTS = [
        300, 293, 334, 296, 336,
    ]

    # Nose landmarks
    NOSE_POINTS = [
        1, 2, 98, 327, 129, 358, 19, 195, 5,
    ]

    # Left ear landmarks (approximate, face mesh doesn't have specific ear points)
    LEFT_EAR_POINTS = [
        234, 127, 162,
    ]

    # Right ear landmarks (approximate)
    RIGHT_EAR_POINTS = [
        454, 356, 389,
    ]

    def __init__(self):
        """Initialize MediaPipe face mesh"""
        # Suppress TensorFlow Lite feedback manager warnings during initialization
        # Warnings can occur when accessing mp.solutions.face_mesh or creating FaceMesh()
        with suppress_output():
            self.mp_mesh = mp.solutions.face_mesh
            self.mesh = self.mp_mesh.FaceMesh()
        self.mp_draw = mp.solutions.drawing_utils
        status("Face detector initialized")

    def detect_and_draw(self, image: np.ndarray) -> np.ndarray:
        """
        Detect face landmarks and draw them on the image

        Args:
            image: RGB image array

        Returns:
            Image with landmarks drawn
        """
        # Suppress TensorFlow Lite feedback manager warnings during processing
        with suppress_output():
            results = self.mesh.process(image)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                h, w, c = image.shape
                tx = 0
                ty = 0

                for id, lm in enumerate(face_landmarks.landmark):
                    px, py = int(lm.x * w), int(lm.y * h)

                    # Draw mouth points (green)
                    if id in self.MOUTH_POINTS:
                        # Calculate center point from landmarks 13 and 14
                        if id in [13, 14]:
                            tx += px
                            ty += py

                        if id == 14:
                            # Draw center of mouth (yellow)
                            tx = int(tx / 2)
                            ty = int(ty / 2)
                            cv2.circle(image, (tx, ty), 10, (0, 255, 255), cv2.FILLED)

                        # Draw individual mouth points
                        cv2.circle(image, (px, py), 4, (0, 255, 0), cv2.FILLED)

                    # Draw left eye (blue)
                    elif id in self.LEFT_EYE_POINTS:
                        cv2.circle(image, (px, py), 3, (255, 0, 0), cv2.FILLED)

                    # Draw right eye (cyan)
                    elif id in self.RIGHT_EYE_POINTS:
                        cv2.circle(image, (px, py), 3, (255, 255, 0), cv2.FILLED)

                    # Draw left eyebrow (purple)
                    elif id in self.LEFT_EYEBROW_POINTS:
                        cv2.circle(image, (px, py), 3, (255, 0, 255), cv2.FILLED)

                    # Draw right eyebrow (pink)
                    elif id in self.RIGHT_EYEBROW_POINTS:
                        cv2.circle(image, (px, py), 3, (255, 128, 255), cv2.FILLED)

                    # Draw nose (red)
                    elif id in self.NOSE_POINTS:
                        cv2.circle(image, (px, py), 4, (0, 0, 255), cv2.FILLED)

                    # Draw left ear (orange)
                    elif id in self.LEFT_EAR_POINTS:
                        cv2.circle(image, (px, py), 3, (0, 165, 255), cv2.FILLED)

                    # Draw right ear (light orange)
                    elif id in self.RIGHT_EAR_POINTS:
                        cv2.circle(image, (px, py), 3, (0, 200, 255), cv2.FILLED)

        return image
