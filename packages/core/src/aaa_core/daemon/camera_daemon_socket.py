"""
Camera Daemon - Runs with elevated privileges for RealSense access
Streams frames via Unix domain socket for GUI consumption
"""

import json
import os
import signal
import socket
import struct
import sys
import threading
import time

import numpy as np

from aaa_core.config.console import error, status, success, underline

SOCKET_PATH = "/tmp/aaa_camera.sock"
COMMAND_SOCKET_PATH = "/tmp/aaa_camera_cmd.sock"


class CameraDaemonSocket:
    """
    Daemon process for camera capture with elevated privileges

    Uses Unix domain socket for IPC instead of shared memory.
    This allows cross-user access on macOS (root daemon → user GUI).

    Manages:
    - RealSense camera initialization
    - Continuous frame capture
    - Socket server for streaming frames
    - Multiple client connections

    Frame Format (sent over socket):
    - Header: [rgb_size: uint32, depth_size: uint32, metadata_size: uint32]
    - RGB data: rgb_size bytes (720x1280x3 uint8, BGR from RealSense)
    - Depth data: depth_size bytes (720x1280 uint16)
    - Metadata: metadata_size bytes (JSON)
    """

    def __init__(self):
        """Initialize daemon (does not start capture)"""
        self.running = False

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

        # Socket server for frames
        self.server_socket = None
        self.client_sockets = []
        self.client_lock = threading.Lock()

        # Command socket for control
        self.command_socket = None
        self.command_thread = None

        # Latest frame (cached for new clients)
        self.latest_rgb = None
        self.latest_depth = None
        self.latest_metadata = {}
        self.frame_lock = threading.Lock()

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        status("Camera daemon initialized (socket mode)")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Initialize camera and socket, start capture loop"""
        try:
            status("Starting camera daemon...")

            # Set running flag BEFORE starting threads
            self.running = True
            self.start_time = time.time()

            # Create socket server
            self._create_socket()

            # Initialize RealSense camera
            self._initialize_camera()

            # Start client acceptor thread
            acceptor_thread = threading.Thread(target=self._accept_clients, daemon=True)
            acceptor_thread.start()

            # Start command listener thread
            self.command_thread = threading.Thread(target=self._command_listener, daemon=True)
            self.command_thread.start()

            # Start capture loop
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

        # Close all client connections
        with self.client_lock:
            for client in self.client_sockets:
                try:
                    client.close()
                except:
                    pass
            self.client_sockets.clear()

        # Close socket server
        self._destroy_socket()

        success("Camera daemon stopped")

    def _create_socket(self):
        """Create Unix domain socket server"""
        status("Creating socket server...")

        try:
            # Remove existing socket if present
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

            # Create socket
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(SOCKET_PATH)

            # Set permissions so any user can connect
            os.chmod(SOCKET_PATH, 0o666)

            # Listen for connections
            self.server_socket.listen(5)

            success(f"Socket server listening at {SOCKET_PATH}")

        except Exception as e:
            error(f"Failed to create socket: {e}")
            raise

    def _destroy_socket(self):
        """Cleanup socket server"""
        status("Cleaning up socket...")

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                error(f"Error closing socket: {e}")

        # Remove socket file
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

        # Cleanup command socket
        if self.command_socket:
            try:
                self.command_socket.close()
            except Exception as e:
                error(f"Error closing command socket: {e}")

        try:
            os.unlink(COMMAND_SOCKET_PATH)
        except OSError:
            pass

        success("Socket cleaned up")

    def _command_listener(self):
        """Listen for commands on command socket"""
        try:
            # Create command socket
            self.command_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

            # Remove old socket if exists
            try:
                os.unlink(COMMAND_SOCKET_PATH)
            except OSError:
                pass

            # Bind socket
            self.command_socket.bind(COMMAND_SOCKET_PATH)
            os.chmod(COMMAND_SOCKET_PATH, 0o666)

            success(f"Command socket listening at {COMMAND_SOCKET_PATH}")

            # Set timeout for checking running flag
            self.command_socket.settimeout(1.0)

            while self.running:
                try:
                    data, addr = self.command_socket.recvfrom(1024)
                    command = json.loads(data.decode('utf-8'))
                    self._handle_command(command)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        error(f"Error receiving command: {e}")

        except Exception as e:
            error(f"Command listener error: {e}")

    def _handle_command(self, command):
        """Handle a command from client"""
        cmd_type = command.get('command')

        if cmd_type == 'set_exposure':
            exposure_value = command.get('value')
            if exposure_value and self.rs_camera:
                if self.rs_camera.set_exposure(exposure_value):
                    status(f"✓ Exposure set to {exposure_value}")
                else:
                    error(f"✗ Failed to set exposure to {exposure_value}")
        else:
            error(f"Unknown command: {cmd_type}")

    def _accept_clients(self):
        """Accept client connections in background thread"""
        status("Ready to accept client connections...")

        while self.running:
            try:
                self.server_socket.settimeout(1.0)  # Check running flag every second
                client_socket, _ = self.server_socket.accept()

                with self.client_lock:
                    self.client_sockets.append(client_socket)

                status(f"Client connected (total: {len(self.client_sockets)})")

            except socket.timeout:
                continue  # Check running flag
            except Exception as e:
                if self.running:
                    error(f"Error accepting client: {e}")
                break

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
        """Capture frames and send to all connected clients"""
        status("Starting capture loop...")
        success(f"Camera daemon running - press Ctrl+C to stop")

        last_status_time = time.time()

        while self.running:
            try:
                # Capture frame from RealSense
                ret, rgb_frame, depth_frame = self.rs_camera.get_frame_stream()

                if ret and rgb_frame is not None and depth_frame is not None:
                    # Update frame counter
                    self.frame_count += 1
                    current_time = time.time()
                    fps = self.frame_count / (current_time - self.start_time) if self.frame_count > 0 else 0.0

                    # Create metadata
                    metadata = {
                        "frame_count": self.frame_count,
                        "timestamp": current_time,
                        "fps": fps,
                        "detection_mode": self.detection_mode,
                    }

                    # Cache latest frame (for new clients)
                    with self.frame_lock:
                        self.latest_rgb = rgb_frame.copy()
                        self.latest_depth = depth_frame.copy()
                        self.latest_metadata = metadata

                    # Send to all connected clients
                    self._broadcast_frame(rgb_frame, depth_frame, metadata)

                    # Status update every 5 seconds
                    if current_time - last_status_time >= 5.0:
                        print(f"Daemon: {self.frame_count} frames captured, {fps:.1f} fps")
                        last_status_time = current_time

            except Exception as e:
                error(f"Error in capture loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)  # Avoid busy loop on error

    def _broadcast_frame(self, rgb_frame, depth_frame, metadata):
        """Send frame to all connected clients"""
        # Serialize frame data
        rgb_bytes = rgb_frame.tobytes()
        depth_bytes = depth_frame.tobytes()
        metadata_bytes = json.dumps(metadata).encode('utf-8')

        # Create header: [rgb_size, depth_size, metadata_size]
        header = struct.pack('III', len(rgb_bytes), len(depth_bytes), len(metadata_bytes))

        # Combine into single message
        message = header + rgb_bytes + depth_bytes + metadata_bytes

        # Send to all clients (remove disconnected ones)
        with self.client_lock:
            disconnected = []
            for client in self.client_sockets:
                try:
                    client.sendall(message)
                except (BrokenPipeError, OSError):
                    disconnected.append(client)

            # Remove disconnected clients
            for client in disconnected:
                self.client_sockets.remove(client)
                try:
                    client.close()
                except:
                    pass

            if disconnected:
                status(f"{len(disconnected)} client(s) disconnected (remaining: {len(self.client_sockets)})")
