"""
Daemon Image Processor
Reads frames from camera daemon instead of direct camera access
Drop-in replacement for ImageProcessor when using daemon architecture
"""

import threading
import time
from typing import Callable, Optional

import numpy as np
from aaa_vision.detection_manager import DetectionManager

from aaa_core.config.console import error, status, success, warning
from aaa_core.daemon.camera_client_socket import CameraClientSocket


class DaemonImageProcessor(threading.Thread):
    """
    Image processor that reads from camera daemon via shared memory

    This is a drop-in replacement for ImageProcessor that works with
    the daemon architecture. It reads frames from shared memory instead
    of accessing the camera directly.

    Compatible with existing GUI code - same interface as ImageProcessor.
    """

    def __init__(
        self,
        display_width: int = 800,
        display_height: int = 650,
        callback: Optional[Callable] = None,
    ):
        """
        Initialize daemon image processor

        Args:
            display_width: Width for display scaling
            display_height: Height for display scaling
            callback: Callback function to receive processed frames (numpy array)
        """
        super(DaemonImageProcessor, self).__init__(daemon=True)
        status("Daemon image processor initialized")

        self.display_width = display_width
        self.display_height = display_height
        self.thread_active = False
        self.callback = callback

        # Connect to daemon
        self.camera_client = CameraClientSocket()

        # Video freeze state (for Find Objects feature)
        self.video_frozen = False
        self.frozen_frame = None

        # Initialize detection manager
        self.detection_manager = DetectionManager()
        self.detection_mode = self.detection_manager.detection_mode

        # Camera info
        self.use_realsense = True  # Daemon always provides RealSense
        self.has_object_detection = (
            self.detection_manager.segmentation_model is not None
        )

        # Depth visualization toggle (show colorized depth instead of RGB)
        self.show_depth_visualization = False

        # Store last RGB frame for re-detection
        self._last_rgb_frame = None

        # Store last depth frame for point cloud extraction
        self.depth_frame = None

        # Store last aligned color frame (848x480, pixel-aligned to depth)
        self._last_aligned_color = None

        # Track recent frame brightness for auto-exposure (rolling buffer of ~2 seconds @ 30fps)
        from collections import deque

        self._brightness_history = deque(maxlen=60)  # 60 frames = 2 seconds at 30fps
        self._brightness_lock = threading.Lock()

    def run(self):
        """Main processing loop - read frames from daemon"""
        status("Daemon image processor running")
        self.thread_active = True

        frame_count = 0

        while self.thread_active:
            try:
                # Read frame from daemon via socket
                rgb_frame, depth_frame, metadata, aligned_color = (
                    self.camera_client.get_frame()
                )

                if rgb_frame is not None:
                    frame_count += 1
                    if frame_count % 30 == 0:  # Debug every 30 frames
                        status(f"[DaemonImageProcessor] Received frame {frame_count}")

                    # Convert BGR to RGB (RealSense provides BGR)
                    image_rgb = rgb_frame[:, :, ::-1].copy()

                    # Store for re-detection
                    self._last_rgb_frame = image_rgb.copy()

                    # Store depth frame for point cloud extraction
                    self.depth_frame = (
                        depth_frame.copy() if depth_frame is not None else None
                    )

                    # Store aligned color (848x480, pixel-aligned to depth)
                    self._last_aligned_color = (
                        aligned_color.copy() if aligned_color is not None else None
                    )

                    # Track brightness for auto-exposure (calculate from RGB)
                    avg_brightness = np.mean(image_rgb)
                    with self._brightness_lock:
                        self._brightness_history.append(avg_brightness)

                    # Process with detection manager
                    processed_frame = self.detection_manager.process_frame(
                        image_rgb, depth_frame=depth_frame
                    )

                    # If depth visualization is enabled, show colorized depth instead
                    if self.show_depth_visualization and depth_frame is not None:
                        processed_frame = self._colorize_depth(
                            depth_frame,
                            aligned_color=self._last_aligned_color,
                            display_shape=image_rgb.shape,
                        )

                    # Call callback with processed frame
                    if self.callback:
                        self.callback(processed_frame)
                    else:
                        if frame_count == 1:
                            warning("[DaemonImageProcessor] No callback set!")
                else:
                    if frame_count == 0:
                        status("[DaemonImageProcessor] Waiting for first frame...")
                    time.sleep(0.1)  # Wait longer if no frame

                # Sleep to target ~30 fps
                time.sleep(1 / 30)

            except Exception as e:
                error(f"Error in daemon image processor: {e}")
                time.sleep(0.1)  # Avoid busy loop on error

    def stop(self):
        """Stop the processing thread"""
        status("Stopping daemon image processor...")

        # Signal thread to stop
        self.thread_active = False

        # Wait for thread to finish FIRST (before disconnecting)
        # Socket has 1-second timeout, so thread will exit promptly
        if self.is_alive():
            self.join(timeout=2.0)

        # Now safe to disconnect from daemon
        if self.camera_client:
            self.camera_client.disconnect()

        success("Daemon image processor stopped")

    def camera_changed(self, camera_index: int, camera_name: str = None):
        """
        Camera switching not supported in daemon mode
        Daemon controls which camera to use
        """
        status("Camera switching not supported in daemon mode")

    def toggle_flip(self):
        """Flip not yet implemented in daemon mode"""
        status("Flip not yet implemented in daemon mode")

    def toggle_depth_visualization(self):
        """Toggle between RGB and depth visualization"""
        self.show_depth_visualization = not self.show_depth_visualization
        view_mode = "Depth" if self.show_depth_visualization else "RGB"
        status(f"Switched to {view_mode} view")
        return self.show_depth_visualization

    def _colorize_depth(
        self,
        depth_frame: np.ndarray,
        aligned_color: np.ndarray = None,
        display_shape: tuple = None,
    ) -> np.ndarray:
        """
        Convert depth frame to colorized visualization, optionally blended
        with the SDK-aligned color frame for pixel-accurate overlay.

        Args:
            depth_frame: Raw depth frame (uint16, values in mm) at native 848x480
            aligned_color: SDK-aligned color frame (BGR, same resolution as depth).
                If provided, blended with the colorized depth for context.
            display_shape: Target display shape (height, width, ...) to upscale to.
                If None, returns at native depth resolution.

        Returns:
            Colorized (and optionally blended) depth image as RGB numpy array
        """
        import cv2

        # Normalize depth to 0-255 range (clip at 5000mm = 5m for better contrast)
        depth_clipped = np.clip(depth_frame, 0, 5000)
        depth_normalized = (depth_clipped / 5000 * 255).astype(np.uint8)

        # Apply colormap (TURBO gives good depth perception)
        depth_colorized = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_TURBO)

        # Blend with SDK-aligned color at native depth resolution (pixel-accurate)
        if aligned_color is not None and aligned_color.shape[:2] == depth_frame.shape[:2]:
            blended = cv2.addWeighted(aligned_color, 0.4, depth_colorized, 0.6, 0)
        else:
            blended = depth_colorized

        # Convert BGR to RGB for display
        result = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)

        # Upscale to display size if requested
        if display_shape is not None:
            h, w = display_shape[:2]
            result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR)

        return result

    def toggle_detection_mode(self):
        """Toggle detection mode"""
        self.detection_manager.toggle_mode()
        self.detection_mode = self.detection_manager.detection_mode
        status(f"Detection mode toggled to: {self.detection_mode}")

    def set_detection_mode(self, mode: str):
        """Set detection mode"""
        self.detection_manager.detection_mode = mode
        self.detection_mode = mode
        status(f"Detection mode set to: {mode}")

    @property
    def flip_horizontal(self):
        """Flip property for compatibility"""
        return False

    def set_realsense_exposure(self, exposure_value: int) -> bool:
        """
        Set RealSense camera exposure via daemon command socket

        Args:
            exposure_value: Exposure value (50-1000)

        Returns:
            bool: True if command sent successfully
        """
        try:
            import json
            import socket

            # Create UDP socket
            cmd_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

            # Send command to daemon
            command = {"command": "set_exposure", "value": int(exposure_value)}

            cmd_socket.sendto(
                json.dumps(command).encode("utf-8"), "/tmp/aaa_camera_cmd.sock"
            )

            cmd_socket.close()
            return True

        except Exception as e:
            error(f"Failed to send exposure command: {e}")
            return False

    def get_recent_brightness(self) -> float:
        """
        Get average brightness from recent frames (~2 seconds)

        Returns:
            float: Average brightness (0-255), or 128 if no data available
        """
        with self._brightness_lock:
            if len(self._brightness_history) == 0:
                return 128.0  # Default middle brightness
            return float(np.mean(self._brightness_history))

    def clear_brightness_history(self):
        """Clear brightness history buffer (useful after exposure changes)"""
        with self._brightness_lock:
            self._brightness_history.clear()
        success(
            "Brightness history cleared (waiting for new frames with updated exposure)"
        )
