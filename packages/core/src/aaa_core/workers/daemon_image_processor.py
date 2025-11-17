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

from aaa_core.config.console import error, status, success
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
        callback: Optional[Callable] = None
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
        self.has_object_detection = self.detection_manager.segmentation_model is not None

        # Store last RGB frame for re-detection
        self._last_rgb_frame = None

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
                # Read frame from daemon via shared memory
                rgb_frame, depth_frame, metadata = self.camera_client.get_frame()

                if rgb_frame is not None:
                    frame_count += 1
                    if frame_count % 30 == 0:  # Debug every 30 frames
                        print(f"[DaemonImageProcessor] Received frame {frame_count}")

                    # Convert BGR to RGB (RealSense provides BGR)
                    image_rgb = rgb_frame[:, :, ::-1].copy()

                    # Store for re-detection
                    self._last_rgb_frame = image_rgb.copy()

                    # Track brightness for auto-exposure (calculate from RGB)
                    avg_brightness = np.mean(image_rgb)
                    with self._brightness_lock:
                        self._brightness_history.append(avg_brightness)

                    # Process with detection manager
                    processed_frame = self.detection_manager.process_frame(
                        image_rgb,
                        depth_frame=depth_frame
                    )

                    # Call callback with processed frame
                    if self.callback:
                        self.callback(processed_frame)
                    else:
                        if frame_count == 1:
                            print("[DaemonImageProcessor] WARNING: No callback set!")
                else:
                    if frame_count == 0:
                        print("[DaemonImageProcessor] Waiting for first frame...")
                    time.sleep(0.1)  # Wait longer if no frame

                # Sleep to target ~30 fps
                time.sleep(1/30)

            except Exception as e:
                error(f"Error in daemon image processor: {e}")
                time.sleep(0.1)  # Avoid busy loop on error

    def stop(self):
        """Stop the processing thread"""
        status("Stopping daemon image processor...")
        self.thread_active = False

        # Disconnect from daemon
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

    def toggle_detection_mode(self):
        """Toggle detection mode"""
        self.detection_manager.toggle_mode()
        self.detection_mode = self.detection_manager.detection_mode
        status(f"Detection mode toggled to: {self.detection_mode}")

    def set_detection_mode(self, mode: str):
        """Set detection mode"""
        self.detection_manager.set_mode(mode)
        self.detection_mode = self.detection_manager.detection_mode
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
            command = {
                'command': 'set_exposure',
                'value': int(exposure_value)
            }

            cmd_socket.sendto(
                json.dumps(command).encode('utf-8'),
                '/tmp/aaa_camera_cmd.sock'
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
        print("✓ Brightness history cleared (waiting for new frames with updated exposure)")
