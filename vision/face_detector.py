"""
Face Landmark Detection
Uses MediaPipe to track facial landmarks, specifically mouth points
"""

import cv2
import mediapipe as mp
import numpy as np


class FaceDetector:
    """Detects and tracks facial landmarks using MediaPipe"""

    # Mouth landmark indices from MediaPipe face mesh
    # Reference: https://raw.githubusercontent.com/google/mediapipe/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
    MOUTH_POINTS = [
        78,
        191,
        80,
        81,
        82,
        13,
        312,
        311,
        310,
        415,
        308,
        324,
        318,
        402,
        317,
        14,
        87,
        178,
        88,
        95,
    ]

    def __init__(self):
        """Initialize MediaPipe face mesh"""
        self.mp_mesh = mp.solutions.face_mesh
        self.mesh = self.mp_mesh.FaceMesh()
        self.mp_draw = mp.solutions.drawing_utils
        print("Face detector initialized")

    def detect_and_draw(self, image: np.ndarray) -> np.ndarray:
        """
        Detect face landmarks and draw them on the image

        Args:
            image: RGB image array

        Returns:
            Image with landmarks drawn
        """
        results = self.mesh.process(image)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                tx = 0
                ty = 0

                for id, lm in enumerate(face_landmarks.landmark):
                    if id in self.MOUTH_POINTS:
                        h, w, c = image.shape
                        px, py = int(lm.x * w), int(lm.y * h)

                        # Calculate center point from landmarks 13 and 14
                        if id in [13, 14]:
                            tx += px
                            ty += py

                        if id == 14:
                            # Draw center of mouth
                            tx = int(tx / 2)
                            ty = int(ty / 2)
                            cv2.circle(image, (tx, ty), 10, (0, 255, 255), cv2.FILLED)

                        # Draw individual mouth points
                        cv2.circle(image, (px, py), 4, (0, 255, 0), cv2.FILLED)

        return image
