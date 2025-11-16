"""
Robotic arm controller worker thread.

Handles background communication with the UFactory Lite6 robotic arm,
including connection management, movement commands, and gripper control.
"""

import logging
from typing import Optional, Tuple

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

try:
    from aaa_lite6_driver import Lite6Arm
    LITE6_AVAILABLE = True
except ImportError:
    LITE6_AVAILABLE = False
    logging.warning("aaa_lite6_driver not available - arm control disabled")


logger = logging.getLogger(__name__)


if PYQT_AVAILABLE:
    class ArmController(QThread):
        """
        Background thread for robotic arm control.

        Signals:
            connection_status: Emitted when connection status changes
                (connected: bool, message: str)
            position_update: Emitted when position is read
                (x, y, z, roll, pitch, yaw)
            error_occurred: Emitted when an error occurs
                (error_message: str)
        """

        # (connected, message)
        connection_status = pyqtSignal(bool, str)
        # [x, y, z, roll, pitch, yaw]
        position_update = pyqtSignal(list)
        # error message
        error_occurred = pyqtSignal(str)

        def __init__(self, arm_ip: str, port: int = 502):
            """
            Initialize arm controller.

            Args:
                arm_ip: IP address of the Lite6 arm
                port: Port number (default: 502 for Modbus TCP)
            """
            super().__init__()
            self.arm_ip = arm_ip
            self.port = port
            self.arm: Optional[Lite6Arm] = None
            self.running = False

        def connect_arm(self) -> bool:
            """
            Connect to the Lite6 arm.

            Returns:
                True if connection successful, False otherwise
            """
            if not LITE6_AVAILABLE:
                self.connection_status.emit(False, "Lite6 driver not available")
                return False

            try:
                logger.info(f"Connecting to Lite6 arm at {self.arm_ip}:{self.port}")
                self.arm = Lite6Arm(self.arm_ip, self.port)

                if self.arm.connect():
                    self.connection_status.emit(True, f"Connected to arm at {self.arm_ip}")
                    logger.info(f"Successfully connected to Lite6 arm at {self.arm_ip}")
                    return True
                else:
                    self.connection_status.emit(False, "Failed to connect to arm")
                    logger.error("Failed to connect to Lite6 arm")
                    return False

            except Exception as e:
                error_msg = f"Error connecting to arm: {str(e)}"
                self.connection_status.emit(False, error_msg)
                self.error_occurred.emit(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

        def disconnect_arm(self):
            """Disconnect from the arm safely."""
            if self.arm and self.arm.connected:
                try:
                    self.arm.disconnect()
                    self.connection_status.emit(False, "Disconnected from arm")
                    logger.info("Disconnected from Lite6 arm")
                except Exception as e:
                    logger.error(f"Error disconnecting from arm: {e}", exc_info=True)

        def move_to(
                self, x: float, y: float, z: float,
                roll: Optional[float] = None,
                pitch: Optional[float] = None,
                yaw: Optional[float] = None,
                speed: float = 100,
                wait: bool = False) -> bool:
            """
            Move arm to specified position.

            Args:
                x, y, z: Position coordinates in mm
                roll, pitch, yaw: Optional orientation in degrees
                speed: Movement speed (mm/s)
                wait: Whether to wait for movement to complete

            Returns:
                True if command sent successfully, False otherwise
            """
            if not self.arm or not self.arm.connected:
                logger.warning("Cannot move: arm not connected")
                return False

            try:
                if roll is not None and pitch is not None and yaw is not None:
                    success = self.arm.move_to_position(
                        x, y, z, roll, pitch, yaw, speed=speed, wait=wait
                    )
                else:
                    success = self.arm.move_to_position(
                        x, y, z, speed=speed, wait=wait
                    )

                if not success:
                    logger.warning(f"Move command failed: ({x}, {y}, {z})")

                return success

            except Exception as e:
                error_msg = f"Error moving arm: {str(e)}"
                self.error_occurred.emit(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

        def get_position(self) -> Optional[Tuple[float, ...]]:
            """
            Get current arm position.

            Returns:
                Tuple of (x, y, z, roll, pitch, yaw) or None if unavailable
            """
            if not self.arm or not self.arm.connected:
                return None

            try:
                pos = self.arm.get_position()
                if pos:
                    self.position_update.emit(list(pos))
                return pos
            except Exception as e:
                logger.error(f"Error getting position: {e}", exc_info=True)
                return None

        def set_gripper(self, position: int, speed: int = 5000, wait: bool = False) -> bool:
            """
            Set gripper position.

            Args:
                position: Gripper position (0=closed, 800=open)
                speed: Movement speed
                wait: Whether to wait for movement to complete

            Returns:
                True if command sent successfully, False otherwise
            """
            if not self.arm or not self.arm.connected:
                logger.warning("Cannot set gripper: arm not connected")
                return False

            try:
                success = self.arm.set_gripper_position(position, speed=speed, wait=wait)
                if not success:
                    logger.warning(f"Gripper command failed: position={position}")
                return success
            except Exception as e:
                error_msg = f"Error setting gripper: {str(e)}"
                self.error_occurred.emit(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

        def open_gripper(self, speed: int = 5000, wait: bool = False) -> bool:
            """Open the gripper fully."""
            return self.set_gripper(800, speed=speed, wait=wait)

        def close_gripper(self, speed: int = 5000, wait: bool = False) -> bool:
            """Close the gripper fully."""
            return self.set_gripper(0, speed=speed, wait=wait)

        def home(self) -> bool:
            """
            Move arm to home position.

            Returns:
                True if command sent successfully, False otherwise
            """
            if not self.arm or not self.arm.connected:
                logger.warning("Cannot home: arm not connected")
                return False

            try:
                success = self.arm.home()
                if not success:
                    logger.warning("Home command failed")
                return success
            except Exception as e:
                error_msg = f"Error homing arm: {str(e)}"
                self.error_occurred.emit(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

        def emergency_stop(self) -> bool:
            """
            Emergency stop - immediately halt all movement.

            Returns:
                True if command sent successfully, False otherwise
            """
            if not self.arm or not self.arm.connected:
                return False

            try:
                success = self.arm.emergency_stop()
                logger.warning("Emergency stop triggered")
                return success
            except Exception as e:
                logger.error(f"Error during emergency stop: {e}", exc_info=True)
                return False

        def stop(self):
            """Clean shutdown of the controller."""
            self.running = False
            self.disconnect_arm()
            self.quit()
            self.wait()
else:
    # Dummy class if PyQt6 not available
    class ArmController:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyQt6 required for ArmController")
