#!/usr/bin/env python3
"""
Test Unix domain socket IPC for cross-user communication
This tests if we can send camera frames from root daemon to user GUI
"""

import os
import socket
import struct
import sys
import time

import numpy as np

SOCKET_PATH = "/tmp/aaa_camera.sock"


def test_server():
    """Server (daemon) - runs as root"""
    print("Starting server (daemon mode)...")

    # Remove existing socket
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass

    # Create socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)

    # Set permissions so any user can connect
    os.chmod(SOCKET_PATH, 0o666)
    print(f"✓ Socket created at {SOCKET_PATH} with permissions 0666")

    server.listen(1)
    print("Waiting for client connection...")

    conn, addr = server.accept()
    print("✓ Client connected!")

    # Simulate sending camera frames
    frame_count = 0
    try:
        while frame_count < 10:
            # Create fake frame data (1280x720x3 RGB)
            rgb_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            depth_frame = np.random.randint(0, 5000, (720, 1280), dtype=np.uint16)

            # Serialize frame data
            rgb_bytes = rgb_frame.tobytes()
            depth_bytes = depth_frame.tobytes()

            # Send frame header: [rgb_size, depth_size]
            header = struct.pack('II', len(rgb_bytes), len(depth_bytes))
            conn.sendall(header)

            # Send RGB frame
            conn.sendall(rgb_bytes)

            # Send depth frame
            conn.sendall(depth_bytes)

            frame_count += 1
            print(f"Sent frame {frame_count} (RGB: {len(rgb_bytes)} bytes, Depth: {len(depth_bytes)} bytes)")
            time.sleep(0.033)  # ~30 fps

    except BrokenPipeError:
        print("Client disconnected")
    finally:
        conn.close()
        server.close()
        os.unlink(SOCKET_PATH)
        print("✓ Server shutdown")


def test_client():
    """Client (GUI) - runs as regular user"""
    print("Starting client (GUI mode)...")

    # Wait for socket to exist
    for i in range(10):
        if os.path.exists(SOCKET_PATH):
            break
        print(f"Waiting for socket... ({i+1}/10)")
        time.sleep(0.5)
    else:
        print("✗ Socket not found!")
        return False

    # Connect to socket
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        print("✓ Connected to daemon!")
    except PermissionError as e:
        print(f"✗ Permission denied: {e}")
        return False
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

    # Receive frames
    frame_count = 0
    try:
        while frame_count < 10:
            # Receive header
            header_data = b''
            while len(header_data) < 8:
                chunk = client.recv(8 - len(header_data))
                if not chunk:
                    break
                header_data += chunk

            if len(header_data) < 8:
                break

            rgb_size, depth_size = struct.unpack('II', header_data)

            # Receive RGB frame
            rgb_data = b''
            while len(rgb_data) < rgb_size:
                chunk = client.recv(rgb_size - len(rgb_data))
                if not chunk:
                    break
                rgb_data += chunk

            # Receive depth frame
            depth_data = b''
            while len(depth_data) < depth_size:
                chunk = client.recv(depth_size - len(depth_data))
                if not chunk:
                    break
                depth_data += chunk

            # Reconstruct frames
            rgb_frame = np.frombuffer(rgb_data, dtype=np.uint8).reshape(720, 1280, 3)
            depth_frame = np.frombuffer(depth_data, dtype=np.uint16).reshape(720, 1280)

            frame_count += 1
            print(f"✓ Received frame {frame_count} - RGB shape: {rgb_frame.shape}, Depth shape: {depth_frame.shape}")

    except Exception as e:
        print(f"✗ Error receiving frames: {e}")
        return False
    finally:
        client.close()

    print(f"✓ Successfully received {frame_count} frames!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Server (daemon): sudo python test_ipc_socket.py server")
        print("  Client (GUI):    python test_ipc_socket.py client")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "server":
        if os.geteuid() != 0:
            print("✗ Server must run as root (use sudo)")
            sys.exit(1)
        test_server()
    elif mode == "client":
        success = test_client()
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
