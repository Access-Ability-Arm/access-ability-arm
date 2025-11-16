"""
Camera Daemon - Runs with elevated privileges for RealSense access
Writes frames to shared memory for GUI consumption
"""

import json
import signal
import sys
import time
from multiprocessing import shared_memory

import numpy as np

from aaa_core.config.console import error, status, success, underline


class CameraDaemon:
    """
    Daemon process for camera capture with elevated privileges

    Manages:
    - RealSense camera initialization
    - Continuous frame capture
    - Shared memory buffer management
    - Command socket listener (future)

    Shared Memory Layout:
    - aaa_rgb_frame: 1280x720x3 uint8 (RGB frame)
    - aaa_depth_frame: 1280x720 uint16 (depth in mm)
    - aaa_metadata: 4096 bytes JSON (frame info)
    """

    def __init__(self):
        """Initialize daemon (does not start capture)"""
        self.running = False

        # Shared memory buffers
        self.shm_rgb = None
        self.shm_depth = None
        self.shm_metadata = None

        # Frame dimensions (1280x720 for RealSense D435)
        self.rgb_shape = (720, 1280, 3)
        self.depth_shape = (720, 1280)

        # Camera
        self.rs_camera = None

        # Frame counter for stats
        self.frame_count = 0
        self.start_time = None

        # Detection mode
        self.detection_mode = "camera"  # camera, objects, face

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        status("Camera daemon initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Initialize camera and shared memory, start capture loop"""
        try:
            status("Starting camera daemon...")

            # Create shared memory buffers
            self._create_shared_memory()

            # Initialize RealSense camera
            self._initialize_camera()

            # Start capture
            self.running = True
            self.start_time = time.time()
            self._capture_loop()

        except KeyboardInterrupt:
            print("\nInterrupted by user")
            self.stop()
        except Exception as e:
            error(f"Fatal error in daemon: {e}")
            import traceback
            traceback.print_exc()
            self.stop()
            raise

    def stop(self):
        """Stop capture and cleanup resources"""
        status("Stopping camera daemon...")
        self.running = False

        # Stop camera
        if self.rs_camera:
            try:
                # RealSense doesn't have explicit stop in our wrapper
                self.rs_camera = None
            except Exception as e:
                error(f"Error stopping camera: {e}")

        # Cleanup shared memory
        self._destroy_shared_memory()

        success("Camera daemon stopped")

    def _create_shared_memory(self):
        """Create shared memory buffers for frames"""
        import os
        import stat

        status("Creating shared memory buffers...")

        try:
            # RGB buffer (640 * 480 * 3 * 1 byte = 921,600 bytes)
            rgb_size = np.prod(self.rgb_shape) * np.uint8().itemsize
            self.shm_rgb = shared_memory.SharedMemory(
                name="aaa_rgb_frame",
                create=True,
                size=rgb_size
            )
            # Set file descriptor permissions to allow all users to access
            # On macOS, we need to use fchmod on the file descriptor
            try:
                os.fchmod(self.shm_rgb._fd, 0o644)  # rw-r--r--
            except (AttributeError, OSError) as e:
                status(f"  Warning: Could not set RGB permissions: {e}")
            status(f"  RGB buffer: {rgb_size:,} bytes")

            # Depth buffer (640 * 480 * 2 bytes = 614,400 bytes)
            depth_size = np.prod(self.depth_shape) * np.uint16().itemsize
            self.shm_depth = shared_memory.SharedMemory(
                name="aaa_depth_frame",
                create=True,
                size=depth_size
            )
            # Set file descriptor permissions to allow all users to access
            try:
                os.fchmod(self.shm_depth._fd, 0o644)  # rw-r--r--
            except (AttributeError, OSError) as e:
                status(f"  Warning: Could not set depth permissions: {e}")
            status(f"  Depth buffer: {depth_size:,} bytes")

            # Metadata buffer (4 KB for JSON)
            self.shm_metadata = shared_memory.SharedMemory(
                name="aaa_metadata",
                create=True,
                size=4096
            )
            # Set file descriptor permissions to allow all users to access
            try:
                os.fchmod(self.shm_metadata._fd, 0o644)  # rw-r--r--
            except (AttributeError, OSError) as e:
                status(f"  Warning: Could not set metadata permissions: {e}")
            status(f"  Metadata buffer: 4,096 bytes")

            success("Shared memory buffers created with world-readable permissions")

        except FileExistsError:
            error("Shared memory already exists - is daemon already running?")
            error("Clean up with: python scripts/cleanup_shared_memory.py")
            raise

    def _destroy_shared_memory(self):
        """Cleanup shared memory buffers"""
        status("Cleaning up shared memory...")

        if self.shm_rgb:
            try:
                self.shm_rgb.close()
                self.shm_rgb.unlink()
            except Exception as e:
                error(f"Error cleaning RGB buffer: {e}")

        if self.shm_depth:
            try:
                self.shm_depth.close()
                self.shm_depth.unlink()
            except Exception as e:
                error(f"Error cleaning depth buffer: {e}")

        if self.shm_metadata:
            try:
                self.shm_metadata.close()
                self.shm_metadata.unlink()
            except Exception as e:
                error(f"Error cleaning metadata buffer: {e}")

        success("Shared memory cleaned up")

    def _initialize_camera(self):
        """Initialize RealSense camera (requires sudo on macOS)"""
        status("Initializing RealSense camera...")

        try:
            from aaa_core.hardware.realsense_camera import RealsenseCamera

            self.rs_camera = RealsenseCamera()
            success(f"RealSense camera initialized")

        except Exception as e:
            error(f"Failed to initialize RealSense camera: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _capture_loop(self):
        """Capture frames and write to shared memory"""
        status("Starting capture loop...")
        success(f"Camera daemon running - press Ctrl+C to stop")

        # Create numpy views into shared memory (zero-copy access)
        rgb_array = np.ndarray(
            self.rgb_shape,
            dtype=np.uint8,
            buffer=self.shm_rgb.buf
        )

        depth_array = np.ndarray(
            self.depth_shape,
            dtype=np.uint16,
            buffer=self.shm_depth.buf
        )

        last_status_time = time.time()

        while self.running:
            try:
                # Capture frame from RealSense
                ret, rgb_frame, depth_frame = self.rs_camera.get_frame_stream()

                if ret and rgb_frame is not None and depth_frame is not None:
                    # Write directly to shared memory (zero-copy)
                    # Note: RGB frames are in BGR format from RealSense
                    rgb_array[:] = rgb_frame
                    depth_array[:] = depth_frame

                    # Update metadata
                    current_time = time.time()
                    fps = self.frame_count / (current_time - self.start_time) if self.frame_count > 0 else 0.0

                    metadata = {
                        "timestamp": current_time,
                        "frame_number": self.frame_count,
                        "fps": round(fps, 2),
                        "detection_mode": self.detection_mode,
                        "num_detections": 0,
                        "camera_type": "realsense",
                        "resolution": f"{self.rgb_shape[1]}x{self.rgb_shape[0]}"
                    }

                    # Write metadata as JSON
                    metadata_bytes = json.dumps(metadata).encode('utf-8')
                    # Pad with zeros to avoid reading stale data
                    padded_metadata = metadata_bytes + b'\x00' * (4096 - len(metadata_bytes))
                    self.shm_metadata.buf[:4096] = padded_metadata[:4096]

                    self.frame_count += 1

                    # Print status every 5 seconds
                    if current_time - last_status_time >= 5.0:
                        print(f"Daemon: {self.frame_count} frames captured, {fps:.1f} fps")
                        last_status_time = current_time

                else:
                    error("Failed to capture frame")
                    time.sleep(0.1)  # Avoid busy loop on error

            except Exception as e:
                error(f"Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)  # Avoid busy loop on error
