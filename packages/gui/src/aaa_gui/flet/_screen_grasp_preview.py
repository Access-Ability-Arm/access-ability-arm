"""Screen 3B: Grasp Preview — Inline overlay with info card and action bar.

Matches prototype: docs/ux/screens/3-grasp-b-inline.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from . import _design_tokens as T

if TYPE_CHECKING:
    from .main_window import FletMainWindow


def build_screen_grasp_preview(window: FletMainWindow) -> ft.Container:
    """Build the grasp preview screen with inline overlay.

    Prototype spec (3-grasp-b-inline.html):
    - Back button: bg-black/40, rounded-xl, px-4 py-2.5
    - Info card (top-right): bg-black/70, rounded-2xl, p-5, min-w-56 (224px)
      - Object number badge: w-10 h-10 (40px) rounded-full
      - Confidence bar: h-2, bg-white/20 track, bg-green-400 fill, rounded-full
      - Text sizes: title text-lg, status text-sm, metrics text-sm
    - Action bar (bottom): gradient from-black/80 to-transparent, pt-20 pb-6
      - "Grab This": bg-green-500, rounded-2xl, px-10 py-5, text-xl, font-semibold
      - "Try Again": bg-white/20, rounded-2xl, px-8 py-5, text-xl
      - "More": bg-white/10, rounded-xl, px-4 py-3, text-sm, text-white/60
    """

    # --- Back button (top-left) ---
    def _back_hover(e):
        e.control.bgcolor = ft.Colors.with_opacity(
            0.60 if e.data == "true" else 0.40, T.BLACK
        )
        e.control.update()

    back_btn = ft.Container(
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
        on_click=lambda _: window._back_from_grasp_preview(),
        on_hover=_back_hover,
        ink=True,
    )

    # --- Info card (top-right) ---
    window.grasp_badge_container = ft.Container(
        content=ft.Text("#1", size=T.TEXT_LG, color=T.WHITE, weight=ft.FontWeight.W_700),
        bgcolor=T.BLUE_500,
        border_radius=T.RADIUS_FULL,
        width=40,
        height=40,
        alignment=ft.alignment.center,
    )
    window.grasp_object_name = ft.Text(
        "Object", size=T.TEXT_LG, color=T.WHITE, weight=ft.FontWeight.W_600,
    )
    window.grasp_status_text = ft.Text(
        "Analyzing...", size=T.TEXT_SM, color=T.GREEN_400, weight=ft.FontWeight.W_500,
    )

    # Confidence progress bar (h-2, rounded-full)
    window.grasp_confidence_bar = ft.ProgressBar(
        value=0, width=180, bar_height=8,
        color=T.GREEN_400,
        bgcolor=ft.Colors.with_opacity(0.20, T.WHITE),
    )
    window.grasp_confidence_text = ft.Text(
        "Confidence: --", size=T.TEXT_SM, color=T.GRAY_400,
    )
    window.grasp_dimensions_text = ft.Text(
        "Dimensions: --", size=T.TEXT_SM, color=T.GRAY_400,
    )

    info_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [window.grasp_badge_container, window.grasp_object_name],
                    spacing=12,
                ),
                window.grasp_status_text,
                ft.Container(height=4),
                window.grasp_confidence_bar,
                window.grasp_confidence_text,
                window.grasp_dimensions_text,
            ],
            spacing=6,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_DARK_70, T.BLACK),
        border_radius=T.RADIUS_2XL,
        padding=ft.padding.all(20),
        width=240,
    )

    # --- Action bar (bottom) ---
    # Prototype uses a gradient: from-black/80 to-transparent, pt-20 pb-6
    # Flet doesn't support gradient on Container bg, so we use a solid high-opacity bg

    # "Grab This" (primary, green)
    grab_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.BACK_HAND, size=24, color=T.WHITE),
                ft.Text("Grab This", size=T.TEXT_XL, color=T.WHITE, weight=ft.FontWeight.W_600),
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=T.GREEN_500,
        border_radius=T.RADIUS_2XL,
        padding=ft.padding.symmetric(horizontal=40, vertical=20),
        on_click=lambda _: window._on_execute(),
        ink=True,
    )

    # "Try Again" (secondary, white/20)
    retry_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.REFRESH, size=24, color=T.WHITE),
                ft.Text("Try Again", size=T.TEXT_XL, color=T.WHITE, weight=ft.FontWeight.W_500),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_LIGHT_20, T.WHITE),
        border_radius=T.RADIUS_2XL,
        padding=ft.padding.symmetric(horizontal=32, vertical=20),
        on_click=lambda _: window._retry_grasp(),
        ink=True,
    )

    # "More" popup (bg-white/10, rounded-xl, text-sm)
    more_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_HORIZ,
        icon_color=ft.Colors.with_opacity(0.60, T.WHITE),
        icon_size=20,
        items=[
            ft.PopupMenuItem(
                text="Export PLY",
                icon=ft.Icons.CLOUD_UPLOAD,
                on_click=lambda _: window._export_selected_object_ply(),
            ),
            ft.PopupMenuItem(
                text="Export Mesh",
                icon=ft.Icons.VIEW_IN_AR,
                on_click=lambda _: window._export_selected_object_mesh(),
            ),
            ft.PopupMenuItem(
                text="Complete Shape",
                icon=ft.Icons.AUTO_FIX_HIGH,
                on_click=lambda _: window._export_completed_object_mesh(),
            ),
            ft.PopupMenuItem(
                text="Show Points",
                icon=ft.Icons.VISIBILITY,
                on_click=lambda _: window._on_show_points(),
            ),
            ft.PopupMenuItem(),  # Divider
            ft.PopupMenuItem(
                text="Preview 3D",
                icon=ft.Icons.THREED_ROTATION,
                on_click=lambda _: window._preview_selected_object_ply(),
            ),
        ],
    )

    more_btn_container = ft.Container(
        content=more_menu,
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_LIGHT_10, T.WHITE),
        border_radius=T.RADIUS_XL,
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
    )

    # Action bar container — simulate gradient with high-opacity bottom bar
    action_bar = ft.Container(
        content=ft.Row(
            [retry_btn, grab_btn, more_btn_container],
            spacing=16,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_DARK_80, T.BLACK),
        padding=ft.padding.only(left=24, right=24, top=24, bottom=24),
    )

    return ft.Container(
        content=ft.Stack(
            [
                # Top-left: back button
                ft.Container(content=back_btn, top=16, left=16),
                # Top-right: info card
                ft.Container(content=info_card, top=16, right=16),
                # Bottom: action bar (full width)
                ft.Container(content=action_bar, bottom=0, left=0, right=0),
            ],
        ),
        expand=True,
    )
