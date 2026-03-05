"""Arm Control mixin – robotic arm movement, gripper, and connection logic."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .main_window import FletMainWindow

import flet as ft

from aaa_core.config.settings import app_config

# Camera intrinsic: approximate focal length for RealSense D435 at 1920x1080
_CAM_FX = 1386.0

# Max movement per click (mm) before speed scaling
_MAX_STEP_MM = 50.0

# Fallback depth (mm) when no depth data available
_FALLBACK_DEPTH_MM = 500.0

# Camera-to-robot axis mapping: cam_x -> robot axis index and sign,
# cam_y -> robot axis index and sign.  (0=X, 1=Y, 2=Z)
# Default: camera-right -> robot -Y, camera-down -> robot -Z
_CAM_TO_ROBOT = {"cam_x": (1, -1), "cam_y": (2, -1)}


class ArmControlMixin:
    """Mixin that provides robotic-arm control methods for MainWindow.

    Handles button-press driven movement commands, speed/gripper changes,
    connection lifecycle, and status UI updates.
    """

    def _on_button_press(self: FletMainWindow, direction: str, button_type: str):
        """Handle robotic arm button press"""
        button_name = f"{direction}_{button_type}"
        print(f"Button {button_name} pressed")

        start_time = time.time()
        self.button_controller.update_button_state("pressed", start_time, button_name)

        # Simulate release after brief moment and execute arm command
        def on_release():
            duration = time.time() - start_time
            self.button_controller.update_button_state("released", 0, button_name)
            self._handle_arm_command(button_name, duration)

        threading.Timer(0.1, on_release).start()

    def _on_speed_changed(self: FletMainWindow, e):
        """Handle speed slider change"""
        self.movement_speed_percent = int(e.control.value)
        self.speed_label.value = f"Speed: {self.movement_speed_percent}%"
        self.page.update()
        print(f"Movement speed set to: {self.movement_speed_percent}%")

    def _on_grip_state_changed(self: FletMainWindow, is_closed: bool):
        """Handle grip state toggle"""
        state = "closed" if is_closed else "open"
        print(f"Grip state: {state}")
        self.button_controller.update_button_state("clicked", 0, "grip_state")

        # Control gripper if arm is connected
        if self.arm_controller and self.arm_controller.arm:
            if is_closed:
                self.arm_controller.close_gripper(
                    speed=app_config.gripper_speed, wait=False
                )
            else:
                self.arm_controller.open_gripper(
                    speed=app_config.gripper_speed, wait=False
                )

    def _handle_arm_command(self: FletMainWindow, button_name: str, duration: float):
        """
        Handle arm movement command based on button press

        Args:
            button_name: Name of button pressed (e.g., "x_pos", "y_neg")
            duration: Duration of button press in seconds
        """
        if not self.arm_controller or not self.arm_controller.arm:
            return

        if not self.arm_controller.arm.connected:
            print("Arm not connected - cannot move")
            return

        # Get current position
        pos = self.arm_controller.get_position()
        if not pos or len(pos) < 6:
            print("Could not get current arm position")
            return

        x, y, z, roll, pitch, yaw = pos[0], pos[1], pos[2], pos[3], pos[4], pos[5]

        # Determine step size based on button hold duration
        # Short tap: small step, long hold: large step
        base_step = (
            app_config.tap_step_size
            if duration < app_config.button_hold_threshold
            else app_config.hold_step_size
        )

        # Apply speed percentage to step size
        step = base_step * (self.movement_speed_percent / 100.0)

        # Apply movement based on button
        if button_name == "x_pos":
            x += step
        elif button_name == "x_neg":
            x -= step
        elif button_name == "y_pos":
            y += step
        elif button_name == "y_neg":
            y -= step
        elif button_name == "z_pos":
            z += step
        elif button_name == "z_neg":
            z -= step
        elif button_name == "grip_pos":
            # Grip controls - apply speed percentage
            current_grip = self.arm_controller.arm.get_gripper_position() or 400
            grip_step = 100 * (self.movement_speed_percent / 100.0)
            new_grip = min(800, current_grip + grip_step)
            self.arm_controller.set_gripper(int(new_grip), wait=False)
            return
        elif button_name == "grip_neg":
            current_grip = self.arm_controller.arm.get_gripper_position() or 400
            grip_step = 100 * (self.movement_speed_percent / 100.0)
            new_grip = max(0, current_grip - grip_step)
            self.arm_controller.set_gripper(int(new_grip), wait=False)
            return

        # Send move command with speed percentage applied
        movement_speed = app_config.movement_speed * (
            self.movement_speed_percent / 100.0
        )
        print(
            f"Moving to: ({x:.1f}, {y:.1f}, {z:.1f}) at {self.movement_speed_percent}% speed"
        )
        self.arm_controller.move_to(
            x, y, z, roll, pitch, yaw, speed=movement_speed, wait=False
        )

    def _on_arm_connection_status(self: FletMainWindow, connected: bool, message: str):
        """Handle arm connection status updates"""
        print(f"Arm connection status: {message}")

        # Update initial loading message if still building UI (don't call page.update during init)
        if (
            hasattr(self, "loading_text")
            and hasattr(self, "_ui_built")
            and self._ui_built
        ):
            if connected:
                self.loading_text.value = "Arm connected. Building interface..."
            else:
                self.loading_text.value = "Arm connection failed. Building interface..."
            self.page.update()

        if self.arm_status_text and self._ui_built:
            if connected:
                self.arm_status_text.value = f"Arm: \u2713 Connected ({app_config.lite6_ip})"
                self.arm_status_text.color = "#2E7D32"  # Green 800
            else:
                self.arm_status_text.value = f"Arm: \u2717 {message}"
                self.arm_status_text.color = "#C62828"  # Red 800
            # Update connect button state as well
            try:
                self._set_connect_button_state(connected, connecting=False)
            except Exception:
                pass
            self.page.update()

    def _on_arm_error(self: FletMainWindow, error_message: str):
        """Handle arm errors"""
        print(f"Arm error: {error_message}")
        if self.arm_status_text:
            self.arm_status_text.value = f"Arm Error: {error_message}"
            self.arm_status_text.color = "#C62828"  # Red 800
            self.page.update()

    def _set_connect_button_state(self: FletMainWindow, connected: bool, connecting: bool = False):
        """Update the connect button text and enabled state."""
        if not hasattr(self, "arm_connect_btn") or self.arm_connect_btn is None:
            return

        if connecting:
            self.arm_connect_btn.text = "Connecting..."
            self.arm_connect_btn.disabled = True
        else:
            if connected:
                self.arm_connect_btn.text = "Disconnect Arm"
                self.arm_connect_btn.disabled = False
            else:
                self.arm_connect_btn.text = "Connect Arm"
                self.arm_connect_btn.disabled = False

        if self._ui_built:
            try:
                self.page.update()
            except Exception:
                pass

    def _on_connect_arm(self: FletMainWindow, e):
        """Handle Connect/Disconnect button click (runs connect/disconnect in background)."""
        if not self.arm_controller:
            print("Arm controller not available")
            return

        # If currently connected, disconnect
        try:
            if self.arm_controller.is_connected():
                print("Disconnecting arm...")

                def disconnect_thread():
                    try:
                        self.arm_controller.disconnect_arm()
                        print("Disconnected from arm")
                        self._set_connect_button_state(False)
                    except Exception as ex:
                        print(f"Error during disconnect: {ex}")

                threading.Thread(target=disconnect_thread, daemon=True).start()
                self._set_connect_button_state(False, connecting=False)
                return
        except Exception:
            pass

        # Otherwise, attempt to connect in background
        print("Connecting to arm (background)...")
        self._set_connect_button_state(False, connecting=True)

        def connect_thread():
            try:
                result = self.arm_controller.connect_arm()
                if result:
                    print("Background connect succeeded")
                    self._set_connect_button_state(True, connecting=False)
                else:
                    print("Background connect failed")
                    self._set_connect_button_state(False, connecting=False)
            except Exception as ex:
                print(f"Background connect exception: {ex}")
                self._set_connect_button_state(False, connecting=False)

        threading.Thread(target=connect_thread, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  Click-to-Center                                                     #
    # ------------------------------------------------------------------ #

    def _on_click_to_center(self: FletMainWindow, e: ft.TapEvent):
        """Move arm so the clicked point becomes image center."""
        if not self.arm_controller or not self.arm_controller.arm:
            print("Click-to-center: arm not connected")
            return
        if not self.arm_controller.arm.connected:
            print("Click-to-center: arm not connected")
            return

        # --- COVER-fit coordinate mapping ---
        container_w = self.page.width or 1920
        container_h = self.page.height or 1080
        img_w, img_h = 1920, 1080

        scale = max(container_w / img_w, container_h / img_h)
        displayed_w = img_w * scale
        displayed_h = img_h * scale
        offset_x = (displayed_w - container_w) / 2
        offset_y = (displayed_h - container_h) / 2

        pixel_x = (e.local_x + offset_x) / scale
        pixel_y = (e.local_y + offset_y) / scale

        # Pixel offset from image center
        dx = pixel_x - (img_w / 2)
        dy = pixel_y - (img_h / 2)

        # --- Read depth at clicked pixel ---
        depth_mm = _FALLBACK_DEPTH_MM
        ip = self.image_processor
        if ip is not None:
            depth_map = getattr(ip, "_last_display_depth", None)
            if depth_map is not None:
                px = int(np.clip(pixel_x, 0, depth_map.shape[1] - 1))
                py = int(np.clip(pixel_y, 0, depth_map.shape[0] - 1))
                # Sample neighborhood if center pixel is zero
                d = float(depth_map[py, px])
                if d <= 0:
                    r = 5
                    y0 = max(0, py - r)
                    y1 = min(depth_map.shape[0], py + r + 1)
                    x0 = max(0, px - r)
                    x1 = min(depth_map.shape[1], px + r + 1)
                    patch = depth_map[y0:y1, x0:x1]
                    valid = patch[patch > 0]
                    if len(valid) > 0:
                        d = float(np.median(valid))
                if d > 0:
                    depth_mm = d

        # --- Convert pixel offset to mm using pinhole model ---
        cam_dx_mm = dx * depth_mm / _CAM_FX
        cam_dy_mm = dy * depth_mm / _CAM_FX

        # --- Clamp to MAX_STEP_MM ---
        speed_scale = self.movement_speed_percent / 100.0
        cam_dx_mm = float(np.clip(cam_dx_mm, -_MAX_STEP_MM, _MAX_STEP_MM)) * speed_scale
        cam_dy_mm = float(np.clip(cam_dy_mm, -_MAX_STEP_MM, _MAX_STEP_MM)) * speed_scale

        if abs(cam_dx_mm) < 0.5 and abs(cam_dy_mm) < 0.5:
            return  # clicked near center, nothing to do

        # --- Get current position ---
        pos = self.arm_controller.get_position()
        if not pos or len(pos) < 6:
            print("Click-to-center: could not get arm position")
            return

        coords = list(pos[:6])  # [x, y, z, roll, pitch, yaw]

        # Apply camera-to-robot mapping
        axis_x, sign_x = _CAM_TO_ROBOT["cam_x"]
        axis_y, sign_y = _CAM_TO_ROBOT["cam_y"]
        coords[axis_x] += sign_x * cam_dx_mm
        coords[axis_y] += sign_y * cam_dy_mm

        movement_speed = app_config.movement_speed * speed_scale
        print(
            f"Click-to-center: pixel({pixel_x:.0f},{pixel_y:.0f}) "
            f"depth={depth_mm:.0f}mm offset=({cam_dx_mm:.1f},{cam_dy_mm:.1f})mm"
        )
        self.arm_controller.move_to(
            *coords, speed=movement_speed, wait=False,
        )
