#!/usr/bin/env python3
"""
Cleanup Daemon Resources
Removes stale socket if daemon crashes

Usage:
    python scripts/cleanup_shared_memory.py
"""

import os

SOCKET_PATH = "/tmp/aaa_camera.sock"


def cleanup():
    """Remove daemon socket file"""
    cleaned = 0

    if os.path.exists(SOCKET_PATH):
        try:
            os.unlink(SOCKET_PATH)
            print(f"✓ Cleaned up: {SOCKET_PATH}")
            cleaned += 1
        except Exception as e:
            print(f"✗ Error cleaning socket: {e}")
    else:
        print(f"  (socket not found: {SOCKET_PATH})")

    if cleaned > 0:
        print(f"\nCleaned up {cleaned} resource(s)")
    else:
        print("\nNo daemon resources found (daemon not running or already clean)")


if __name__ == "__main__":
    cleanup()
