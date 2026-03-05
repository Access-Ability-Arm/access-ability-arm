"""Camera & Exposure Control mixin for MainWindow.

Provides camera switching (regular/daemon), flip, depth view toggle,
and RealSense exposure controls including auto-exposure adjustment.
"""

import sys
import time

from aaa_core.config.settings import app_config
from aaa_core.workers.image_processor import ImageProcessor

try:
    from aaa_core.daemon.camera_client import CameraClient
    from aaa_core.workers.daemon_image_processor import DaemonImageProcessor

    DAEMON_AVAILABLE = True
except ImportError:
    DAEMON_AVAILABLE = False


class CameraMixin:
    """Mixin that provides camera and exposure control methods for MainWindow."""

    def _check_daemon_running(self):
        """
        Check if camera daemon is running and responding

        Returns:
            bool: True if daemon is running and accepting connections, False otherwise
        """
        # Daemon is only used on macOS (RealSense requires sudo there)
        # On Windows/Linux, RealSense can be accessed directly
        if sys.platform != "darwin":
            print("[DEBUG] _check_daemon_running: Not macOS, daemon not needed")
            return False

        print(f"[DEBUG] _check_daemon_running: DAEMON_AVAILABLE={DAEMON_AVAILABLE}")
        if not DAEMON_AVAILABLE:
            print("[DEBUG] _check_daemon_running: Daemon components not available")
            return False

        import os
        import socket

        SOCKET_PATH = "/tmp/aaa_camera.sock"

        try:
            # Check if socket file exists
            print(
                f"[DEBUG] _check_daemon_running: Checking for socket at {SOCKET_PATH}..."
            )
            if not os.path.exists(SOCKET_PATH):
                print("[DEBUG] _check_daemon_running: Socket not found")
                return False

            # Socket file exists - verify daemon is actually responding
            print("[DEBUG] _check_daemon_running: Socket found, testing connection...")
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.settimeout(1.0)
            try:
                test_socket.connect(SOCKET_PATH)
                test_socket.close()
                print("[DEBUG] _check_daemon_running: Daemon is responding")
                return True
            except (ConnectionRefusedError, OSError) as e:
                print(f"[DEBUG] _check_daemon_running: Daemon not responding: {e}")
                return False
        except Exception as e:
            print(f"[DEBUG] _check_daemon_running: Error checking daemon - {e}")
            return False

    def _on_camera_changed(self, e):
        """Handle camera selection change"""
        if not e.control.value:
            return

        selected_value = e.control.value

        # Check if switching to daemon or regular camera
        if selected_value == "daemon":
            print("Switching to RealSense daemon...")
            self._switch_to_daemon()
        else:
            camera_index = int(selected_value)
            print(f"Switching to camera {camera_index}")

            # Get camera name from camera manager
            camera_name = None
            for cam in self.camera_manager.cameras:
                if cam["camera_index"] == camera_index:
                    camera_name = cam["camera_name"]
                    break

            # Check if currently using daemon - need to switch processor type
            is_using_daemon = (
                isinstance(self.image_processor, DaemonImageProcessor)
                if DAEMON_AVAILABLE
                else False
            )

            if is_using_daemon:
                # Switch from daemon to regular ImageProcessor
                self._switch_to_regular_camera(camera_index, camera_name)
            elif self.image_processor:
                # Already using regular processor, just change camera
                self.image_processor.camera_changed(camera_index, camera_name)
                self._update_status()
                if self.video_frozen:
                    self._unfreeze_video()

    def _switch_to_daemon(self):
        """Switch from regular camera to daemon (RealSense with depth)"""
        if not DAEMON_AVAILABLE:
            print("[ERROR] Daemon components not available")
            return

        # Stop current image processor
        if self.image_processor:
            self.image_processor.stop()

        # Create new DaemonImageProcessor
        self.image_processor = DaemonImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
            callback=self._update_video_feed,
        )
        self.image_processor.start()
        self.using_realsense = True

        # Set detection mode to camera only (Manual tab default)
        self.image_processor.set_detection_mode("camera")

        # Update status
        self._update_status()
        if self.video_frozen:
            self._unfreeze_video()
        print("Switched to RealSense daemon (with depth)")

    def _switch_to_regular_camera(self, camera_index: int, camera_name: str):
        """Switch from daemon to regular camera"""
        # Stop current image processor
        if self.image_processor:
            self.image_processor.stop()

        # Create new ImageProcessor
        self.image_processor = ImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
            callback=self._update_video_feed,
        )

        # Set camera before starting
        self.image_processor.current_camera_name = camera_name
        self.image_processor._update_flip_for_camera(camera_name)
        self.image_processor.camera_changed(camera_index, camera_name)

        # Start processor
        self.image_processor.start()

        # Set detection mode to camera only (Manual tab default)
        self.image_processor.set_detection_mode("camera")

        # Update status
        self._update_status()
        if self.video_frozen:
            self._unfreeze_video()
        print(f"Switched to regular camera: {camera_name}")

    def _on_refresh_camera(self):
        """Handle refresh camera button - capture new frame"""
        if self.video_frozen:
            self._unfreeze_video()
        print("Camera view refreshed")

    def _unfreeze_video(self):
        """Unfreeze video to show live camera feed"""
        self.video_frozen = False
        self.frozen_frame = None
        self.frozen_raw_frame = None
        self.frozen_detections = None
        self.frozen_depth_frame = None
        self.frozen_aligned_color = None
        self.frozen_display_depth = None
        self._clear_object_buttons()
        print("Video unfrozen - showing live camera feed")

    def _on_flip_camera(self):
        """Toggle horizontal flip for camera"""
        if self.image_processor:
            self.image_processor.toggle_flip()
            # Update button appearance to show flip state
            if self.image_processor.flip_horizontal:
                self.flip_camera_btn.bgcolor = "#4CAF50"  # Green 500 when enabled
                self.flip_camera_btn.icon_color = "#FFFFFF"  # White icon
            else:
                self.flip_camera_btn.bgcolor = "#E0E0E0"  # Grey 300 when disabled
                self.flip_camera_btn.icon_color = "#424242"  # Grey 800
            self.page.update()

    def _on_toggle_depth_view(self):
        """Toggle between RGB and depth visualization"""
        if self.image_processor:
            is_depth = self.image_processor.toggle_depth_visualization()
            # Update button appearance to show current view mode
            if is_depth:
                self.depth_toggle_btn.bgcolor = "#2196F3"  # Blue 500 when showing depth
                self.depth_toggle_btn.icon_color = "#FFFFFF"  # White icon
                self.depth_toggle_btn.tooltip = "Showing Depth view (click for RGB)"
            else:
                self.depth_toggle_btn.bgcolor = "#E0E0E0"  # Grey 300 when showing RGB
                self.depth_toggle_btn.icon_color = "#424242"  # Grey 800
                self.depth_toggle_btn.tooltip = "Showing RGB view (click for Depth)"
            self.page.update()

    def _on_exposure_change(self, e):
        """Handle RealSense exposure slider change"""
        if not self.using_realsense or not self.image_processor:
            return

        exposure_value = int(e.control.value)
        self.exposure_value_text.value = f"Exposure: {exposure_value}"

        # Update RealSense camera exposure
        if self.image_processor.set_realsense_exposure(exposure_value):
            print(f"\u2713 RealSense exposure set to {exposure_value}")

        self.page.update()

    def _auto_adjust_exposure(self):
        """Run auto-exposure adjustment once"""
        if not self.using_realsense or not self.image_processor:
            return

        # Run once
        self._run_auto_exposure_once()

    def _run_auto_exposure_once(self):
        """Run auto-exposure adjustment once without enabling continuous mode"""
        if not self.using_realsense or not self.image_processor:
            return

        try:
            # Get current frame brightness
            if hasattr(self.image_processor, "get_recent_brightness"):
                avg_brightness = self.image_processor.get_recent_brightness()
            else:
                return

            # Calculate optimal exposure
            current_exposure = int(self.exposure_slider.value)
            # Target: 90 (lower than 128) for better noise/clarity tradeoff
            # Segmentation models prioritize clean edges over brightness
            target_brightness = 90
            brightness_ratio = target_brightness / max(avg_brightness, 1)
            new_exposure = int(current_exposure * brightness_ratio)

            # Clamp with max 2500 to avoid excessive noise (high exposure = worse segmentation)
            new_exposure = max(100, min(2500, new_exposure))

            print(
                f"Startup auto-exposure: brightness={avg_brightness:.1f}, {current_exposure} \u2192 {new_exposure}"
            )

            # Update slider and camera
            self.exposure_slider.value = new_exposure
            self.exposure_value_text.value = f"Exposure: {new_exposure}"

            if self.image_processor.set_realsense_exposure(new_exposure):
                print(f"\u2713 Exposure set to {new_exposure}")
                print(
                    f"   (Wait ~2 seconds for camera to adjust and buffer to refill before clicking auto-exposure again)"
                )

            self.page.update()

        except Exception as e:
            print(f"Startup auto-exposure failed: {e}")

    def _continuous_auto_exposure(self):
        """Continuously adjust exposure until disabled"""
        while self.auto_exposure_enabled:
            try:
                # Get current frame brightness
                if hasattr(self.image_processor, "get_recent_brightness"):
                    avg_brightness = self.image_processor.get_recent_brightness()
                else:
                    # Fallback: analyze current displayed frame
                    if self.video_feed.src_base64:
                        import base64
                        from io import BytesIO

                        import numpy as np
                        from PIL import Image

                        img_data = base64.b64decode(
                            self.video_feed.src_base64.split(",")[1]
                        )
                        img = Image.open(BytesIO(img_data))
                        img_array = np.array(img.convert("RGB"))
                        avg_brightness = np.mean(img_array)
                    else:
                        time.sleep(10)
                        continue

                # Calculate optimal exposure
                current_exposure = int(self.exposure_slider.value)
                target_brightness = 128
                brightness_ratio = target_brightness / max(avg_brightness, 1)
                new_exposure = int(current_exposure * brightness_ratio)

                # Clamp to slider range
                new_exposure = max(100, min(4000, new_exposure))

                # Only adjust if change is significant (>5%)
                if abs(new_exposure - current_exposure) / current_exposure > 0.05:
                    print(
                        f"Auto-exposure: brightness={avg_brightness:.1f}, {current_exposure} \u2192 {new_exposure}"
                    )

                    # Update slider and camera
                    self.exposure_slider.value = new_exposure
                    self.exposure_value_text.value = f"Exposure: {new_exposure}"

                    if self.image_processor.set_realsense_exposure(new_exposure):
                        pass  # Success

                    self.page.update()

                # Wait 10 seconds before next check (sporadic to improve responsiveness)
                time.sleep(10)

            except Exception as e:
                print(f"Auto-exposure error: {e}")
                time.sleep(10)
