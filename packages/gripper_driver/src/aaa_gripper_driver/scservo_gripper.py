"""
Waveshare SC Servo Gripper Driver

Provides high-level interface to Waveshare SC series servos (SC09/SC15)
connected via the Bus Servo Adapter (A) for gripper control.
"""

from dataclasses import dataclass
from typing import Optional
import time

# Import vendored SDK
from aaa_gripper_driver.vendor import PortHandler, scscl, COMM_SUCCESS, SDK_AVAILABLE


@dataclass
class GripperConfig:
    """Configuration for SCServoGripper

    Position values are in raw servo units (0-4095 for 12-bit resolution).
    Percentage values are 0-100.
    """
    # Position range (calibrate for your gripper mechanism)
    min_position: int = 0       # Fully closed position
    max_position: int = 4095    # Fully open position

    # Preset positions (percentage of range, 0=closed, 100=open)
    preset_full: int = 100      # Full open
    preset_wide: int = 75       # Wide open
    preset_medium: int = 50     # Medium open
    preset_narrow: int = 25     # Narrow open
    preset_point: int = 15      # Point mode (single finger extended)
    preset_push: int = 0        # Push mode (fully closed)

    # Speed presets for force simulation (lower speed = gentler grip)
    speed_soft: int = 500       # Soft/slow grip
    speed_medium: int = 1500    # Medium grip
    speed_firm: int = 3000      # Firm/fast grip

    # Default movement speed
    default_speed: int = 2000   # Servo speed units

    # Default movement time (0 = speed-controlled)
    default_time: int = 0

    # Timeouts
    move_timeout: float = 5.0   # Seconds to wait for movement


class SCServoGripper:
    """
    Waveshare SC Servo Gripper driver

    Provides position control, preset positions, speed-based force control,
    and special modes (point, push) for the gripper.

    Note: SC series servos don't have software torque limiting. Force control
    is simulated by using slower speeds for gentler grips.
    """

    # SC Servo control table addresses (for SCSCL protocol)
    ADDR_TORQUE_ENABLE = 40
    ADDR_PRESENT_POSITION = 56
    ADDR_PRESENT_SPEED = 58
    ADDR_PRESENT_LOAD = 60
    ADDR_MOVING = 66

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 1000000,
        servo_id: int = 1,
        config: Optional[GripperConfig] = None
    ):
        """
        Initialize SC Servo Gripper driver

        Args:
            port: Serial port name
            baudrate: Serial baudrate (default: 1000000)
            servo_id: Servo ID on the bus (default: 1)
            config: Gripper configuration (uses defaults if None)
        """
        if not SDK_AVAILABLE:
            raise ImportError(
                "scservo_sdk not installed. Download from: "
                "https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A) "
                "and copy scservo_sdk folder to vendor/"
            )

        self.port = port
        self.baudrate = baudrate
        self.servo_id = servo_id
        self.config = config or GripperConfig()

        self._port_handler: Optional[PortHandler] = None
        self._servo: Optional[scscl] = None
        self.connected = False

        print(f"[Gripper] Initializing on {port} @ {baudrate} baud, servo ID {servo_id}")

    def connect(self) -> bool:
        """
        Connect to the servo

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._port_handler = PortHandler(self.port)
            if not self._port_handler.openPort():
                print(f"[Gripper] Failed to open port {self.port}")
                return False

            if not self._port_handler.setBaudRate(self.baudrate):
                print(f"[Gripper] Failed to set baudrate {self.baudrate}")
                self._port_handler.closePort()
                return False

            self._servo = scscl(self._port_handler)

            # Ping servo to verify connection
            # ping() returns (model_number, comm_result, error)
            model_number, comm_result, error = self._servo.ping(self.servo_id)
            if comm_result != COMM_SUCCESS:
                print(f"[Gripper] Servo ID {self.servo_id} not responding")
                self._port_handler.closePort()
                return False

            print(f"[Gripper] Connected to servo ID {self.servo_id}, model: {model_number}")

            # Enable torque
            comm_result, error = self._servo.write1ByteTxRx(
                self.servo_id, self.ADDR_TORQUE_ENABLE, 1
            )
            if comm_result != COMM_SUCCESS:
                print(f"[Gripper] Warning: Could not enable torque")

            self.connected = True
            print(f"[Gripper] Ready for operation")
            return True

        except Exception as e:
            print(f"[Gripper] Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from the servo"""
        if self._port_handler and self.connected:
            # Disable torque before disconnecting
            if self._servo:
                try:
                    self._servo.write1ByteTxRx(
                        self.servo_id, self.ADDR_TORQUE_ENABLE, 0
                    )
                except Exception:
                    pass
            self._port_handler.closePort()
            self.connected = False
            print("[Gripper] Disconnected")

    def emergency_stop(self):
        """Emergency stop - disable torque immediately"""
        if self._servo and self.connected:
            try:
                self._servo.write1ByteTxRx(
                    self.servo_id, self.ADDR_TORQUE_ENABLE, 0
                )
                print("[Gripper] EMERGENCY STOP - torque disabled")
            except Exception as e:
                print(f"[Gripper] Emergency stop error: {e}")

    # -------------------------------------------------------------------------
    # Position Control
    # -------------------------------------------------------------------------

    def _percent_to_position(self, percent: float) -> int:
        """Convert percentage (0-100) to raw position"""
        percent = max(0.0, min(100.0, percent))
        range_size = self.config.max_position - self.config.min_position
        return int(self.config.min_position + (percent / 100.0) * range_size)

    def _position_to_percent(self, position: int) -> float:
        """Convert raw position to percentage (0-100)"""
        range_size = self.config.max_position - self.config.min_position
        if range_size == 0:
            return 0.0
        percent = ((position - self.config.min_position) / range_size) * 100.0
        return max(0.0, min(100.0, percent))

    def set_position(
        self,
        position: int,
        speed: Optional[int] = None,
        time_ms: Optional[int] = None,
        wait: bool = True
    ) -> bool:
        """
        Move to raw servo position

        Args:
            position: Target position (0-4095)
            speed: Movement speed (uses default if None)
            time_ms: Movement time in ms (0 = use speed, uses default if None)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self._servo:
            print("[Gripper] Not connected")
            return False

        speed = speed if speed is not None else self.config.default_speed
        time_ms = time_ms if time_ms is not None else self.config.default_time
        position = max(0, min(4095, position))

        try:
            # Use WritePos which writes position, time, and speed together
            comm_result, error = self._servo.WritePos(
                self.servo_id, position, time_ms, speed
            )

            if comm_result != COMM_SUCCESS:
                print(f"[Gripper] Write position failed: {self._servo.getTxRxResult(comm_result)}")
                return False

            if wait:
                return self._wait_for_move(position)

            return True

        except Exception as e:
            print(f"[Gripper] Set position error: {e}")
            return False

    def set_position_percent(
        self,
        percent: float,
        speed: Optional[int] = None,
        wait: bool = True
    ) -> bool:
        """
        Move to position as percentage of range

        Args:
            percent: Target position (0=closed, 100=open)
            speed: Movement speed (uses default if None)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        position = self._percent_to_position(percent)
        result = self.set_position(position, speed=speed, wait=wait)
        if result:
            print(f"[Gripper] Moved to {percent:.1f}%")
        return result

    def get_position(self) -> Optional[int]:
        """
        Get current raw servo position

        Returns:
            Current position (0-4095) or None if error
        """
        if not self.connected or not self._servo:
            return None

        try:
            # ReadPos returns (position, comm_result, error)
            position, comm_result, error = self._servo.ReadPos(self.servo_id)
            if comm_result != COMM_SUCCESS:
                return None
            return position
        except Exception as e:
            print(f"[Gripper] Get position error: {e}")
            return None

    def get_position_percent(self) -> Optional[float]:
        """
        Get current position as percentage

        Returns:
            Current position (0-100) or None if error
        """
        position = self.get_position()
        if position is None:
            return None
        return self._position_to_percent(position)

    def is_moving(self) -> bool:
        """Check if servo is currently moving"""
        if not self.connected or not self._servo:
            return False

        try:
            moving, comm_result, error = self._servo.ReadMoving(self.servo_id)
            if comm_result != COMM_SUCCESS:
                return False
            return moving == 1
        except Exception:
            return False

    def _wait_for_move(self, target: int, tolerance: int = 20) -> bool:
        """Wait for servo to reach target position"""
        start_time = time.time()
        while time.time() - start_time < self.config.move_timeout:
            current = self.get_position()
            if current is not None and abs(current - target) <= tolerance:
                return True
            # Also check if servo stopped moving
            if not self.is_moving():
                current = self.get_position()
                if current is not None and abs(current - target) <= tolerance:
                    return True
            time.sleep(0.05)
        print("[Gripper] Move timeout")
        return False

    # -------------------------------------------------------------------------
    # Preset Positions
    # -------------------------------------------------------------------------

    def open_full(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """Open gripper fully (100%)"""
        print("[Gripper] Opening full...")
        return self.set_position_percent(self.config.preset_full, speed, wait)

    def open_wide(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """Open gripper wide (75% by default)"""
        print("[Gripper] Opening wide...")
        return self.set_position_percent(self.config.preset_wide, speed, wait)

    def open_medium(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """Open gripper medium (50% by default)"""
        print("[Gripper] Opening medium...")
        return self.set_position_percent(self.config.preset_medium, speed, wait)

    def open_narrow(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """Open gripper narrow (25% by default)"""
        print("[Gripper] Opening narrow...")
        return self.set_position_percent(self.config.preset_narrow, speed, wait)

    def close(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """Close gripper fully (0%)"""
        print("[Gripper] Closing...")
        return self.set_position_percent(0, speed, wait)

    # -------------------------------------------------------------------------
    # Force-Controlled Gripping (via speed control)
    # -------------------------------------------------------------------------

    def get_load(self) -> Optional[int]:
        """
        Get current load/torque reading

        Returns:
            Current load value or None if error
        """
        if not self.connected or not self._servo:
            return None

        try:
            # read2ByteTxRx returns (data, comm_result, error)
            load, comm_result, error = self._servo.read2ByteTxRx(
                self.servo_id, self.ADDR_PRESENT_LOAD
            )
            if comm_result != COMM_SUCCESS:
                return None
            return load
        except Exception as e:
            print(f"[Gripper] Get load error: {e}")
            return None

    def grip(
        self,
        force: str = "medium",
        wait: bool = True
    ) -> bool:
        """
        Close gripper with speed-based force control

        Uses different speeds to simulate force levels:
        - soft: slow closing speed
        - medium: moderate speed
        - firm: fast closing speed

        Note: SC series servos don't have software torque limiting,
        so force control is approximate based on speed.

        Args:
            force: Force level - "soft", "medium", or "firm"
            wait: Wait for grip to complete

        Returns:
            True if successful, False otherwise
        """
        # Map force levels to speeds
        speed_map = {
            "soft": self.config.speed_soft,
            "medium": self.config.speed_medium,
            "firm": self.config.speed_firm,
        }
        speed = speed_map.get(force.lower(), self.config.speed_medium)

        print(f"[Gripper] Gripping with {force} force (speed: {speed})...")

        # Close gripper with selected speed
        return self.close(speed=speed, wait=wait)

    def release(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """
        Release grip and open gripper

        Args:
            speed: Movement speed (uses default if None)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        return self.open_full(speed, wait)

    # -------------------------------------------------------------------------
    # Special Modes
    # -------------------------------------------------------------------------

    def point_mode(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """
        Enter point mode - single finger extended for pressing buttons/touchscreens

        This positions the gripper so one finger is extended while the other is retracted.

        Args:
            speed: Movement speed (uses default if None)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        print("[Gripper] Entering point mode...")
        return self.set_position_percent(self.config.preset_point, speed, wait)

    def push_mode(self, speed: Optional[int] = None, wait: bool = True) -> bool:
        """
        Enter push mode - gripper closed for pushing/sliding objects

        Args:
            speed: Movement speed (uses default if None)
            wait: Wait for movement to complete

        Returns:
            True if successful, False otherwise
        """
        print("[Gripper] Entering push mode...")
        return self.set_position_percent(self.config.preset_push, speed, wait)

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
