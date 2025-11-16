"""
Camera Detection and Management
Enumerates available cameras and provides camera switching functionality
"""

import asyncio
import os
import platform
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
        self.max_cameras_to_check = max_cameras_to_check
        self.cameras: List[Dict[str, any]] = []

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
                    # Try to get camera name from backend
                    # CAP_PROP_BACKEND_NAME available in newer OpenCV versions
                    if hasattr(cv2, 'CAP_PROP_BACKEND_NAME'):
                        backend_name = cap.get(cv2.CAP_PROP_BACKEND_NAME)  # noqa: F841

                    # For macOS, try to infer from common patterns
                    # OpenCV doesn't expose camera names directly, so we use heuristics
                    if platform.system() == "Darwin":
                        # Camera 0 is usually built-in FaceTime
                        # Camera 1+ are usually external or Continuity Camera
                        if camera_index == 0:
                            camera_name = "FaceTime HD Camera (Built-in)"
                        else:
                            camera_name = f"External Camera {camera_index}"
                    else:
                        # Linux - use Video4Linux naming
                        camera_name = f"Video Device {camera_index}"

                    cap.release()
                    return camera_name
        except Exception:
            pass

        # Fallback to generic name
        return f"Camera {camera_index}"

    async def _get_camera_information_for_windows(self):
        """Get detailed camera information on Windows platform"""
        return await windows_devices.DeviceInformation.find_all_async(
            VIDEO_DEVICES
        )
