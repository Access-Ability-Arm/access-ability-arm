"""
Flet Main Window
Modern cross-platform GUI using Flet framework
"""

import base64
import threading
import time
from io import BytesIO

import cv2
import flet as ft
import numpy as np
from PIL import Image

from config.settings import app_config
from hardware.button_controller import ButtonController
from hardware.camera_manager import CameraManager
from workers.image_processor import ImageProcessor


class FletMainWindow:
    """Main application window using Flet"""

    ARM_DIRECTIONS = ["x", "y", "z", "grip"]

    def __init__(self, page: ft.Page):
        """
        Initialize Flet main window

        Args:
            page: Flet page object
        """
        self.page = page
        self.page.title = "DE-GUI - Assistive Robotic Arm"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 20
        self.page.window.width = 1280
        self.page.window.height = 1000
        self.page.window.resizable = True

        # Initialize components
        self.button_controller = None
        self.camera_manager = None
        self.image_processor = None
        self.video_feed = None
        self.status_text = None
        self.camera_dropdown = None

        self._setup_components()
        self._build_ui()
        self._start_image_processor()

    def _setup_components(self):
        """Initialize hardware and processing components"""
        # Button controller
        self.button_controller = ButtonController(
            hold_threshold=app_config.button_hold_threshold
        )

        # Camera manager
        self.camera_manager = CameraManager(
            max_cameras_to_check=app_config.max_cameras_to_check
        )

    def _build_ui(self):
        """Build the Flet UI layout"""
        # Video feed display - create placeholder
        # Create a minimal 1x1 transparent PNG as base64 placeholder
        placeholder_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        self.video_feed = ft.Image(
            src_base64=placeholder_base64,
            width=800,
            height=650,
            fit=ft.ImageFit.CONTAIN,
            border_radius=10,
        )

        # Camera selection
        cameras = self.camera_manager.get_camera_info()
        camera_options = [
            ft.dropdown.Option(
                key=str(cam["camera_index"]),
                text=f"Camera {cam['camera_index']}: {cam['camera_name']}",
            )
            for cam in cameras
        ]

        self.camera_dropdown = ft.Dropdown(
            label="Select Camera",
            options=camera_options,
            value="0" if camera_options else None,
            on_change=self._on_camera_changed,
            width=300,
        )

        # Status display
        self.status_text = ft.Text(
            "Initializing...",
            size=12,
            color="#455A64",  # Blue Grey 700
        )

        # Detection mode toggle button
        self.toggle_mode_btn = ft.ElevatedButton(
            text="Toggle Detection Mode (T)",
            icon=ft.Icons.SWAP_HORIZ,
            on_click=lambda _: self._toggle_detection_mode(),
        )

        # Control panel with robotic arm buttons
        control_panel = self._build_control_panel()

        # Main layout
        self.page.add(
            ft.Column(
                [
                    # Header
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.PRECISION_MANUFACTURING, size=40),
                                ft.Text(
                                    "DE-GUI Assistive Robotic Arm",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        margin=ft.margin.only(bottom=20),
                    ),
                    # Main content area
                    ft.Row(
                        [
                            # Left: Video feed
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Container(
                                            content=self.video_feed,
                                            border=ft.border.all(
                                                2,
                                                "#B0BEC5",  # Blue Grey 200
                                            ),
                                            border_radius=10,
                                        ),
                                        ft.Row(
                                            [
                                                self.camera_dropdown,
                                                self.toggle_mode_btn,
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                padding=10,
                            ),
                            # Right: Control panel
                            control_panel,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=20,
                    ),
                    # Footer: Status
                    ft.Container(
                        content=self.status_text,
                        margin=ft.margin.only(top=10),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            )
        )

        # Keyboard shortcuts
        self.page.on_keyboard_event = self._on_keyboard_event

    def _build_control_panel(self) -> ft.Container:
        """Build the robotic arm control panel"""

        def create_direction_controls(direction: str, icon: str) -> ft.Container:
            """Create positive/negative button pair for a direction"""
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(direction.upper(), weight=ft.FontWeight.BOLD, size=16),
                        ft.Row(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.REMOVE,
                                    tooltip=f"{direction} negative",
                                    on_click=lambda e,
                                    d=direction: self._on_button_press(d, "neg"),
                                    bgcolor="#EF9A9A",  # Red 200
                                    icon_color="#B71C1C",  # Red 900
                                ),
                                ft.Icon(icon, size=30),
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    tooltip=f"{direction} positive",
                                    on_click=lambda e,
                                    d=direction: self._on_button_press(d, "pos"),
                                    bgcolor="#A5D6A7",  # Green 200
                                    icon_color="#1B5E20",  # Green 900
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5,
                ),
                padding=10,
                border=ft.border.all(1, "#CFD8DC"),  # Blue Grey 100
                border_radius=10,
            )

        # Grip state toggle
        grip_toggle = ft.Container(
            content=ft.Column(
                [
                    ft.Text("GRIP STATE", weight=ft.FontWeight.BOLD, size=16),
                    ft.Switch(
                        label="Open/Close",
                        on_change=lambda e: self._on_grip_state_changed(
                            e.control.value
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=10,
            border=ft.border.all(1, "#CFD8DC"),  # Blue Grey 100
            border_radius=10,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Manual Controls",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    create_direction_controls("x", ft.Icons.SWAP_HORIZ),
                    create_direction_controls("y", ft.Icons.SWAP_VERT),
                    create_direction_controls("z", ft.Icons.HEIGHT),
                    create_direction_controls("grip", ft.Icons.BACK_HAND),
                    grip_toggle,
                ],
                spacing=15,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=300,
            padding=20,
            bgcolor="#ECEFF1",  # Blue Grey 50
            border_radius=10,
        )

    def _start_image_processor(self):
        """Initialize and start image processing"""
        self.image_processor = ImageProcessor(
            display_width=800,
            display_height=650,
            callback=self._update_video_feed,  # Use callback for Flet
        )

        # Start processing thread
        self.image_processor.start()

        # Update status
        self._update_status()

    def _update_status(self):
        """Update status display"""
        realsense_status = (
            "✓ Available" if self.image_processor.use_realsense else "✗ Not available"
        )

        seg_model = (
            app_config.segmentation_model.upper()
            if app_config.segmentation_model
            else "None"
        )
        seg_status = (
            seg_model
            if self.image_processor.has_object_detection
            else "✗ Not available"
        )

        mode = self.image_processor.detection_mode

        # Format mode name for display
        mode_display = {
            "face": "Face Tracking",
            "objects": "Object Detection",
            "combined": "Combined (Face + Objects)"
        }.get(mode, mode.upper())

        status_msg = (
            f"RealSense: {realsense_status} | "
            f"Detection: {seg_status} | "
            f"Mode: {mode_display}"
        )

        self.status_text.value = status_msg
        self.page.update()

    def _update_video_feed(self, img_array):
        """
        Update video feed with new frame

        Args:
            img_array: Numpy array (BGR format from OpenCV)
        """
        try:
            # Convert BGR to RGB
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)

            # Convert to PIL Image
            pil_image = Image.fromarray(img_rgb)

            # Convert to base64
            buffered = BytesIO()
            pil_image.save(buffered, format="JPEG", quality=85)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            # Update Flet image
            self.video_feed.src_base64 = img_base64
            self.page.update()

        except Exception as e:
            print(f"Error updating video feed: {e}")

    def _on_camera_changed(self, e):
        """Handle camera selection change"""
        if e.control.value:
            camera_index = int(e.control.value)
            print(f"Switching to camera {camera_index}")
            self.image_processor.camera_changed(camera_index)

    def _on_button_press(self, direction: str, button_type: str):
        """Handle robotic arm button press"""
        button_name = f"{direction}_{button_type}"
        print(f"Button {button_name} pressed")

        start_time = time.time()
        self.button_controller.start()
        self.button_controller.update_button_state("pressed", start_time, button_name)

        # Simulate release after brief moment (you would connect to actual button release events)
        threading.Timer(
            0.1,
            lambda: self.button_controller.update_button_state(
                "released", 0, button_name
            ),
        ).start()

    def _on_grip_state_changed(self, is_closed: bool):
        """Handle grip state toggle"""
        state = "closed" if is_closed else "open"
        print(f"Grip state: {state}")
        self.button_controller.update_button_state("clicked", 0, "grip_state")

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        if self.image_processor:
            self.image_processor.toggle_detection_mode()
            self._update_status()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard shortcuts"""
        if e.key == "T" and e.shift == False and e.ctrl == False and e.alt == False:
            self._toggle_detection_mode()

    def cleanup(self):
        """Clean up resources"""
        if self.image_processor:
            self.image_processor.stop()
