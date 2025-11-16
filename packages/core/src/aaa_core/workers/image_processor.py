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

        # Store last raw RGB frame for frozen frame re-processing
        self._last_rgb_frame = None

        # Horizontal flip (mirror) for front-facing cameras
        self.flip_horizontal = False
        self.current_camera_name = None

        # Camera will be initialized when thread starts (in run() method)
        # to avoid blocking the UI thread

        # Detection setup
        self.detection_manager = DetectionManager()

    def _initialize_camera(self):
        """Initialize camera (RealSense if available, otherwise webcam)"""
        print("[DEBUG ImageProcessor] _initialize_camera called")

        # Check if RealSense is explicitly enabled via command-line
        import sys
        enable_realsense = getattr(sys, '_enable_realsense_override', False)

        if enable_realsense:
            status("RealSense enabled via --enable-realsense flag")

        # Try to initialize RealSense first with timeout (only if enabled)
        if enable_realsense and app_config.realsense_available:
            realsense_result = {'camera': None, 'error': None, 'timed_out': False}

            def init_realsense():
                """Initialize RealSense in a separate thread"""
                try:
                    print("[DEBUG ImageProcessor] Attempting RealSense initialization...")
                    from aaa_core.hardware.realsense_camera import RealsenseCamera
                    print("[DEBUG ImageProcessor] Creating RealSense camera object...")
                    realsense_result['camera'] = RealsenseCamera()
                    print("[DEBUG ImageProcessor] RealSense initialized successfully")
                except Exception as e:
                    print(f"[DEBUG ImageProcessor] RealSense failed: {e}")
                    realsense_result['error'] = e

            # Start RealSense initialization in separate thread with timeout
            rs_thread = threading.Thread(target=init_realsense, daemon=True)
            rs_thread.start()
            rs_thread.join(timeout=5.0)  # 5 second timeout

            if rs_thread.is_alive():
                # Thread is still running after timeout
                print("[DEBUG ImageProcessor] RealSense initialization timed out after 5 seconds")
                error("RealSense initialization timed out")
                status("Falling back to standard webcam")
                realsense_result['timed_out'] = True
            elif realsense_result['camera']:
                # Success
                self.rs_camera = realsense_result['camera']
                self.use_realsense = True
                success(f"Using {underline('RealSense camera')}")
            elif realsense_result['error']:
                # Failed with exception
                error(f"RealSense initialization failed: {realsense_result['error']}")
                status("Falling back to standard webcam")

            # Use webcam if RealSense failed or timed out
            if not self.use_realsense:
                print("[DEBUG ImageProcessor] Creating standard webcam capture...")
                # Try next camera index if default is 0 (likely the failed RealSense)
                fallback_camera = app_config.default_camera + 1 if app_config.default_camera == 0 else app_config.default_camera
                print(f"[DEBUG ImageProcessor] Trying camera index {fallback_camera}...")
                self.camera = cv2.VideoCapture(fallback_camera)
                print("[DEBUG ImageProcessor] Standard webcam created")
        else:
            print("[DEBUG ImageProcessor] RealSense SDK disabled or not available")
            if not enable_realsense and app_config.realsense_available:
                status("Using RealSense RGB camera as standard webcam (depth disabled)")

            camera_index = app_config.default_camera
            print(f"[DEBUG ImageProcessor] Opening camera index {camera_index} with OpenCV")
            self.camera = cv2.VideoCapture(camera_index)
            success(f"Using {underline('standard webcam')} (camera {camera_index})")
        print("[DEBUG ImageProcessor] _initialize_camera completed")

    def camera_changed(self, camera_index: int, camera_name: str = None):
        """
        Switch to a different camera

        Args:
            camera_index: Index of the camera to switch to
            camera_name: Name of the camera (optional, used to auto-enable flip)
        """
        print(f"[DEBUG ImageProcessor] camera_changed called: index={camera_index}, name={camera_name}")
        print(f"[DEBUG ImageProcessor] use_realsense={self.use_realsense}, camera={self.camera}")

        # If using RealSense, stop it and switch to webcam
        if self.use_realsense and self.rs_camera:
            print("[DEBUG ImageProcessor] Stopping RealSense camera...")
            try:
                # RealSense doesn't have a release method, just set to None
                self.rs_camera = None
                self.use_realsense = False
            except Exception as e:
                print(f"[DEBUG ImageProcessor] Error stopping RealSense: {e}")

        # Release existing webcam if any
        if self.camera:
            print("[DEBUG ImageProcessor] Releasing existing webcam...")
            try:
                self.camera.release()
            except Exception as e:
                print(f"[DEBUG ImageProcessor] Error releasing camera: {e}")

        # Open new camera
        print(f"[DEBUG ImageProcessor] Opening camera index {camera_index}...")
        self.camera = cv2.VideoCapture(camera_index)
        self.use_realsense = False
        self.current_camera_name = camera_name

        # Auto-enable flip for built-in MacBook cameras
        self._update_flip_for_camera(camera_name)

        success(f"Switched to camera {camera_index}")
        print(f"[DEBUG ImageProcessor] Camera switch complete")

    def _update_flip_for_camera(self, camera_name: str):
        """
        Auto-enable horizontal flip for built-in MacBook cameras

        Args:
            camera_name: Name of the camera
        """
        if camera_name:
            # Check if this is a built-in MacBook camera
            builtin_keywords = ["MacBook", "FaceTime HD Camera", "iSight"]
            is_builtin = any(keyword in camera_name for keyword in builtin_keywords)
            self.flip_horizontal = is_builtin

            if is_builtin:
                status(f"Auto-enabled flip for built-in camera: {camera_name}")

    def toggle_flip(self):
        """Toggle horizontal flip on/off"""
        self.flip_horizontal = not self.flip_horizontal
        flip_state = "enabled" if self.flip_horizontal else "disabled"
        status(f"Camera flip {flip_state}")

    def run(self):
        """Main processing loop"""
        status("Image processor is running")
        self.thread_active = True

        # Initialize camera in the thread to avoid blocking UI
        self._initialize_camera()

        while self.thread_active:
            ret, frame, depth_frame = self._capture_frame()

            if ret and frame is not None:
                # Flip image horizontally for mirror effect if enabled
                if self.flip_horizontal:
                    frame = cv2.flip(frame, 1)

                    # Also flip depth frame if available
                    if depth_frame is not None:
                        depth_frame = cv2.flip(depth_frame, 1)

                # Convert to RGB
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Store the raw RGB frame (before processing) for frozen frame re-processing
                self._last_rgb_frame = image_rgb.copy()

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
