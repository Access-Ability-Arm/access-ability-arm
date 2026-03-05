"""Screen 1A: Live View — Minimal floating overlays on full-screen video.

Matches prototype: docs/ux/screens/1-live-a-minimal.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from . import _design_tokens as T

if TYPE_CHECKING:
    from .main_window import FletMainWindow


def build_screen_live_view(window: FletMainWindow) -> ft.Container:
    """Build the live view screen with floating overlays on video.

    Prototype spec:
    - Status pill (top-center): bg-black/60, rounded-full, px-5 py-2.5
    - Arm status badge (top-left): bg-black/40, rounded-xl, px-4 py-2
    - Settings gear (top-right): bg-black/40, 48x48, rounded-full
    - Primary CTA (bottom-center): bg-blue-500, rounded-2xl, px-10 py-5, text-xl, shadow-2xl
    - Secondary "Move Arm" (bottom-right): bg-white/10, rounded-full, px-5 py-3
    """

    # --- Status pill (top-center) ---
    window.status_pill_dot = ft.Container(
        width=10,
        height=10,
        border_radius=T.RADIUS_FULL,
        bgcolor=T.GREEN_500,
    )
    window.status_pill_text = ft.Text(
        "Camera Only",
        size=T.TEXT_BASE,
        color=T.WHITE,
        weight=ft.FontWeight.W_500,
    )
    status_pill = ft.Container(
        content=ft.Row(
            [window.status_pill_dot, window.status_pill_text],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_DARK_60, T.BLACK),
        border_radius=T.RADIUS_FULL,
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
    )

    # --- Arm status badge (top-left) ---
    window.arm_badge_icon = ft.Icon(
        ft.Icons.LINK_OFF, size=16, color=T.AMBER_500,
    )
    window.arm_badge_text = ft.Text(
        "Arm", size=T.TEXT_SM, color=T.WHITE, weight=ft.FontWeight.W_500,
    )
    arm_badge = ft.Container(
        content=ft.Row(
            [window.arm_badge_icon, window.arm_badge_text],
            spacing=6,
        ),
        bgcolor=ft.Colors.with_opacity(0.40, T.BLACK),
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
    )

    # --- Settings gear (top-right) ---
    settings_btn = ft.Container(
        content=ft.Icon(ft.Icons.SETTINGS, size=24, color=T.WHITE),
        bgcolor=ft.Colors.with_opacity(0.40, T.BLACK),
        border_radius=T.RADIUS_FULL,
        width=T.GEAR_SIZE,
        height=T.GEAR_SIZE,
        alignment=ft.alignment.center,
        on_click=lambda _: window._navigate_to_settings(),
        ink=True,
    )

    # --- Primary CTA "Find Objects" (bottom-center) ---
    find_objects_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH, size=24, color=T.WHITE),
                ft.Text(
                    "Find Objects",
                    size=T.TEXT_XL,
                    color=T.WHITE,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=T.BLUE_500,
        border_radius=T.RADIUS_2XL,
        padding=ft.padding.symmetric(horizontal=T.CTA_PADDING_H, vertical=T.CTA_PADDING_V),
        on_click=lambda _: window._on_find_objects_and_navigate(),
        ink=True,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=16,
            color=ft.Colors.with_opacity(0.30, T.BLUE_600),
            offset=ft.Offset(0, 4),
        ),
    )

    # --- Secondary "Move Arm" (bottom-right) ---
    move_arm_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.OPEN_WITH, size=20, color=T.WHITE),
                ft.Text(
                    "Move Arm",
                    size=T.TEXT_BASE,
                    color=T.WHITE,
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_LIGHT_10, T.WHITE),
        border_radius=T.RADIUS_FULL,
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        on_click=lambda _: window._navigate_to_manual_control(),
        ink=True,
    )

    # --- Assemble with Stack positioning ---
    # Use left/right/top/bottom for positioning instead of Container.alignment,
    # which causes children to expand to fill the Stack.
    # Z-order: full-width layers first (behind), corner buttons last (on top)
    return ft.Container(
        content=ft.Stack(
            [
                # Full-width layers (behind)
                ft.Container(
                    content=ft.Row(
                        [status_pill], alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    top=16, left=0, right=0,
                ),
                ft.Container(
                    content=ft.Row(
                        [find_objects_btn], alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bottom=32, left=0, right=0,
                ),
                # Corner buttons (on top, clickable)
                ft.Container(content=arm_badge, top=16, left=16),
                ft.Container(content=settings_btn, top=16, right=16),
                ft.Container(content=move_arm_btn, bottom=32, right=24),
            ],
        ),
        expand=True,
    )
