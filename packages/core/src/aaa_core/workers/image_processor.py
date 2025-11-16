"""
Image Processing Worker Thread
Handles camera capture, detection processing, and image conversion
"""

import threading
from typing import Callable, Optional

import cv2
import numpy as np
from aaa_vision.detection_manager import DetectionManager

from aaa_core.config.console import error, status, success, underline
from aaa_core.config.settings import app_config


class ImageProcessor(threading.Thread):
    """
    Worker thread for continuous camera capture and image processing
    Runs detection algorithms and provides processed frames via callback
    """

    def __init__(
        self,
        display_width: int = 800,
        display_height: int = 650,
        callback: Optional[Callable] = None
    ):
        """
        Initialize image processor

        Args:
            display_width: Width for display scaling
            display_height: Height for display scaling
            callback: Callback function to receive processed frames (numpy array)
        """
        super(ImageProcessor, self).__init__(daemon=True)
        status("Image processor initialized")

        self.display_width = display_width
        self.display_height = display_height
        self.thread_active = False
        self.callback = callback  # For Flet or other non-Qt frameworks

        # Camera setup
        self.use_realsense = False
        self.rs_camera = None
        self.camera = None
        self.depth_frame = None

        # Fixed reference point for depth measurement (when RealSense available)
        self.reference_point = (250, 100)  # (x, y) for fixed depth reading
        self.show_reference_point = True

        self._initialize_camera()

        # Detection setup
        self.detection_manager = DetectionManager()

    def _initialize_camera(self):
        """Initialize camera (RealSense if available, otherwise webcam)"""
        # Try to initialize RealSense first
        if app_config.realsense_available:
            try:
                from aaa_core.hardware.realsense_camera import RealsenseCamera

                self.rs_camera = RealsenseCamera()
                self.use_realsense = True
                success(f"Using {underline('RealSense camera')}")
            except Exception as e:
                error(f"RealSense initialization failed: {e}")
                status("Falling back to standard webcam")
                self.camera = cv2.VideoCapture(0)
        else:
            self.camera = cv2.VideoCapture(0)
            success(f"Using {underline('standard webcam')}")

    def camera_changed(self, camera_index: int):
        """
        Switch to a different camera

        Args:
            camera_index: Index of the camera to switch to
        """
        # Only works with standard webcam, not RealSense
        if not self.use_realsense and self.camera:
            self.camera.release()
            self.camera = cv2.VideoCapture(camera_index)
            success(f"Switched to camera {camera_index}")

    def run(self):
        """Main processing loop"""
        status("Image processor is running")
        self.thread_active = True

        while self.thread_active:
            ret, frame, depth_frame = self._capture_frame()

            if ret and frame is not None:
                # Flip image horizontally for mirror effect FIRST
                frame = cv2.flip(frame, 1)

                # Also flip depth frame if available
                if depth_frame is not None:
                    depth_frame = cv2.flip(depth_frame, 1)

                # Convert to RGB
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Process with detection (labels will now be correct orientation)
                processed_image = self.detection_manager.process_frame(
                    image_rgb, depth_frame
                )

                # Draw fixed reference point depth measurement if RealSense is active
                if self.show_reference_point and depth_frame is not None:
                    processed_image = self._draw_reference_point(
                        processed_image, depth_frame
                    )

                # Call callback if provided
                if self.callback:
                    self.callback(processed_image)  # Pass numpy array directly to callback

    def _capture_frame(self):
        """
        Capture a frame from the active camera

        Returns:
            Tuple of (success, frame, depth_frame)
        """
        ret = False
        frame = None
        depth_frame = None

        if self.use_realsense and self.rs_camera:
            ret, frame, depth_frame = self.rs_camera.get_frame_stream()
            self.depth_frame = depth_frame
        elif self.camera:
            ret, frame = self.camera.read()

        return ret, frame, depth_frame

    def _draw_reference_point(
        self, image: np.ndarray, depth_frame: np.ndarray
    ) -> np.ndarray:
        """
        Draw a fixed reference point with depth measurement

        Args:
            image: RGB image array
            depth_frame: Depth frame from RealSense

        Returns:
            Image with reference point drawn
        """
        point_x, point_y = self.reference_point

        # Ensure point is within depth frame bounds
        if 0 <= point_y < depth_frame.shape[0] and 0 <= point_x < depth_frame.shape[1]:
            try:
                distance_mm = depth_frame[point_y, point_x]

                # Draw red circle at reference point
                cv2.circle(image, (point_x, point_y), 8, (255, 0, 0), -1)

                # Draw distance text above the point
                cv2.putText(
                    image,
                    f"{distance_mm} mm",
                    (point_x, point_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2,
                )
            except Exception:
                pass  # Silently skip if depth is unavailable at reference point

        return image

    def toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        self.detection_manager.toggle_mode()

    def set_detection_mode(self, mode: str):
        """
        Set detection mode directly

        Args:
            mode: Detection mode ("objects", "face", "combined", "camera")
        """
        self.detection_manager.detection_mode = mode

    @property
    def detection_mode(self) -> str:
        """Get current detection mode"""
        return self.detection_manager.detection_mode

    @property
    def has_object_detection(self) -> bool:
        """Check if object detection is available"""
        return self.detection_manager.has_object_detection

    def stop(self):
        """Stop the processing thread"""
        self.thread_active = False
        self.quit()
        self.wait()
