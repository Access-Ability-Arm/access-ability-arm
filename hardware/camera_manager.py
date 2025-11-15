"""
Camera Detection and Management
Enumerates available cameras and provides camera switching functionality
"""

import asyncio
import platform
from typing import Dict, List

import cv2

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
        print("Camera manager initialized")
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
            return self.cameras

        self.cameras = self._add_camera_information(camera_indexes)

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
            # For macOS and Linux, use generic camera names
            for camera_index in camera_indexes:
                camera_name = f"Camera {camera_index}"
                cameras.append(
                    {"camera_index": camera_index, "camera_name": camera_name}
                )

        return cameras

    async def _get_camera_information_for_windows(self):
        """Get detailed camera information on Windows platform"""
        return await windows_devices.DeviceInformation.find_all_async(VIDEO_DEVICES)
