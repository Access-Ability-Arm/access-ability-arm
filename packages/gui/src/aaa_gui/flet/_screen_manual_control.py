"""Screen 4C: Manual Control — Gesture Edges with bottom bar.

Matches prototype: docs/ux/screens/4-manual-c-gesture.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from . import _design_tokens as T

if TYPE_CHECKING:
    from .main_window import FletMainWindow


def build_screen_manual_control(window: FletMainWindow) -> ft.Container:
    """Build manual control screen with edge zones and bottom bar.

    Prototype spec (4-manual-c-gesture.html):
    - Edge zones: bg-blue-500/30, hover bg-blue-500/60
      - Left/Right: w-24 h-48 (96x192px), rounded-r-3xl / rounded-l-3xl (24px)
      - Top/Bottom: h-20 w-48 (80x192px), rounded-b-3xl / rounded-t-3xl (24px)
    - Back button: bg-black/40, rounded-xl, px-4 py-2.5
    - Bottom bar: bg-black/70, p-4
      - Height buttons: 90x60px, bg-green-500/80, rounded-2xl
      - Gripper buttons: 90x60px, bg-amber-500/80, rounded-2xl
      - Speed: bg-white/20 (unselected) / bg-white (selected), rounded-lg, px-4 py-2
      - Stop: bg-red-600, rounded-2xl, px-6 py-4, font-bold
    """

    # --- Edge zone hover handler (mode-aware colour) ---
    def _edge_hover(e):
        opacity = T.EDGE_ZONE_HOVER if e.data == "true" else T.EDGE_ZONE_DEFAULT
        base = T.AMBER_500 if getattr(window, "control_mode", "translate") == "rotate" else T.BLUE_500
        e.control.bgcolor = ft.Colors.with_opacity(opacity, base)
        e.control.update()

    # --- Edge zones ---
    # Labels stored on window so _on_mode_toggle can update them.
    window.left_zone_label = ft.Text("Left", size=T.TEXT_SM, color=T.WHITE, weight=ft.FontWeight.W_500)
    window.right_zone_label = ft.Text("Right", size=T.TEXT_SM, color=T.WHITE, weight=ft.FontWeight.W_500)
    window.top_zone_label = ft.Text("Forward", size=T.TEXT_SM, color=T.WHITE, weight=ft.FontWeight.W_500)
    window.back_zone_label = ft.Text("Back", size=T.TEXT_SM, color=T.WHITE, weight=ft.FontWeight.W_500)

    # Left: X- (move left)  /  Yaw- in rotate mode
    window.left_zone_container = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.CHEVRON_LEFT, size=40, color=T.WHITE),
                window.left_zone_label,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        ),
        bgcolor=ft.Colors.with_opacity(T.EDGE_ZONE_DEFAULT, T.BLUE_500),
        border_radius=ft.border_radius.only(
            top_right=T.RADIUS_3XL, bottom_right=T.RADIUS_3XL,
        ),
        width=T.EDGE_ZONE_LR_W,
        height=T.EDGE_ZONE_LR_H,
        alignment=ft.alignment.center,
        on_click=lambda _: window._on_button_press("x", "neg"),
        on_hover=_edge_hover,
        ink=True,
    )
    left_zone = window.left_zone_container

    # Right: X+ (move right)  /  Yaw+ in rotate mode
    window.right_zone_container = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=40, color=T.WHITE),
                window.right_zone_label,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        ),
        bgcolor=ft.Colors.with_opacity(T.EDGE_ZONE_DEFAULT, T.BLUE_500),
        border_radius=ft.border_radius.only(
            top_left=T.RADIUS_3XL, bottom_left=T.RADIUS_3XL,
        ),
        width=T.EDGE_ZONE_LR_W,
        height=T.EDGE_ZONE_LR_H,
        alignment=ft.alignment.center,
        on_click=lambda _: window._on_button_press("x", "pos"),
        on_hover=_edge_hover,
        ink=True,
    )
    right_zone = window.right_zone_container

    # Top: Y+ (forward)  /  Pitch+ in rotate mode
    window.top_zone_container = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.EXPAND_LESS, size=40, color=T.WHITE),
                window.top_zone_label,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        ),
        bgcolor=ft.Colors.with_opacity(T.EDGE_ZONE_DEFAULT, T.BLUE_500),
        border_radius=ft.border_radius.only(
            bottom_left=T.RADIUS_3XL, bottom_right=T.RADIUS_3XL,
        ),
        width=T.EDGE_ZONE_TB_W,
        height=T.EDGE_ZONE_TB_H,
        alignment=ft.alignment.center,
        on_click=lambda _: window._on_button_press("y", "pos"),
        on_hover=_edge_hover,
        ink=True,
    )
    top_zone = window.top_zone_container

    # Bottom: Y- (back)  /  Pitch- in rotate mode — above the bottom bar
    window.back_zone_container = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.EXPAND_MORE, size=40, color=T.WHITE),
                window.back_zone_label,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        ),
        bgcolor=ft.Colors.with_opacity(T.EDGE_ZONE_DEFAULT, T.BLUE_500),
        border_radius=ft.border_radius.only(
            top_left=T.RADIUS_3XL, top_right=T.RADIUS_3XL,
        ),
        width=T.EDGE_ZONE_TB_W,
        height=T.EDGE_ZONE_TB_H,
        alignment=ft.alignment.center,
        on_click=lambda _: window._on_button_press("y", "neg"),
        on_hover=_edge_hover,
        ink=True,
    )
    back_zone = window.back_zone_container

    # --- Mode toggle button (top-right): Move ↔ Rotate ---
    def _mode_hover(e):
        is_rotate = getattr(window, "control_mode", "translate") == "rotate"
        base = T.AMBER_500 if is_rotate else T.BLUE_500
        e.control.bgcolor = ft.Colors.with_opacity(
            0.80 if e.data == "true" else 0.60, base
        )
        e.control.update()

    window.mode_toggle_icon = ft.Icon(ft.Icons.CONTROL_CAMERA, size=20, color=T.WHITE)
    window.mode_toggle_text = ft.Text(
        "Move", size=T.TEXT_BASE, color=T.WHITE, weight=ft.FontWeight.W_500,
    )
    window.mode_toggle_btn = ft.Container(
        content=ft.Row(
            [window.mode_toggle_icon, window.mode_toggle_text],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.60, T.BLUE_500),
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        on_click=lambda _: window._on_mode_toggle(),
        on_hover=_mode_hover,
        ink=True,
    )

    # --- Back button (top-left) ---
    def _back_hover(e):
        e.control.bgcolor = ft.Colors.with_opacity(
            0.60 if e.data == "true" else 0.40, T.BLACK
        )
        e.control.update()

    nav_back_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ARROW_BACK, size=20, color=T.WHITE),
                ft.Text("Back", size=T.TEXT_BASE, color=T.WHITE, weight=ft.FontWeight.W_500),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.40, T.BLACK),
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        on_click=lambda _: window._back_from_manual_control(),
        on_hover=_back_hover,
        ink=True,
    )

    # --- Bottom bar ---
    def _make_bottom_btn(label, icon, base_color, on_click, width=T.BOTTOM_BTN_W):
        default_bg = ft.Colors.with_opacity(0.80, base_color)
        hover_bg = base_color

        def _btn_hover(e):
            e.control.bgcolor = hover_bg if e.data == "true" else default_bg
            e.control.update()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=24, color=T.WHITE),
                    ft.Text(label, size=T.TEXT_XS, color=T.WHITE, weight=ft.FontWeight.W_500),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=default_bg,
            border_radius=T.RADIUS_2XL,
            width=width,
            height=T.BOTTOM_BTN_H,
            alignment=ft.alignment.center,
            on_click=on_click,
            on_hover=_btn_hover,
            ink=True,
        )

    up_btn = _make_bottom_btn(
        "Up", ft.Icons.ARROW_UPWARD,
        T.GREEN_500,
        lambda _: window._on_button_press("z", "pos"),
    )
    down_btn = _make_bottom_btn(
        "Down", ft.Icons.ARROW_DOWNWARD,
        T.GREEN_500,
        lambda _: window._on_button_press("z", "neg"),
    )
    open_grip_btn = _make_bottom_btn(
        "Open", ft.Icons.OPEN_WITH,
        T.AMBER_500,
        lambda _: window._on_grip_state_changed(False),
    )
    close_grip_btn = _make_bottom_btn(
        "Close", ft.Icons.BACK_HAND,
        T.AMBER_500,
        lambda _: window._on_grip_state_changed(True),
    )

    # Speed selector — prototype: bg-white/20 (unselected), bg-white (selected)
    window.speed_segment = ft.SegmentedButton(
        segments=[
            ft.Segment(value="slow", label=ft.Text("Slow", size=T.TEXT_SM)),
            ft.Segment(value="med", label=ft.Text("Med", size=T.TEXT_SM)),
            ft.Segment(value="fast", label=ft.Text("Fast", size=T.TEXT_SM)),
        ],
        selected={"slow"},
        on_change=lambda e: window._on_speed_segment_changed(e),
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.SELECTED: T.WHITE,
                ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.20, T.WHITE),
            },
            color={
                ft.ControlState.SELECTED: T.BLACK,
                ft.ControlState.DEFAULT: T.WHITE,
            },
            shape=ft.RoundedRectangleBorder(radius=T.RADIUS_LG),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        ),
    )

    # STOP button — bg-red-600, rounded-2xl, px-6 py-4, font-bold
    def _stop_hover(e):
        e.control.bgcolor = T.RED_700 if e.data == "true" else T.RED_600
        e.control.update()

    stop_btn = ft.Container(
        content=ft.Text(
            "STOP", size=T.TEXT_BASE, color=T.WHITE, weight=ft.FontWeight.W_700,
        ),
        bgcolor=T.RED_600,
        border_radius=T.RADIUS_2XL,
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
        alignment=ft.alignment.center,
        on_click=lambda _: window._on_stop(),
        on_hover=_stop_hover,
        ink=True,
    )

    bottom_bar = ft.Container(
        content=ft.Row(
            [
                up_btn,
                down_btn,
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.3, T.WHITE)),
                window.speed_segment,
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.3, T.WHITE)),
                open_grip_btn,
                close_grip_btn,
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.3, T.WHITE)),
                stop_btn,
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_DARK_70, T.BLACK),
        padding=ft.padding.all(16),
    )

    # Transparent tap layer for click-to-center and scroll (behind all controls)
    tap_layer = ft.GestureDetector(
        content=ft.Container(expand=True),
        on_tap_up=lambda e: window._on_click_to_center(e),
        on_scroll=lambda e: window._on_scroll_action(e),
    )

    return ft.Container(
        content=ft.Stack(
            [
                # Click-to-center tap target (first = behind everything)
                tap_layer,
                # Left edge — anchored left, vertically centered
                ft.Container(
                    content=left_zone,
                    left=0, top=0, bottom=0,
                    alignment=ft.alignment.center,
                ),
                # Right edge — anchored right, vertically centered
                ft.Container(
                    content=right_zone,
                    right=0, top=0, bottom=0,
                    alignment=ft.alignment.center,
                ),
                # Top edge — anchored top, horizontally centered
                ft.Container(
                    content=top_zone,
                    top=0, left=0, right=0,
                    alignment=ft.alignment.center,
                ),
                # Bottom edge — above bottom bar, horizontally centered
                ft.Container(
                    content=back_zone,
                    bottom=90, left=0, right=0,
                    alignment=ft.alignment.center,
                ),
                # Top-left: navigation back
                ft.Container(content=nav_back_btn, top=16, left=16),
                # Top-right: mode toggle (Move / Rotate)
                ft.Container(content=window.mode_toggle_btn, top=16, right=16),
                # Bottom: control bar (intentionally full-width)
                ft.Container(content=bottom_bar, bottom=0, left=0, right=0),
            ],
        ),
        expand=True,
    )
