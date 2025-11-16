"""
UFactory Lite6 Robotic Arm Driver

Provides high-level interface to the UFactory Lite6 robotic arm
using the xArm Python SDK.
"""

import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Optional, Tuple

# Suppress xArm SDK version output during import
with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    from xarm.wrapper import XArmAPI


class Lite6Arm:
    """
    UFactory Lite6 robotic arm driver

    Provides position control, gripper control, and safety features
    for the Lite6 collaborative robot arm.
    """

    def __init__(self, ip: str, port: int = 502):
        """
        Initialize connection to Lite6 arm

        Args:
            ip: IP address of the Lite6 arm
            port: Port number (default: 502)
        """
        self.ip = ip
        self.port = port
        self.arm: Optional[XArmAPI] = None
        self.connected = False

        print(f"[Lite6] Initializing connection to {ip}:{port}...")

    def connect(self) -> bool:
        """
        Connect to the Lite6 arm

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Suppress xArm SDK stdout and stderr output during connection
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.arm = XArmAPI(self.ip, is_radian=False)

            # Check connection
            if self.arm.connected:
                # Get arm version info
                version = getattr(self.arm, 'version', 'Unknown')

                print(f"[Lite6] Connected to {self.ip}")
                print(f"[Lite6] Arm firmware version: {version}")

                # Enable motion
                self.arm.motion_enable(enable=True)
                self.arm.set_mode(0)  # Position mode
                self.arm.set_state(state=0)  # Ready state

                self.connected = True
                print(f"[Lite6] Arm ready for operation")
                return True
            else:
                print(f"[Lite6] Failed to connect to {self.ip}")
                return False

        except Exception as e:
            print(f"[Lite6] Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the arm"""
        if self.arm and self.connected:
            self.arm.disconnect()
            self.connected = False
            print("[Lite6] Disconnected")

    def move_to_position(
        self,
        x: float,
        y: float,
        z: float,
        roll: Optional[float] = None,
        pitch: Optional[float] = None,
        yaw: Optional[float] = None,
        speed: float = 100,
        wait: bool = True
    ) -> bool:
        """
        Move arm to specified position

        Args:
            x: X coordinate in mm
            y: Y coordinate in mm
            z: Z coordinate in mm
            roll: Roll angle in degrees (optional)
            pitch: Pitch angle in degrees (optional)
            yaw: Yaw angle in degrees (optional)
            speed: Movement speed (mm/s)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.arm:
            print("[Lite6] Not connected")
            return False

        try:
            # If orientation provided, use full 6-DOF position
            if roll is not None and pitch is not None and yaw is not None:
                code = self.arm.set_position(
                    x=x, y=y, z=z,
                    roll=roll, pitch=pitch, yaw=yaw,
                    speed=speed,
                    wait=wait
                )
                print(f"[Lite6] Moved to: x={x}, y={y}, z={z}, "
                      f"r={roll}, p={pitch}, y={yaw}")
            else:
                # Position only, maintain current orientation
                code = self.arm.set_position(
                    x=x, y=y, z=z,
                    speed=speed,
                    wait=wait
                )
                print(f"[Lite6] Moved to position: x={x}, y={y}, z={z}")

            if code == 0:
                return True
            else:
                print(f"[Lite6] Move failed with code: {code}")
                return False

        except Exception as e:
            print(f"[Lite6] Move error: {e}")
            return False

    def get_position(self) -> Optional[Tuple[float, float, float, float, float, float]]:
        """
        Get current arm position

        Returns:
            Tuple of (x, y, z, roll, pitch, yaw) in mm and degrees, or None if error
        """
        if not self.connected or not self.arm:
            return None

        try:
            code, position = self.arm.get_position()
            if code == 0 and len(position) >= 6:
                # Return full position: x, y, z, roll, pitch, yaw
                return (position[0], position[1], position[2],
                        position[3], position[4], position[5])
            return None
        except Exception as e:
            print(f"[Lite6] Get position error: {e}")
            return None

    def open_gripper(self, speed: int = 5000, wait: bool = True) -> bool:
        """
        Open the gripper

        Args:
            speed: Opening speed (pulse/s)
            wait: Wait for operation to complete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.arm:
            print("[Lite6] Not connected")
            return False

        try:
            code = self.arm.set_gripper_position(800, speed=speed, wait=wait)
            if code == 0:
                print("[Lite6] Gripper opened")
                return True
            else:
                print(f"[Lite6] Gripper open failed with code: {code}")
                return False
        except Exception as e:
            print(f"[Lite6] Gripper error: {e}")
            return False

    def close_gripper(self, speed: int = 5000, wait: bool = True) -> bool:
        """
        Close the gripper

        Args:
            speed: Closing speed (pulse/s)
            wait: Wait for operation to complete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.arm:
            print("[Lite6] Not connected")
            return False

        try:
            code = self.arm.set_gripper_position(0, speed=speed, wait=wait)
            if code == 0:
                print("[Lite6] Gripper closed")
                return True
            else:
                print(f"[Lite6] Gripper close failed with code: {code}")
                return False
        except Exception as e:
            print(f"[Lite6] Gripper error: {e}")
            return False

    def set_gripper_position(
        self,
        position: float,
        speed: int = 5000,
        wait: bool = True
    ) -> bool:
        """
        Set gripper to specific position

        Args:
            position: Position (0-800, where 0 is closed, 800 is open)
            speed: Movement speed (pulse/s)
            wait: Wait for operation to complete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.arm:
            print("[Lite6] Not connected")
            return False

        try:
            code = self.arm.set_gripper_position(position, speed=speed, wait=wait)
            if code == 0:
                print(f"[Lite6] Gripper set to position: {position}")
                return True
            else:
                print(f"[Lite6] Gripper set failed with code: {code}")
                return False
        except Exception as e:
            print(f"[Lite6] Gripper error: {e}")
            return False

    def get_gripper_position(self) -> Optional[float]:
        """
        Get current gripper position

        Returns:
            Gripper position (0-800) or None if error
        """
        if not self.connected or not self.arm:
            return None

        try:
            code, position = self.arm.get_gripper_position()
            if code == 0:
                return position
            return None
        except Exception as e:
            print(f"[Lite6] Get gripper position error: {e}")
            return None

    def home(self) -> bool:
        """
        Move arm to home position

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.arm:
            print("[Lite6] Not connected")
            return False

        try:
            code = self.arm.move_gohome(wait=True)
            if code == 0:
                print("[Lite6] Moved to home position")
                return True
            else:
                print(f"[Lite6] Home failed with code: {code}")
                return False
        except Exception as e:
            print(f"[Lite6] Home error: {e}")
            return False

    def emergency_stop(self):
        """Emergency stop - immediately halt all motion"""
        if self.arm:
            try:
                self.arm.emergency_stop()
                print("[Lite6] EMERGENCY STOP")
            except Exception as e:
                print(f"[Lite6] Emergency stop error: {e}")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
