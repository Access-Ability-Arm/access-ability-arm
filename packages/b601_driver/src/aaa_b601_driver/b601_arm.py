"""
Seeed Studio reBot Arm B601 Driver

Presents the same public API as Lite6Arm so ArmControllerFlet can swap
between them without changes to the rest of the codebase.

Communication: USB-C serial → CAN bus adapter via reBotArm_control_py + motorbridge.

Unit convention (matches Lite6Arm):
  - Positions accepted/returned in millimetres
  - Angles accepted/returned in degrees
  - Internally converts to metres/radians before calling the SDK

Installation:
    pip install motorbridge
    git clone https://github.com/vectorBH6/reBotArm_control_py.git \\
        packages/b601_driver/vendor/reBotArm_control_py
    pip install -e packages/b601_driver/vendor/reBotArm_control_py

Linux serial permission (run once):
    sudo chmod 666 /dev/ttyACM0
    # or: sudo usermod -aG dialout $USER (permanent)
"""

import math
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_MM_TO_M = 0.001
_M_TO_MM = 1000.0
_D2R = math.pi / 180.0
_R2D = 180.0 / math.pi

# GUI gripper scale: 0 = fully closed, 800 = fully open (matches Lite6 convention).
# B601 gripper is a motor; we map this range to 0.0–1.0 internally.
_GRIPPER_SCALE = 800.0

try:
    # VERIFY: exact module and class name after cloning reBotArm_control_py.
    # The examples in that repo use a class similar to this; adjust if needed.
    from rebotarm_control import ReBotArm  # noqa: F401
    B601_SDK_AVAILABLE = True
except ImportError:
    B601_SDK_AVAILABLE = False


class B601Arm:
    """
    Seeed Studio reBot Arm B601 (DM or RS variant).

    Drop-in replacement for Lite6Arm; all public method signatures are
    identical so ArmControllerFlet needs no conditional logic beyond
    construction.
    """

    def __init__(self, port: str = "/dev/ttyACM0"):
        """
        Args:
            port: Serial port connected to the B601 CAN adapter.
                  Linux: "/dev/ttyACM0"   Windows: "COM3"
        """
        self.port = port
        self._arm = None
        self.connected = False
        print(f"[B601] Initializing on {port}")

    # ------------------------------------------------------------------ #
    #  Connection                                                          #
    # ------------------------------------------------------------------ #

    def connect(self) -> bool:
        if not B601_SDK_AVAILABLE:
            print("[B601] reBotArm_control_py not installed — see b601_arm.py docstring")
            return False
        try:
            # VERIFY: constructor signature after cloning reBotArm_control_py
            self._arm = ReBotArm(port=self.port)
            self._arm.connect()
            self.connected = True
            print(f"[B601] Connected on {self.port}")
            return True
        except Exception as e:
            print(f"[B601] Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self._arm and self.connected:
            try:
                self._arm.disconnect()
            except Exception:
                pass
            self.connected = False
            print("[B601] Disconnected")

    # ------------------------------------------------------------------ #
    #  Motion — standard Cartesian (mm / degrees)                         #
    # ------------------------------------------------------------------ #

    def move_to_position(
        self,
        x: float,
        y: float,
        z: float,
        roll: Optional[float] = None,
        pitch: Optional[float] = None,
        yaw: Optional[float] = None,
        speed: float = 100,
        wait: bool = True,
    ) -> bool:
        if not self.connected or not self._arm:
            print("[B601] Not connected")
            return False
        try:
            xm, ym, zm = x * _MM_TO_M, y * _MM_TO_M, z * _MM_TO_M
            if roll is not None:
                rr = roll  * _D2R
                pr = pitch * _D2R
                yr = yaw   * _D2R
                # VERIFY: method name and signature in reBotArm_control_py
                self._arm.move_to_cartesian(xm, ym, zm, rr, pr, yr)
            else:
                self._arm.move_to_cartesian(xm, ym, zm)
            return True
        except Exception as e:
            print(f"[B601] Move error: {e}")
            return False

    def move_relative_tool(
        self,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
        droll: float = 0,
        dpitch: float = 0,
        dyaw: float = 0,
        speed: float = 100,
        wait: bool = False,
    ) -> bool:
        """
        Approximates tool-frame relative motion: reads current pose, applies
        the delta in world-frame, then issues an absolute Cartesian command.
        Sufficient for GUI jogging; not a true tool-frame transform.
        """
        if not self.connected or not self._arm:
            return False
        pose = self.get_position()
        if pose is None:
            return False
        cx, cy, cz, cr, cp, cyw = pose
        return self.move_to_position(
            cx + dx, cy + dy, cz + dz,
            cr + droll, cp + dpitch, cyw + dyaw,
            speed=speed,
            wait=wait,
        )

    def move_to_position_smooth(
        self,
        x: float,
        y: float,
        z: float,
        roll: Optional[float] = None,
        pitch: Optional[float] = None,
        yaw: Optional[float] = None,
        duration: float = 2.0,
    ) -> bool:
        """
        Move via SE(3) geodesic trajectory (reBotArm_control_py example 8).
        Produces smoother arc-path motion — preferred for grasp approach.
        Falls back to move_to_position() if the SDK method is unavailable.
        """
        if not self.connected or not self._arm:
            return False
        try:
            xm, ym, zm = x * _MM_TO_M, y * _MM_TO_M, z * _MM_TO_M
            rr = (roll  or 0.0) * _D2R
            pr = (pitch or 0.0) * _D2R
            yr = (yaw   or 0.0) * _D2R
            # VERIFY: method name in reBotArm_control_py example 8
            self._arm.move_trajectory(xm, ym, zm, rr, pr, yr, duration=duration)
            return True
        except AttributeError:
            # SDK version without trajectory — fall back to point move
            return self.move_to_position(x, y, z, roll, pitch, yaw)
        except Exception as e:
            print(f"[B601] Trajectory move error: {e}")
            return False

    def get_position(self) -> Optional[Tuple[float, float, float, float, float, float]]:
        if not self.connected or not self._arm:
            return None
        try:
            # VERIFY: return format — (x_m, y_m, z_m, roll_rad, pitch_rad, yaw_rad) assumed
            pose = self._arm.get_cartesian_pose()
            if pose is None:
                return None
            x, y, z, r, p, yw = pose
            return (
                x  * _M_TO_MM,
                y  * _M_TO_MM,
                z  * _M_TO_MM,
                r  * _R2D,
                p  * _R2D,
                yw * _R2D,
            )
        except Exception as e:
            print(f"[B601] Get position error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Gripper  (GUI uses 0–800 scale; B601 gripper motor uses 0.0–1.0)  #
    # ------------------------------------------------------------------ #

    def set_gripper_position(
        self,
        position: float,
        speed: int = 5000,
        wait: bool = True,
    ) -> bool:
        """
        Args:
            position: 0 (closed) to 800 (open) — same scale as Lite6.
            speed: Accepted for API compatibility; not used (B601 gripper
                   speed is controlled via motor parameters).
        """
        if not self.connected or not self._arm:
            return False
        try:
            pct = max(0.0, min(1.0, position / _GRIPPER_SCALE))
            # VERIFY: method name and signature in reBotArm_control_py
            self._arm.set_gripper(pct)
            return True
        except Exception as e:
            print(f"[B601] Gripper error: {e}")
            return False

    def open_gripper(self, speed: int = 5000, wait: bool = True) -> bool:
        return self.set_gripper_position(800, speed=speed, wait=wait)

    def close_gripper(self, speed: int = 5000, wait: bool = True) -> bool:
        return self.set_gripper_position(0, speed=speed, wait=wait)

    def get_gripper_position(self) -> Optional[float]:
        if not self.connected or not self._arm:
            return None
        try:
            # VERIFY: return value — 0.0–1.0 assumed
            pct = self._arm.get_gripper()
            return pct * _GRIPPER_SCALE if pct is not None else None
        except Exception as e:
            print(f"[B601] Get gripper error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Gravity Compensation (B601-specific; not on Lite6Arm)              #
    # ------------------------------------------------------------------ #

    def set_gravity_compensation(self, enabled: bool) -> bool:
        """
        Enable/disable gravity compensation ('floating') mode.
        In this mode the arm holds its pose against gravity but yields
        to manual force — useful for guided positioning.

        On disable: automatically returns to home pose.
        """
        if not self.connected or not self._arm:
            return False
        try:
            # VERIFY: method names in reBotArm_control_py example 9
            if enabled:
                self._arm.start_gravity_compensation()
            else:
                self._arm.stop_gravity_compensation()
                self._arm.home()
            print(f"[B601] Gravity compensation {'ON' if enabled else 'OFF'}")
            return True
        except Exception as e:
            print(f"[B601] Gravity compensation error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Utilities                                                           #
    # ------------------------------------------------------------------ #

    def home(self) -> bool:
        if not self.connected or not self._arm:
            print("[B601] Not connected")
            return False
        try:
            # VERIFY: method name in reBotArm_control_py
            self._arm.home()
            print("[B601] Moved to home position")
            return True
        except Exception as e:
            print(f"[B601] Home error: {e}")
            return False

    def stop_motion(self) -> bool:
        if not self.connected or not self._arm:
            return False
        try:
            self._arm.stop()
            return True
        except Exception as e:
            print(f"[B601] Stop error: {e}")
            return False

    def emergency_stop(self):
        if self._arm:
            try:
                self._arm.emergency_stop()
                print("[B601] EMERGENCY STOP")
            except Exception as e:
                print(f"[B601] Emergency stop error: {e}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
