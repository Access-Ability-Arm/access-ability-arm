"""
Camera Client - Reads frames from daemon's shared memory
Used by GUI running in user context (no sudo required)
"""

import json
import time
from multiprocessing import shared_memory

import numpy as np

from aaa_core.config.console import error, status, success


class CameraClient:
    """
    Reads camera frames from shared memory written by daemon

    This runs in user context (no sudo) and reads frames written by
    the daemon running with elevated privileges.

    Usage:
        client = CameraClient()
        rgb, depth, metadata = client.get_frame()
        # ... use frames ...
        client.disconnect()
    """

    def __init__(self):
        """Connect to daemon's shared memory"""
        self.shm_rgb = None
        self.shm_depth = None
        self.shm_metadata = None

        self.rgb_shape = (720, 1280, 3)
        self.depth_shape = (720, 1280)

        self.connected = False

        self._connect()

    def _connect(self):
        """Connect to daemon's shared memory buffers"""
        try:
            status("Connecting to camera daemon...")

            # Connect to existing shared memory (created by daemon)
            self.shm_rgb = shared_memory.SharedMemory(name="aaa_rgb_frame")
            self.shm_depth = shared_memory.SharedMemory(name="aaa_depth_frame")
            self.shm_metadata = shared_memory.SharedMemory(name="aaa_metadata")

            self.connected = True
            success("Connected to camera daemon")

        except FileNotFoundError:
            error("Camera daemon not running")
            error("Start daemon with: sudo python scripts/aaa_camera_daemon.py")
            error("Or use: make daemon-start")
            raise RuntimeError(
                "Camera daemon not running. "
                "Start with: sudo python scripts/aaa_camera_daemon.py"
            )

    def get_frame(self):
        """
        Read latest frame from shared memory

        Returns:
            tuple: (rgb_frame, depth_frame, metadata)
                - rgb_frame: numpy array (480, 640, 3) uint8, BGR format
                - depth_frame: numpy array (480, 640) uint16, depth in mm
                - metadata: dict with frame info

        Raises:
            RuntimeError: If not connected to daemon
        """
        if not self.connected:
            raise RuntimeError("Not connected to daemon")

        try:
            # Create numpy views into shared memory (no copy - fast!)
            rgb_view = np.ndarray(
                self.rgb_shape,
                dtype=np.uint8,
                buffer=self.shm_rgb.buf
            )

            depth_view = np.ndarray(
                self.depth_shape,
                dtype=np.uint16,
                buffer=self.shm_depth.buf
            )

            # Copy to avoid data tearing (daemon writing while we read)
            # This is very fast (~2-3ms for both frames)
            rgb_frame = rgb_view.copy()
            depth_frame = depth_view.copy()

            # Read metadata
            metadata_bytes = bytes(self.shm_metadata.buf[:4096])

            # Find null terminator
            null_idx = metadata_bytes.find(b'\x00')
            if null_idx > 0:
                metadata_bytes = metadata_bytes[:null_idx]

            # Parse JSON
            try:
                metadata = json.loads(metadata_bytes.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If metadata is corrupted, return empty dict
                metadata = {}

            return rgb_frame, depth_frame, metadata

        except Exception as e:
            error(f"Error reading frame: {e}")
            raise

    def is_daemon_running(self):
        """
        Check if daemon is running by attempting to access shared memory

        Returns:
            bool: True if daemon is running, False otherwise
        """
        try:
            shm = shared_memory.SharedMemory(name="aaa_rgb_frame")
            shm.close()
            return True
        except FileNotFoundError:
            return False

    def reconnect(self):
        """
        Reconnect to daemon after it was restarted

        Raises:
            RuntimeError: If daemon is not running
        """
        self.disconnect()
        time.sleep(0.5)
        self._connect()

    def disconnect(self):
        """Cleanup shared memory connections"""
        status("Disconnecting from camera daemon...")

        if self.shm_rgb:
            try:
                self.shm_rgb.close()
            except Exception as e:
                error(f"Error closing RGB buffer: {e}")

        if self.shm_depth:
            try:
                self.shm_depth.close()
            except Exception as e:
                error(f"Error closing depth buffer: {e}")

        if self.shm_metadata:
            try:
                self.shm_metadata.close()
            except Exception as e:
                error(f"Error closing metadata buffer: {e}")

        self.connected = False
        success("Disconnected from camera daemon")

    def __del__(self):
        """Cleanup on object destruction"""
        if self.connected:
            self.disconnect()
