"""
Image Processing Worker Thread
Handles camera capture, detection processing, and image conversion
"""

import sys
import threading
from typing import Callable, Optional

import cv2
import numpy as np
from aaa_core.config.console import error, status, success, underline
from aaa_core.config.settings import app_config
from aaa_vision.detection_manager import DetectionManager


class ImageProcessor(threading.Thread):
    """
    Worker thread for continuous camera capture and image processing
    Runs detection algorithms and provides processed frames via callback
    """

    def __init__(
        self,
        display_width: int = 800,
        display_height: int = 650,
        callback: Optional[Callable] = None,
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

    def _is_infrared_stream(self, camera_index: int) -> bool:
        """
        Check if a camera outputs infrared/grayscale data (all RGB channels identical)

        NOTE: On macOS, the RealSense D435 RGB module does NOT appear as a separate
        UVC camera device. Only the infrared/depth stream is accessible without the SDK.
        To access RealSense RGB color on macOS, use --enable-realsense flag.

        Args:
            camera_index: Camera index to check

        Returns:
            True if camera outputs infrared/grayscale, False if true RGB color
        """
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()

                if ret and frame is not None and len(frame.shape) == 3:
                    # Check if channels are EXACTLY identical (infrared hardware)
                    # True infrared has identical channels at hardware level (max_diff = 0)
                    # RGB cameras have independent sensors with natural noise variance
                    b, g, r = cv2.split(frame)
                    diff_bg = np.abs(b.astype(np.int16) - g.astype(np.int16))
                    diff_gr = np.abs(g.astype(np.int16) - r.astype(np.int16))
                    max_diff = max(diff_bg.max(), diff_gr.max())
                    is_infrared = max_diff == 0
                    return is_infrared
        except Exception:
            pass
        return False

    def _initialize_camera(self):
        """Initialize camera (RealSense if available, otherwise webcam)"""
        print("[DEBUG ImageProcessor] _initialize_camera called")

        # Check if RealSense should be enabled
        # - On Windows/Linux: auto-enable if RealSense SDK is available
        # - On macOS: require explicit --enable-realsense flag (due to USB permission issues)
        import sys

        explicit_enable = getattr(sys, "_enable_realsense_override", False)

        # Auto-enable RealSense on Windows/Linux if SDK is available
        if sys.platform == "darwin":
            # macOS requires explicit flag due to USB permission issues
            enable_realsense = explicit_enable
            if enable_realsense:
                status("RealSense enabled via --enable-realsense flag")
        else:
            # Windows/Linux: auto-enable if SDK available
            enable_realsense = app_config.realsense_available or explicit_enable
            if enable_realsense and app_config.realsense_available:
                status("RealSense SDK detected - enabling depth support")

        # Try to initialize RealSense first with timeout (only if enabled)
        if enable_realsense and app_config.realsense_available:
            realsense_result = {"camera": None, "error": None, "timed_out": False}

            def init_realsense():
                """Initialize RealSense in a separate thread"""
                try:
                    print(
                        "[DEBUG ImageProcessor] Attempting RealSense initialization..."
                    )
                    from aaa_core.hardware.realsense_camera import RealsenseCamera

                    print("[DEBUG ImageProcessor] Creating RealSense camera object...")
                    realsense_result["camera"] = RealsenseCamera()
                    print("[DEBUG ImageProcessor] RealSense initialized successfully")
                except Exception as e:
                    print(f"[DEBUG ImageProcessor] RealSense failed: {e}")
                    realsense_result["error"] = e

            # Start RealSense initialization in separate thread with timeout
            rs_thread = threading.Thread(target=init_realsense, daemon=True)
            rs_thread.start()
            rs_thread.join(timeout=5.0)  # 5 second timeout

            if rs_thread.is_alive():
                # Thread is still running after timeout
                print(
                    "[DEBUG ImageProcessor] RealSense initialization timed out after 5 seconds"
                )
                error("RealSense initialization timed out")
                status("Falling back to standard webcam")
                realsense_result["timed_out"] = True
            elif realsense_result["camera"]:
                # Success
                self.rs_camera = realsense_result["camera"]
                self.use_realsense = True
                success(f"Using {underline('RealSense camera')}")
            elif realsense_result["error"]:
                # Failed with exception
                error(f"RealSense initialization failed: {realsense_result['error']}")
                status("Falling back to standard webcam")

            # Use webcam if RealSense failed or timed out
            if not self.use_realsense:
                print("[DEBUG ImageProcessor] Creating standard webcam capture...")
                camera_index = app_config.default_camera
                print(f"[DEBUG ImageProcessor] Trying camera index {camera_index}...")
                self.camera = cv2.VideoCapture(camera_index)
                print("[DEBUG ImageProcessor] Standard webcam created")
        else:
            print("[DEBUG ImageProcessor] RealSense SDK disabled or not available")
            camera_index = app_config.default_camera

            # On macOS, RealSense RGB module is not accessible as UVC device
            # Only infrared/depth stream appears. Warn user if on camera 0.
            if (
                not enable_realsense
                and app_config.realsense_available
                and camera_index == 0
            ):
                status("Note: RealSense camera 0 is infrared (grayscale) on macOS")
                status("For RGB color from RealSense, use --enable-realsense flag")

            print(
                f"[DEBUG ImageProcessor] Opening camera index {camera_index} with OpenCV"
            )
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
        print(
            f"[DEBUG ImageProcessor] camera_changed called: index={camera_index}, name={camera_name}"
        )
        print(
            f"[DEBUG ImageProcessor] use_realsense={self.use_realsense}, camera={self.camera}"
        )

        # On macOS, block switching to RealSense cameras via OpenCV - causes segfault
        # and requires sudo for USB access. Use daemon instead.
        if sys.platform == "darwin" and camera_name and "RealSense" in camera_name:
            error("Cannot switch to RealSense camera via dropdown on macOS")
            status("RealSense requires: 1) Use 'make daemon-start' then 'make run', or")
            status("                    2) Run with --enable-realsense flag")
            status("Keeping current camera")
            return

        # Check if this is a RealSense camera on Windows/Linux - use SDK for depth
        is_realsense = camera_name and "RealSense" in camera_name
        use_sdk = (
            sys.platform != "darwin" and is_realsense and app_config.realsense_available
        )

        # Release existing cameras
        if self.use_realsense and self.rs_camera:
            print("[DEBUG ImageProcessor] Stopping RealSense camera...")
            try:
                self.rs_camera = None
                self.use_realsense = False
            except Exception as e:
                print(f"[DEBUG ImageProcessor] Error stopping RealSense: {e}")

        if self.camera:
            print("[DEBUG ImageProcessor] Releasing existing webcam...")
            try:
                self.camera.release()
                self.camera = None
            except Exception as e:
                print(f"[DEBUG ImageProcessor] Error releasing camera: {e}")

        # Open new camera - use RealSense SDK on Windows/Linux if applicable
        if use_sdk:
            print(
                "[DEBUG ImageProcessor] Initializing RealSense SDK for depth support..."
            )
            try:
                from aaa_core.hardware.realsense_camera import RealsenseCamera

                # Initialize with timeout to prevent hanging
                realsense_result = {"camera": None, "error": None}

                def init_realsense():
                    try:
                        realsense_result["camera"] = RealsenseCamera()
                    except Exception as e:
                        realsense_result["error"] = e

                rs_thread = threading.Thread(target=init_realsense, daemon=True)
                rs_thread.start()
                rs_thread.join(timeout=5.0)

                if rs_thread.is_alive():
                    error("RealSense initialization timed out")
                    status("Falling back to OpenCV (RGB only)")
                elif realsense_result["camera"]:
                    self.rs_camera = realsense_result["camera"]
                    self.use_realsense = True
                    self.current_camera_name = camera_name
                    self._update_flip_for_camera(camera_name)
                    success("Switched to RealSense camera with depth")
                    print(
                        "[DEBUG ImageProcessor] RealSense SDK initialized successfully"
                    )
                    return
                elif realsense_result["error"]:
                    error(f"RealSense SDK failed: {realsense_result['error']}")
                    status("Falling back to OpenCV (RGB only)")
            except Exception as e:
                error(f"RealSense SDK initialization failed: {e}")
                status("Falling back to OpenCV (RGB only)")

        # Fallback: Open camera via OpenCV (RGB only for RealSense)
        print(
            f"[DEBUG ImageProcessor] Opening camera index {camera_index} via OpenCV..."
        )
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
        # Only initialize if camera hasn't been set yet (e.g., via camera_changed)
        if not self.camera and not self.rs_camera:
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
                    self.callback(
                        processed_image
                    )  # Pass numpy array directly to callback

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

    def toggle_detection_logging(self):
        """Toggle detection logging for stability analysis"""
        self.detection_manager.toggle_logging()

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
        # Signal thread to stop
        self.thread_active = False

        # Wait for thread to finish FIRST (before releasing camera)
        # This prevents segfault from releasing camera while thread is reading
        if self.is_alive():
            self.join(timeout=2.0)

        # Now safe to release camera resources
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass

        # Clean up RealSense if used
        if self.rs_camera is not None:
            try:
                self.rs_camera = None
            except Exception:
                pass
