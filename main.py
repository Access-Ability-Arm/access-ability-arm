#!/usr/bin/env python3
"""
DE-GUI - Drane Engineering Assistive Robotic Arm GUI
Main application entry point

This application provides computer vision-powered control for an assistive
robotic arm, featuring:
- YOLOv11/v12 real-time object detection with Apple Metal GPU acceleration
- MediaPipe face landmark tracking
- RealSense depth sensing (optional)
- Manual robotic arm controls
"""

import sys
import warnings

from PyQt6 import QtWidgets

# Suppress user warnings
warnings.simplefilter("ignore", UserWarning)

# Windows COM initialization settings
sys.coinit_flags = 2

# Import main window after PyQt setup
from gui.main_window import MainWindow


def main():
    """Application entry point"""
    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
