"""Screen 2A: Object Selection — Card Gallery (split layout).

Matches prototype: docs/ux/screens/2-select-a-cards.html

KEY LAYOUT: Split flex-col — camera top ~60%, cards bottom ~40% with light bg.
The prototype uses a WHITE card panel, not a dark overlay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from . import _design_tokens as T

if TYPE_CHECKING:
    from .main_window import FletMainWindow


def build_screen_object_selection(window: FletMainWindow) -> ft.Container:
    """Build the object selection screen with card gallery.

    Prototype spec (2-select-a-cards.html):
    - Top section: camera feed (flex-1) with back btn + step indicator floating
    - Bottom section: bg-gray-50, border-t border-gray-200, p-5
    - Cards: min-w-[160px], border-2, rounded-2xl, p-4, bg-white
    - Number badge: w-8 h-8 rounded-full, text-lg font-bold
    - Back button: bg-black/40, rounded-xl, px-4 py-2.5
    - Step indicator: bg-black/70, rounded-full, px-6 py-3, text-lg
    """

    # --- Back button (floating over camera, top-left) ---
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
        on_click=lambda _: window._back_from_object_selection(),
        on_hover=_back_hover,
        ink=True,
    )

    # --- Step indicator (floating over camera, top-center) ---
    step_indicator = ft.Container(
        content=ft.Text(
            "Tap an object to select it",
            size=T.TEXT_LG,
            color=T.WHITE,
            weight=ft.FontWeight.W_500,
        ),
        bgcolor=ft.Colors.with_opacity(T.OVERLAY_DARK_70, T.BLACK),
        border_radius=T.RADIUS_FULL,
        padding=ft.padding.symmetric(horizontal=24, vertical=12),
    )

    # --- Card gallery row (populated dynamically) ---
    window.object_card_row = ft.Row(
        controls=[],
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
    )

    # --- Bottom card panel (light background, matching prototype bg-gray-50) ---
    card_gallery_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "DETECTED OBJECTS",
                    size=T.TEXT_XS,
                    color=T.GRAY_400,
                    weight=ft.FontWeight.W_600,
                    style=ft.TextStyle(letter_spacing=1.5),
                ),
                window.object_card_row,
            ],
            spacing=12,
        ),
        bgcolor=T.GRAY_50,
        border=ft.border.only(top=ft.BorderSide(1, T.GRAY_200)),
        padding=ft.padding.all(20),
    )

    # --- Transparent hover layer for camera labels → card highlighting ---
    camera_hover_layer = ft.GestureDetector(
        content=ft.Container(expand=True),
        on_hover=lambda e: window._on_camera_label_hover(e),
        on_tap_up=lambda e: window._on_camera_label_tap(e),
    )

    # --- Assemble: Stack for camera overlay elements + bottom panel ---
    return ft.Container(
        content=ft.Column(
            [
                # Camera area with floating overlays (takes remaining space)
                ft.Container(
                    content=ft.Stack(
                        [
                            # Hover detection layer (behind everything, catches mouse events)
                            camera_hover_layer,
                            # Top-center: step indicator (full-width, rendered first = behind)
                            ft.Container(
                                content=ft.Row(
                                    [step_indicator],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                                top=16, left=0, right=0,
                            ),
                            # Top-left: back button (rendered last = on top for clicks)
                            ft.Container(content=back_btn, top=16, left=16),
                        ],
                    ),
                    expand=True,  # Camera area takes remaining vertical space
                ),
                # Bottom: card gallery panel
                card_gallery_panel,
            ],
            spacing=0,
        ),
        expand=True,
    )
