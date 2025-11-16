#!/usr/bin/env python3
"""
Access Ability Arm Camera Daemon
Runs with elevated privileges to access RealSense camera
Writes frames to shared memory for GUI consumption

Usage:
    sudo python scripts/aaa_camera_daemon.py

    Or use the control script:
    ./scripts/daemon_control.sh start
"""

import os
import sys

# Add packages to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
packages_core = os.path.join(project_root, 'packages', 'core', 'src')
sys.path.insert(0, packages_core)

from aaa_core.config.console import error, header, info, status
from aaa_core.daemon.camera_daemon_socket import CameraDaemonSocket


def check_privileges():
    """Check if running with root/sudo privileges"""
    if os.name == 'posix':  # Unix/Linux/macOS
        if os.geteuid() != 0:
            print("\n" + "="*70)
            error("ERROR: Camera daemon requires elevated privileges")
            print("="*70)
            print("\nThe RealSense camera requires sudo for USB access on macOS.")
            print("\nPlease run with sudo:")
            print(f"  sudo python {sys.argv[0]}")
            print("\nOr use the control script:")
            print("  ./scripts/daemon_control.sh start")
            print("\nOr use the Makefile:")
            print("  make daemon-start")
            print("="*70 + "\n")
            return False
    return True


def main():
    """Main entry point"""
    # Print header
    header("Access Ability Arm - Camera Daemon")
    info("RealSense depth camera service")
    print()

    # Check privileges
    if not check_privileges():
        sys.exit(1)

    status("Starting daemon with elevated privileges")
    print()

    # Create and start daemon
    daemon = CameraDaemonSocket()

    try:
        daemon.start()
    except KeyboardInterrupt:
        print("\n")
        status("Shutting down on user request...")
        daemon.stop()
    except Exception as e:
        print("\n")
        error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        daemon.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
