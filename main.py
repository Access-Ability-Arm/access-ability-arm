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

from aaa_core.config.console import header, info, status, underline  # noqa: E402
from aaa_gui.flet.main_window import FletMainWindow  # noqa: E402


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
    args = parser.parse_args()

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
        ft.app(target=main, name="Access Ability Arm")
