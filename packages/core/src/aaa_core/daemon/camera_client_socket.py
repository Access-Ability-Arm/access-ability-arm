"""
Camera Client - Reads frames from daemon's Unix socket
Used by GUI running in user context (no sudo required)
"""

import json
import socket
import struct
import time

import numpy as np

from aaa_core.config.console import error, status, success

SOCKET_PATH = "/tmp/aaa_camera.sock"


class CameraClientSocket:
    """
    Reads camera frames from Unix socket served by daemon

    This runs in user context (no sudo) and reads frames written by
    the daemon running with elevated privileges.

    Usage:
        client = CameraClientSocket()
        rgb, depth, metadata = client.get_frame()
        # ... use frames ...
        client.disconnect()
    """

    def __init__(self):
        """Connect to daemon's socket"""
        self.socket = None
        # Updated to match new camera configuration:
        # RGB: 1920x1080 @ 30 FPS, Depth: 848x480 @ 30 FPS
        # Aligned RGB: 848x480 @ 30 FPS (pixel-aligned to depth)
        self.rgb_shape = (1080, 1920, 3)
        self.depth_shape = (480, 848)
        self.aligned_color_shape = (480, 848, 3)
        self.connected = False

        self._connect()

    def _connect(self):
        """Connect to daemon's socket server"""
        try:
            status("Connecting to camera daemon...")

            # Create client socket
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(SOCKET_PATH)

            # Set timeout for receives
            self.socket.settimeout(1.0)

            self.connected = True
            success("✓ Connected to camera daemon (socket)")

        except FileNotFoundError:
            error(f"Daemon socket not found at {SOCKET_PATH}")
            error("Start daemon with: sudo make daemon-start")
            raise
        except PermissionError as e:
            error(f"Permission denied connecting to daemon: {e}")
            raise
        except Exception as e:
            error(f"Failed to connect to daemon: {e}")
            raise

    def get_frame(self):
        """
        Read latest frame from daemon

        Returns:
            Tuple of (rgb_frame, depth_frame, metadata, aligned_color)
            or (None, None, None, None) if error.
            aligned_color is None if daemon uses legacy 3-segment protocol.
        """
        if not self.connected:
            error("[CameraClient] Not connected!")
            return None, None, None, None

        try:
            # New 4-segment protocol: 16-byte header
            header_data = self._recv_exactly(16)
            if not header_data:
                error("[CameraClient] Failed to receive header")
                return None, None, None, None

            rgb_size, depth_size, aligned_rgb_size, metadata_size = struct.unpack(
                "IIII", header_data
            )

            # Receive RGB frame
            rgb_data = self._recv_exactly(rgb_size)
            if not rgb_data:
                return None, None, None, None

            # Receive depth frame
            depth_data = self._recv_exactly(depth_size)
            if not depth_data:
                return None, None, None, None

            # Receive aligned color frame (if present)
            aligned_color_frame = None
            if aligned_rgb_size > 0:
                aligned_color_data = self._recv_exactly(aligned_rgb_size)
                if not aligned_color_data:
                    return None, None, None, None
                aligned_color_frame = np.frombuffer(
                    aligned_color_data, dtype=np.uint8
                ).reshape(self.aligned_color_shape)

            # Receive metadata
            metadata_data = self._recv_exactly(metadata_size)
            if not metadata_data:
                return None, None, None, None

            # Reconstruct frames
            rgb_frame = np.frombuffer(rgb_data, dtype=np.uint8).reshape(self.rgb_shape)
            depth_frame = np.frombuffer(depth_data, dtype=np.uint16).reshape(
                self.depth_shape
            )

            # Parse metadata
            metadata = json.loads(metadata_data.decode("utf-8"))

            return rgb_frame, depth_frame, metadata, aligned_color_frame

        except socket.timeout:
            # Timeout waiting for frame (daemon might be slow)
            return None, None, None, None
        except Exception as e:
            error(f"Error receiving frame: {e}")
            self.connected = False
            return None, None, None, None

    def _recv_exactly(self, size):
        """Receive exactly size bytes from socket"""
        data = b""
        while len(data) < size:
            try:
                chunk = self.socket.recv(size - len(data))
                if not chunk:
                    # Connection closed
                    return None
                data += chunk
            except socket.timeout:
                # Timeout - return what we have (might be incomplete)
                return None if len(data) < size else data
        return data

    def disconnect(self):
        """Disconnect from daemon"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            self.connected = False
            status("Disconnected from camera daemon")

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
