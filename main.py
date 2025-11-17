#!/usr/bin/env python3
"""
DE-GUI - Access Ability Arm
Cross-platform GUI for the Drane Engineering assistive robotic arm

Features:
- Real-time object detection and segmentation
- MediaPipe face landmark tracking
- RealSense depth sensing (optional)
- Manual robotic arm controls
- Cross-platform (desktop, web, mobile)
"""

import warnings

import flet as ft

# Suppress user warnings
warnings.simplefilter("ignore", UserWarning)

from aaa_core.config.console import (  # noqa: E402
    header,
    info,
    status,
    underline,
    warning,
)
from aaa_gui.flet.main_window import FletMainWindow  # noqa: E402


def _check_realsense_conflicts():
    """Check for other processes using RealSense camera and warn user"""
    import os
    import subprocess

    try:
        # Get current process PID
        current_pid = os.getpid()

        # Check for other processes using RealSense (macOS/Linux)
        if os.name == 'posix':
            result = subprocess.run(
                ['lsof', '-t', '-c', 'Python'],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                # Get all Python PIDs
                python_pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]

                # Check if any of these are using RealSense libraries
                conflicts = []
                for pid in python_pids:
                    if pid == current_pid:
                        continue

                    try:
                        # Check if this PID has RealSense library loaded
                        check_result = subprocess.run(
                            ['lsof', '-p', str(pid)],
                            capture_output=True,
                            text=True,
                            timeout=1
                        )

                        if 'realsense' in check_result.stdout.lower():
                            conflicts.append(pid)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        continue

                if conflicts:
                    warning("⚠️  Detected other processes using RealSense camera:")
                    for pid in conflicts:
                        try:
                            # Get process name
                            ps_result = subprocess.run(
                                ['ps', '-p', str(pid), '-o', 'command='],
                                capture_output=True,
                                text=True,
                                timeout=1
                            )
                            cmd = ps_result.stdout.strip()
                            print(f"    PID {pid}: {cmd[:80]}")
                        except:
                            print(f"    PID {pid}")

                    warning("⚠️  This may cause 'Frame didn't arrive' errors")
                    warning("⚠️  Kill these processes first:")
                    print(f"    kill -9 {' '.join(map(str, conflicts))}")
                    print()

                    # Give user a chance to cancel
                    import time
                    time.sleep(2)

    except Exception as e:
        # Silently ignore errors in conflict detection
        pass


def main(page: ft.Page):
    """
    Flet application entry point

    Args:
        page: Flet page object
    """
    # Create main window
    window = FletMainWindow(page)

    # Handle cleanup on close
    def on_window_close(e):
        window.cleanup()

    page.on_close = on_window_close


if __name__ == "__main__":
    # Parse command-line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description="Access Ability Arm - Assistive Robotic Arm Control"
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Run as web application in browser"
    )
    parser.add_argument(
        "--port", type=int, default=8550,
        help="Port for web server (default: 8550)"
    )
    parser.add_argument(
        "--enable-realsense", action="store_true",
        help="Enable RealSense camera support (may hang if camera not working properly)"
    )
    args = parser.parse_args()

    # Store RealSense override flag globally
    import sys
    sys._enable_realsense_override = args.enable_realsense

    # Check for RealSense conflicts
    from aaa_core.config.settings import app_config
    if app_config.realsense_available:
        _check_realsense_conflicts()

    # Run Flet app
    if args.web:
        header(
            f"Starting Access Ability Arm ({underline('Web version')})"
        )
        info(f"Open browser to: {underline(f'http://localhost:{args.port}')}")
        status("Press Ctrl+C to stop the server")
        ft.app(
            target=main, view=ft.AppView.WEB_BROWSER,
            port=args.port, name="Access Ability Arm"
        )
    else:
        header(
            f"Starting Access Ability Arm ({underline('Desktop version')})"
        )
        ft.app(target=main, name="Access Ability Arm")
