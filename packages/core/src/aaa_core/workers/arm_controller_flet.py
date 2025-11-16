"""
Flet-compatible robotic arm controller.

Handles background communication with the UFactory Lite6 robotic arm
for use with Flet GUI (no PyQt6 dependency).
"""

import logging
import threading
from typing import Callable, Optional, Tuple

try:
    from aaa_lite6_driver import Lite6Arm
    LITE6_AVAILABLE = True
except ImportError:
    LITE6_AVAILABLE = False
    logging.warning("aaa_lite6_driver not available - arm control disabled")


logger = logging.getLogger(__name__)


class ArmControllerFlet:
    """
    Background arm controller for Flet applications.

    Uses callbacks instead of Qt signals for status updates.
    """

    def __init__(
            self,
            arm_ip: str,
            port: int = 502,
            on_connection_status: Optional[Callable[[bool, str], None]] = None,
            on_error: Optional[Callable[[str], None]] = None):
        """
        Initialize arm controller.

        Args:
            arm_ip: IP address of the Lite6 arm
            port: Port number (default: 502 for Modbus TCP)
            on_connection_status: Callback for connection status (connected, message)
            on_error: Callback for errors (error_message)
        """
        self.arm_ip = arm_ip
        self.port = port
        self.arm: Optional[Lite6Arm] = None
        self._lock = threading.Lock()

        # Callbacks
        self.on_connection_status = on_connection_status
        self.on_error = on_error

    def connect_arm(self) -> bool:
        """
        Connect to the Lite6 arm.

        Returns:
            True if connection successful, False otherwise
        """
        if not LITE6_AVAILABLE:
            self._emit_connection_status(False, "Lite6 driver not available")
            return False

        try:
            logger.info(f"Connecting to Lite6 arm at {self.arm_ip}:{self.port}")

            with self._lock:
                self.arm = Lite6Arm(self.arm_ip, self.port)

                if self.arm.connect():
                    self._emit_connection_status(
                        True,
                        f"Connected to arm at {self.arm_ip}"
                    )
                    logger.info(f"Successfully connected to Lite6 arm at {self.arm_ip}")
                    return True
                else:
                    self._emit_connection_status(False, "Failed to connect to arm")
                    logger.error("Failed to connect to Lite6 arm")
                    return False

        except Exception as e:
            error_msg = f"Error connecting to arm: {str(e)}"
            self._emit_connection_status(False, error_msg)
            self._emit_error(error_msg)
            logger.error(error_msg, exc_info=True)
            return False

    def is_connected(self) -> bool:
        """
        Check if arm is currently connected.

        Returns:
            True if connected, False otherwise
        """
        with self._lock:
            return self.arm is not None and self.arm.connected

    def disconnect_arm(self):
        """Disconnect from the arm safely."""
        with self._lock:
            if self.arm and self.arm.connected:
                try:
                    self.arm.disconnect()
                    self._emit_connection_status(False, "Disconnected from arm")
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
        with self._lock:
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
                self._emit_error(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

    def get_position(self) -> Optional[Tuple[float, ...]]:
        """
        Get current arm position.

        Returns:
            Tuple of (x, y, z, roll, pitch, yaw) or None if unavailable
        """
        with self._lock:
            if not self.arm or not self.arm.connected:
                return None

            try:
                return self.arm.get_position()
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
        with self._lock:
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
                self._emit_error(error_msg)
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
        with self._lock:
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
                self._emit_error(error_msg)
                logger.error(error_msg, exc_info=True)
                return False

    def emergency_stop(self) -> bool:
        """
        Emergency stop - immediately halt all movement.

        Returns:
            True if command sent successfully, False otherwise
        """
        with self._lock:
            if not self.arm or not self.arm.connected:
                return False

            try:
                success = self.arm.emergency_stop()
                logger.warning("Emergency stop triggered")
                return success
            except Exception as e:
                logger.error(f"Error during emergency stop: {e}", exc_info=True)
                return False

    def _emit_connection_status(self, connected: bool, message: str):
        """Emit connection status via callback"""
        if self.on_connection_status:
            try:
                self.on_connection_status(connected, message)
            except Exception as e:
                logger.error(f"Error in connection status callback: {e}")

    def _emit_error(self, error_message: str):
        """Emit error via callback"""
        if self.on_error:
            try:
                self.on_error(error_message)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
