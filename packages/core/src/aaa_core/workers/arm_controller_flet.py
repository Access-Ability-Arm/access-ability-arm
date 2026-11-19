"""
Flet-compatible robotic arm controller.

Supports both UFactory Lite6 (TCP/IP) and Seeed Studio reBot Arm B601
(serial/CAN).  The arm_type constructor argument selects which driver is
instantiated; all subsequent calls go through the same interface.
"""

import logging
import threading
from typing import Callable, Optional, Tuple

try:
    from aaa_lite6_driver import Lite6Arm
    LITE6_AVAILABLE = True
except ImportError:
    LITE6_AVAILABLE = False
    logging.warning("aaa_lite6_driver not available")

try:
    from aaa_b601_driver import B601Arm
    B601_AVAILABLE = True
except ImportError:
    B601_AVAILABLE = False
    logging.warning("aaa_b601_driver not available")


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
            arm_type: str = "lite6",
            serial_port: str = "/dev/ttyACM0",
            on_connection_status: Optional[Callable[[bool, str], None]] = None,
            on_error: Optional[Callable[[str], None]] = None):
        """
        Args:
            arm_ip: IP address for Lite6 arm (ignored for B601)
            port: TCP port for Lite6 arm (ignored for B601)
            arm_type: "lite6" or "b601"
            serial_port: Serial port for B601 arm (ignored for Lite6)
            on_connection_status: Callback (connected: bool, message: str)
            on_error: Callback (error_message: str)
        """
        self.arm_ip = arm_ip
        self.port = port
        self.arm_type = arm_type
        self.serial_port = serial_port
        self.arm = None
        self._lock = threading.Lock()

        # Callbacks
        self.on_connection_status = on_connection_status
        self.on_error = on_error

    def connect_arm(self) -> bool:
        """Connect to the configured arm (Lite6 or B601).

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self._lock:
                if self.arm_type == "b601":
                    if not B601_AVAILABLE:
                        self._emit_connection_status(False, "B601 driver not available")
                        return False
                    logger.info(f"Connecting to B601 arm on {self.serial_port}")
                    self.arm = B601Arm(self.serial_port)
                    label = f"B601 on {self.serial_port}"
                else:
                    if not LITE6_AVAILABLE:
                        self._emit_connection_status(False, "Lite6 driver not available")
                        return False
                    logger.info(f"Connecting to Lite6 arm at {self.arm_ip}:{self.port}")
                    self.arm = Lite6Arm(self.arm_ip, self.port)
                    label = f"Lite6 at {self.arm_ip}"

                if self.arm.connect():
                    self._emit_connection_status(True, f"Connected to {label}")
                    logger.info(f"Successfully connected to {label}")
                    return True
                else:
                    self._emit_connection_status(False, f"Failed to connect to {label}")
                    logger.error(f"Failed to connect to {label}")
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

    def move_relative_tool(
            self,
            dx: float = 0, dy: float = 0, dz: float = 0,
            droll: float = 0, dpitch: float = 0, dyaw: float = 0,
            speed: float = 10,
            wait: bool = False) -> bool:
        """
        Move arm by relative offset in tool (TCP) coordinate frame.

        Args:
            dx, dy, dz: Translation deltas in mm (tool frame)
            droll, dpitch, dyaw: Rotation deltas in degrees (tool frame)
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
                success = self.arm.move_relative_tool(
                    dx, dy, dz, droll, dpitch, dyaw, speed=speed, wait=wait
                )
                if not success:
                    logger.warning(
                        f"Relative tool move failed: ({dx}, {dy}, {dz})"
                    )
                return success

            except Exception as e:
                error_msg = f"Error in relative tool move: {str(e)}"
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

    def stop_motion(self) -> bool:
        """Stop current motion and clear queued commands.

        Less aggressive than emergency_stop(). Clears the motion
        buffer so no queued moves execute after release.
        """
        with self._lock:
            if not self.arm or not self.arm.connected:
                return False
            try:
                return self.arm.stop_motion()
            except Exception as e:
                logger.error(f"Error stopping motion: {e}", exc_info=True)
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

    def set_gravity_compensation(self, enabled: bool) -> bool:
        """Enable/disable gravity compensation on B601.

        No-op (returns False) on Lite6 — the xArm SDK has no equivalent.
        """
        with self._lock:
            if not self.arm or not self.arm.connected:
                return False
            fn = getattr(self.arm, "set_gravity_compensation", None)
            if fn is None:
                logger.debug("set_gravity_compensation not supported on this arm type")
                return False
            try:
                return fn(enabled)
            except Exception as e:
                logger.error(f"Gravity compensation error: {e}", exc_info=True)
                return False

    def execute_grasp(
        self,
        grasp_point_cam: tuple,
        grasp_approach_cam: tuple,
        grasp_width_m: float,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Execute a full pick sequence from a visual grasp analysis result.

        Uses the camera→gripper (tool) rigid mount transform — a physical
        constant of the hardware — to express all moves as tool-frame
        relative deltas.  This avoids needing to know the arm's base-frame
        position in the room (which changes with every repositioning).

        Steps:
          1. Transform grasp point camera frame → gripper (tool) frame
          2. Move to approach pose (back off along approach vector by APPROACH_OFFSET)
          3. Open gripper to object width
          4. Descend to grasp pose (advance the remaining APPROACH_OFFSET)
          5. Close gripper
          6. Lift by LIFT_MM along tool Z

        Args:
            grasp_point_cam:    (x, y, z) in metres, camera frame
            grasp_approach_cam: (nx, ny, nz) unit approach vector, camera frame
            grasp_width_m:      Object width in metres (sets gripper open amount)
            on_progress:        Optional callback(str) for status messages
        """
        import math
        import numpy as np
        from aaa_core.config.settings import app_config

        _APPROACH_OFFSET_MM = 80.0   # stop this far short of the grasp point
        _LIFT_MM = 100.0             # how far to lift after gripping

        def _report(msg: str):
            logger.info(msg)
            if on_progress:
                try:
                    on_progress(msg)
                except Exception:
                    pass

        def _R_from_rpy(r_deg: float, p_deg: float, y_deg: float) -> np.ndarray:
            # Intrinsic RPY (= extrinsic ZYX): apply Rx first, then Ry, then Rz.
            # Equivalent to: result = Rz(yaw) @ Ry(pitch) @ Rx(roll).
            # Right-hand rule: +roll tilts +Y toward +Z (top of cam toward forward).
            #                  +pitch tilts +Z toward -X (cam face tilts upward).
            #                  +yaw  tilts +X toward +Y (cam face turns leftward).
            r = math.radians(r_deg)
            p = math.radians(p_deg)
            y = math.radians(y_deg)
            Rx = np.array([[1, 0, 0],
                           [0, math.cos(r), -math.sin(r)],
                           [0, math.sin(r),  math.cos(r)]])
            Ry = np.array([[ math.cos(p), 0, math.sin(p)],
                           [0, 1, 0],
                           [-math.sin(p), 0, math.cos(p)]])
            Rz = np.array([[math.cos(y), -math.sin(y), 0],
                           [math.sin(y),  math.cos(y), 0],
                           [0, 0, 1]])
            return Rz @ Ry @ Rx

        # Camera→tool (gripper) rigid mount transform — constant for a given
        # hardware setup; only changes if the camera is physically remounted.
        cfg = app_config
        R_cam_tool = _R_from_rpy(
            cfg.camera_to_tool_roll,
            cfg.camera_to_tool_pitch,
            cfg.camera_to_tool_yaw,
        )
        t_cam_tool = np.array([
            cfg.camera_to_tool_tx_mm,
            cfg.camera_to_tool_ty_mm,
            cfg.camera_to_tool_tz_mm,
        ])

        def cam_to_tool_mm(pt_m: tuple) -> np.ndarray:
            """Camera frame metres → gripper (tool) frame mm."""
            return R_cam_tool @ (np.array(pt_m) * 1000.0) + t_cam_tool

        # Grasp point and approach vector in tool frame (mm)
        grasp_tool = cam_to_tool_mm(grasp_point_cam)

        approach_dir_cam = np.array(grasp_approach_cam, dtype=float)
        norm = float(np.linalg.norm(approach_dir_cam))
        if norm > 1e-9:
            approach_dir_cam /= norm
        # Approach direction in tool frame (rotation only, no translation)
        approach_dir_tool = R_cam_tool @ approach_dir_cam

        # Approach pose = grasp point backed off along approach vector
        approach_tool = grasp_tool - approach_dir_tool * _APPROACH_OFFSET_MM

        # Gripper open position: 1.2× object width on 0–800 GUI scale.
        # 80 mm is the full open span denominator.
        open_pos = min(800, int((grasp_width_m * 1000.0 / 80.0) * 800 * 1.2))

        with self._lock:
            if not self.arm or not self.arm.connected:
                _report("Grasp aborted: arm not connected")
                return False
            arm = self.arm

        try:
            # Step 1: move to approach position (relative to current tool pose)
            _report("Moving to approach pose")
            ok = arm.move_relative_tool(
                float(approach_tool[0]),
                float(approach_tool[1]),
                float(approach_tool[2]),
                speed=app_config.movement_speed,
                wait=True,
            )
            if not ok:
                _report("Approach move failed")
                return False

            # Step 2: open gripper
            _report("Opening gripper")
            arm.set_gripper_position(open_pos, wait=True)

            # Step 3: descend — advance the remaining approach offset to reach grasp point
            _report("Descending to grasp pose")
            descent = approach_dir_tool * _APPROACH_OFFSET_MM
            if not arm.move_relative_tool(
                float(descent[0]), float(descent[1]), float(descent[2]),
                speed=app_config.movement_speed // 2,   # slower for final approach
                wait=True,
            ):
                _report("Descent move failed")
                return False

            # Step 4: close gripper
            _report("Closing gripper")
            arm.close_gripper(wait=True)

            # Step 5: lift along tool Z
            _report("Lifting")
            arm.move_relative_tool(0.0, 0.0, -_LIFT_MM, wait=True)

            _report("Grasp complete")
            return True

        except Exception as e:
            _report(f"Grasp failed: {e}")
            logger.error(f"Grasp execution error: {e}", exc_info=True)
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
