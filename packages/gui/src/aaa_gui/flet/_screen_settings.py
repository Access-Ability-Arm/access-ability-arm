"""Screen 5A: Settings — Slide-over panel (light theme) from the right.

Matches prototype: docs/ux/screens/5-settings-a-slideover.html

KEY: The prototype uses a WHITE background panel with light gray sections,
NOT a dark panel. This is a light-theme slide-over.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import flet as ft

from . import _design_tokens as T
from aaa_core.config.settings import app_config

if TYPE_CHECKING:
    from .main_window import FletMainWindow


def build_settings_dimmer(window: FletMainWindow) -> ft.Container:
    """Build a click-to-close dimmer overlay behind the settings panel.

    Prototype: bg-black/30
    """
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.30, T.BLACK),
        expand=True,
        on_click=lambda _: window._close_settings(),
    )


def build_screen_settings(window: FletMainWindow) -> ft.Container:
    """Build the settings slide-over panel (light theme).

    Prototype spec (5-settings-a-slideover.html):
    - Panel: white bg, shadow-2xl, width 45%, right-aligned, full height
    - Header: flex justify-between, mb-8
    - Close button: w-10 h-10 (40px), rounded-full, bg-gray-100
    - Section headers: uppercase, text-xs, font-semibold, text-gray-400, tracking-wider
    - Setting containers: bg-gray-50, rounded-2xl, p-4
    - Toggles: w-12 h-7, rounded-full, bg-green-500 (active) / bg-gray-300 (inactive)
    - Button groups: flex gap-2, each flex-1 py-3 rounded-xl
    - Active: bg-blue-600 text-white; Inactive: bg-white border-gray-200 text-gray-700
    """

    # --- Header ---
    header = ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    "Settings",
                    size=T.TEXT_2XL,
                    weight=ft.FontWeight.W_600,
                    color=T.GRAY_700,
                ),
                ft.Container(
                    content=ft.Icon(ft.Icons.CLOSE, size=20, color=T.GRAY_400),
                    bgcolor=T.GRAY_100,
                    border_radius=T.RADIUS_FULL,
                    width=T.CLOSE_BTN_SIZE,
                    height=T.CLOSE_BTN_SIZE,
                    alignment=ft.alignment.center,
                    on_click=lambda _: window._close_settings(),
                    ink=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.padding.only(left=24, right=24, top=24, bottom=8),
    )

    # --- Helper: section header ---
    def section_header(text):
        return ft.Text(
            text.upper(),
            size=T.TEXT_XS,
            weight=ft.FontWeight.W_600,
            color=T.GRAY_400,
            style=ft.TextStyle(letter_spacing=1.5),
        )

    # --- Helper: setting container (bg-gray-50, rounded-2xl, p-4) ---
    def setting_box(content):
        return ft.Container(
            content=content,
            bgcolor=T.GRAY_50,
            border_radius=T.RADIUS_2XL,
            padding=ft.padding.all(T.CARD_PADDING),
        )

    # --- Camera section ---
    daemon_running = window._check_daemon_running()
    cameras = window.camera_manager.get_camera_info()
    camera_options = []

    if daemon_running:
        camera_options.append(
            ft.dropdown.Option(key="daemon", text="RealSense D435 (via daemon)")
        )

    for cam in cameras:
        if cam.get("color_type") == "Infrared":
            continue
        if sys.platform == "darwin" and "RealSense" in cam["camera_name"]:
            continue
        name = cam["camera_name"]
        if len(name) > 40:
            name = name[:37] + "..."
        camera_options.append(
            ft.dropdown.Option(key=str(cam["camera_index"]), text=f"[{cam['camera_index']}] {name}")
        )

    current_cam_value = None
    if hasattr(window, "camera_dropdown") and window.camera_dropdown:
        current_cam_value = window.camera_dropdown.value

    window.settings_camera_dropdown = ft.Dropdown(
        label="Camera Source",
        options=camera_options,
        value=current_cam_value,
        on_change=lambda e: window._on_settings_camera_changed(e),
        width=380,
        text_size=T.TEXT_SM,
        border_radius=T.RADIUS_XL,
        border_color=T.GRAY_200,
    )

    initial_flip = (
        window.image_processor.flip_horizontal if window.image_processor else False
    )
    window.settings_mirror_switch = ft.Switch(
        label="Mirror Image",
        value=initial_flip,
        on_change=lambda e: window._on_flip_camera(),
        label_style=ft.TextStyle(size=T.TEXT_BASE, color=T.GRAY_700, weight=ft.FontWeight.W_500),
        active_color=T.GREEN_500,
    )

    initial_depth = (
        getattr(window.image_processor, "show_depth_visualization", False)
        if window.image_processor else False
    )
    window.settings_depth_switch = ft.Switch(
        label="Show Depth View",
        value=initial_depth,
        on_change=lambda e: window._on_toggle_depth_view(),
        label_style=ft.TextStyle(size=T.TEXT_BASE, color=T.GRAY_700, weight=ft.FontWeight.W_500),
        active_color=T.GREEN_500,
    )

    camera_section = ft.Container(
        content=ft.Column(
            [
                section_header("Camera"),
                setting_box(window.settings_camera_dropdown),
                setting_box(
                    ft.Column([window.settings_mirror_switch, window.settings_depth_switch], spacing=8),
                ),
            ],
            spacing=16,
        ),
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
    )

    # --- Arm section ---
    arm_connected = (
        app_config.lite6_available
        and window.arm_controller
        and window.arm_controller.is_connected()
    )
    window.settings_arm_status = ft.Text(
        f"Connected ({app_config.lite6_ip})" if arm_connected else "Not connected",
        size=T.TEXT_SM,
        color=T.GREEN_600 if arm_connected else T.GRAY_400,
    )

    window.settings_arm_btn = ft.Container(
        content=ft.Text(
            "Disconnect" if arm_connected else "Connect Arm",
            size=T.TEXT_SM,
            color=T.RED_600 if arm_connected else T.BLUE_600,
            weight=ft.FontWeight.W_500,
        ),
        bgcolor="#FEE2E2" if arm_connected else T.GRAY_100,  # red-100 or gray-100
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        on_click=lambda _: window._on_connect_arm(None),
        ink=True,
    )

    # Speed selector — prototype uses button group with active: bg-blue-600 text-white
    window.settings_speed_segment = ft.SegmentedButton(
        segments=[
            ft.Segment(value="slow", label=ft.Text("Slow", size=T.TEXT_SM)),
            ft.Segment(value="med", label=ft.Text("Med", size=T.TEXT_SM)),
            ft.Segment(value="fast", label=ft.Text("Fast", size=T.TEXT_SM)),
        ],
        selected={"slow"},
        on_change=lambda e: window._on_speed_segment_changed(e),
    )

    arm_section = ft.Container(
        content=ft.Column(
            [
                section_header("Robotic Arm"),
                setting_box(
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Connection", size=T.TEXT_BASE, color=T.GRAY_700, weight=ft.FontWeight.W_500),
                                    window.settings_arm_status,
                                ],
                                spacing=4,
                            ),
                            window.settings_arm_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                setting_box(
                    ft.Column(
                        [
                            ft.Text("Movement Speed", size=T.TEXT_BASE, color=T.GRAY_700, weight=ft.FontWeight.W_500),
                            window.settings_speed_segment,
                        ],
                        spacing=8,
                    ),
                ),
            ],
            spacing=16,
        ),
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
    )

    # --- Advanced section ---
    window.settings_exposure_slider = ft.Slider(
        min=100, max=4000, value=800, divisions=78,
        label="Exposure: {value}",
        on_change=window._on_exposure_change,
        width=320,
        active_color=T.BLUE_500,
    )
    window.settings_exposure_text = ft.Text("Exposure: 800", size=T.TEXT_SM, color=T.GRAY_400)
    window.settings_auto_exposure_btn = ft.Container(
        content=ft.Text("Auto Adjust", size=T.TEXT_SM, color=T.BLUE_600, weight=ft.FontWeight.W_500),
        bgcolor=T.GRAY_100,
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
        on_click=lambda _: window._auto_adjust_exposure(),
        ink=True,
    )

    advanced_section = ft.Container(
        content=ft.Column(
            [
                section_header("Advanced"),
                setting_box(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("Exposure", size=T.TEXT_BASE, color=T.GRAY_700, weight=ft.FontWeight.W_500),
                                    window.settings_auto_exposure_btn,
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            window.settings_exposure_slider,
                            window.settings_exposure_text,
                        ],
                        spacing=8,
                    ),
                ),
            ],
            spacing=16,
        ),
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
    )

    # --- Assemble panel (WHITE background, shadow-2xl) ---
    panel = ft.Container(
        content=ft.Column(
            [
                header,
                ft.Divider(height=1, color=T.GRAY_200),
                camera_section,
                ft.Divider(height=1, color=T.GRAY_200),
                arm_section,
                ft.Divider(height=1, color=T.GRAY_200),
                advanced_section,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=T.WHITE,
        width=500,
        border_radius=ft.border_radius.only(top_left=T.RADIUS_2XL, bottom_left=T.RADIUS_2XL),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=32,
            color=ft.Colors.with_opacity(0.25, T.BLACK),
            offset=ft.Offset(-4, 0),
        ),
        expand=True,
    )

    # Right-aligned
    return ft.Container(
        content=ft.Row(
            [ft.Container(expand=True), panel],
            spacing=0,
            expand=True,
        ),
        expand=True,
    )
