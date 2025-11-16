"""
Camera Detection and Management
Enumerates available cameras and provides camera switching functionality
"""

import asyncio
import os
import platform
import re
import subprocess
import sys
from contextlib import contextmanager
from typing import Dict, List

import cv2

from aaa_core.config.console import success, underline
from aaa_core.config.console import warning as warn_msg

# Suppress OpenCV warnings during camera enumeration
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'


@contextmanager
def suppress_output():
    """Suppress all output including system-level warnings"""
    # Save original file descriptors
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()

    # Save copies of the original file descriptors
    with os.fdopen(os.dup(stdout_fd), 'w') as stdout_copy, \
         os.fdopen(os.dup(stderr_fd), 'w') as stderr_copy:

        # Redirect stdout and stderr to devnull
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, stdout_fd)
            os.dup2(devnull, stderr_fd)
            yield
        finally:
            # Restore original file descriptors
            os.dup2(stdout_copy.fileno(), stdout_fd)
            os.dup2(stderr_copy.fileno(), stderr_fd)
            os.close(devnull)


if platform.system() == "Windows":
    import winsdk.windows.devices.enumeration as windows_devices

VIDEO_DEVICES = 4  # Windows camera device type


class CameraManager:
    """Manages camera detection and enumeration"""

    def __init__(self, max_cameras_to_check: int = 3):
        """
        Initialize camera manager

        Args:
            max_cameras_to_check: Maximum number of camera indices to check
        """
        print(f"[DEBUG CameraManager] __init__ called with max_cameras={max_cameras_to_check}")
        self.max_cameras_to_check = max_cameras_to_check
        self.cameras: List[Dict[str, any]] = []
        self._macos_camera_names = None  # Cache for macOS camera names
        print("[DEBUG CameraManager] __init__ complete")

    def get_camera_info(self) -> List[Dict[str, any]]:
        """
        Get information about all available cameras

        Returns:
            List of dictionaries with camera_index and camera_name
        """
        self.cameras = []

        camera_indexes = self._get_camera_indexes()

        if len(camera_indexes) == 0:
            warn_msg("No cameras detected")
            return self.cameras

        self.cameras = self._add_camera_information(camera_indexes)

        # Print detected cameras
        if len(self.cameras) > 0:
            camera_names = [underline(c['camera_name']) for c in self.cameras]
            camera_list = ', '.join(camera_names)
            success(f"Detected {underline(str(len(self.cameras)))} camera(s): {camera_list}")

        return self.cameras

    def _get_camera_indexes(self) -> List[int]:
        """
        Find all available camera indices

        Returns:
            List of camera indices that are accessible
        """
        index = 0
        camera_indexes = []
        remaining_checks = self.max_cameras_to_check

        # Use low-level file descriptor suppression to hide all warnings
        # including macOS AVCaptureDevice system warnings
        with suppress_output():
            while remaining_checks > 0:
                capture = cv2.VideoCapture(index)
                if capture.read()[0]:
                    camera_indexes.append(index)
                    capture.release()
                index += 1
                remaining_checks -= 1

        return camera_indexes

    def _add_camera_information(
        self, camera_indexes: List[int]
    ) -> List[Dict[str, any]]:
        """
        Add platform-specific camera names to indices

        Args:
            camera_indexes: List of camera indices

        Returns:
            List of dictionaries with camera_index and camera_name
        """
        platform_name = platform.system()
        cameras = []

        if platform_name == "Windows":
            cameras_info_windows = asyncio.run(
                self._get_camera_information_for_windows()
            )

            for camera_index in camera_indexes:
                if camera_index < len(cameras_info_windows):
                    camera_name = cameras_info_windows.get_at(
                        camera_index
                    ).name.replace("\n", "")
                    cameras.append(
                        {"camera_index": camera_index, "camera_name": camera_name}
                    )
        else:
            # For macOS and Linux, try to get actual camera names
            for camera_index in camera_indexes:
                camera_name = self._get_camera_name_opencv(camera_index)
                cameras.append(
                    {"camera_index": camera_index, "camera_name": camera_name}
                )

        return cameras

    def _get_camera_name_opencv(self, camera_index: int) -> str:
        """
        Get camera name using OpenCV backend properties (macOS/Linux)

        Args:
            camera_index: Camera index

        Returns:
            Camera name or generic fallback
        """
        try:
            # Suppress output during camera name retrieval
            with suppress_output():
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    # Try to get camera name using CAP_PROP_BACKEND property
                    # This works on some OpenCV builds
                    camera_name = None

                    # macOS: Use system_profiler to get actual camera names
                    if platform.system() == "Darwin":
                        macos_names = self._get_macos_camera_names()
                        if camera_index < len(macos_names):
                            camera_name = macos_names[camera_index]
                        else:
                            camera_name = f"Camera {camera_index}"
                    else:
                        # Linux - use Video4Linux naming
                        camera_name = f"Video Device {camera_index}"

                    cap.release()
                    return camera_name
        except Exception:
            pass

        # Fallback to generic name
        return f"Camera {camera_index}"

    def _get_macos_camera_names(self) -> List[str]:
        """
        Get actual camera names on macOS using system_profiler

        Returns:
            List of camera names in order they appear in system_profiler
        """
        if self._macos_camera_names is not None:
            return self._macos_camera_names

        try:
            # Run system_profiler to get camera information
            result = subprocess.run(
                ['system_profiler', 'SPCameraDataType'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # Suppress AVCaptureDeviceTypeExternal warning
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse camera names from output
                # Format is like:
                #   Intel(R) RealSense(TM) Depth Camera 435 with RGB Module RGB:
                #   MacBook Pro Camera:
                #   ckphone24 Camera:

                camera_names = []
                lines = result.stdout.split('\n')

                for line in lines:
                    # Look for lines ending with colon (camera names)
                    # Skip the "Camera:" header line
                    if ':' in line and not line.strip().startswith('Camera:'):
                        # Extract camera name (everything before the colon, trimmed)
                        camera_name = line.split(':')[0].strip()
                        # Skip empty lines and metadata lines (Model ID, Unique ID)
                        if camera_name and not camera_name.startswith('Model ID') and not camera_name.startswith('Unique ID'):
                            camera_names.append(camera_name)

                self._macos_camera_names = camera_names
                return camera_names
        except Exception:
            pass

        # Return empty list if detection fails
        self._macos_camera_names = []
        return []

    async def _get_camera_information_for_windows(self):
        """Get detailed camera information on Windows platform"""
        return await windows_devices.DeviceInformation.find_all_async(
            VIDEO_DEVICES
        )
