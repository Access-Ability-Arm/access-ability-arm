"""
Flet Main Window
Modern cross-platform GUI using Flet framework
"""

import base64
import threading
import time
from io import BytesIO

import cv2
from aaa_core.config.settings import app_config
from aaa_core.hardware.button_controller import ButtonController
from aaa_core.hardware.camera_manager import CameraManager
from aaa_core.workers.image_processor import ImageProcessor
from PIL import Image

import flet as ft

# Import Flet-compatible arm controller
if app_config.lite6_available:
    from aaa_core.workers.arm_controller_flet import ArmControllerFlet


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
        self.page.title = "Access Ability Arm"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 5
        self.page.window.width = app_config.window_width
        self.page.window.height = app_config.window_height
        self.page.window.resizable = True

        # Initialize components
        self.button_controller = None
        self.arm_controller = None
        self.camera_manager = None
        self.image_processor = None
        self.video_feed = None
        self.status_text = None
        self.camera_dropdown = None
        self.arm_status_text = None

        # Show loading screen immediately
        self._show_initial_loading_screen()

        self._setup_components()
        self._build_ui()
        self._start_image_processor()

    def _show_initial_loading_screen(self):
        """Show loading screen immediately on startup"""
        loading_text = ft.Text(
            "Initializing application...",
            size=18,
            color="#607D8B",
            weight=ft.FontWeight.W_500,
        )

        # Store reference for updates
        self.loading_text = loading_text

        loading_screen = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(color="#607D8B", width=50, height=50),
                    loading_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            bgcolor="#ECEFF1",
            alignment=ft.alignment.center,
            expand=True,
        )

        self.page.add(loading_screen)
        self.page.update()

    def _setup_components(self):
        """Initialize hardware and processing components"""
        # Button controller
        self.loading_text.value = "Initializing button controller..."
        self.page.update()

        self.button_controller = ButtonController(
            hold_threshold=app_config.button_hold_threshold
        )
        self.button_controller.start()  # Start the thread once

        # Arm controller (if available)
        if app_config.lite6_available:
            self.loading_text.value = f"Connecting to arm at {app_config.lite6_ip}..."
            self.page.update()

            self.arm_controller = ArmControllerFlet(
                arm_ip=app_config.lite6_ip,
                port=app_config.lite6_port,
                on_connection_status=self._on_arm_connection_status,
                on_error=self._on_arm_error
            )
            # Try to connect if auto-connect enabled
            if app_config.lite6_auto_connect:
                self.arm_controller.connect_arm()

        # Camera manager
        self.loading_text.value = "Detecting cameras..."
        self.page.update()

        self.camera_manager = CameraManager(
            max_cameras_to_check=app_config.max_cameras_to_check
        )

    def _build_ui(self):
        """Build the Flet UI layout"""
        # Update loading message
        self.loading_text.value = "Building interface..."
        self.page.update()

        # Clear the initial loading screen
        self.page.clean()

        # Video feed display (responsive)
        self.video_feed = ft.Image(
            src_base64="",  # Will be updated by image processor
            fit=ft.ImageFit.CONTAIN,
            border_radius=10,
            expand=True,
        )

        # Loading placeholder (shown until first frame arrives)
        self.camera_loading_text = ft.Text(
            "Loading camera feed...",
            size=16,
            color="#607D8B",  # Blue Grey 500
            weight=ft.FontWeight.W_400,
        )
        self.loading_placeholder = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(color="#607D8B"),  # Blue Grey 500
                    self.camera_loading_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#ECEFF1",  # Light grey (Blue Grey 50)
            border_radius=10,
            alignment=ft.alignment.center,
            visible=True,  # Initially visible
            expand=True,
        )

        # Video container with Stack to overlay loading on video
        self.video_container = ft.Container(
            content=ft.Stack(
                [
                    self.video_feed,
                    self.loading_placeholder,
                ],
                expand=True,
            ),
            expand=True,
        )

        # Track if first frame has been received
        self._first_frame_received = False

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
            value=str(app_config.default_camera) if camera_options else None,
            on_change=self._on_camera_changed,
            width=400,
        )

        # Status display
        self.status_text = ft.Text(
            "Initializing...",
            size=12,
            color="#455A64",  # Blue Grey 700
        )

        # Arm status display - check actual connection status
        arm_connected = (
            app_config.lite6_available
            and self.arm_controller
            and self.arm_controller.is_connected()
        )
        if arm_connected:
            arm_status_text = f"Arm: ✓ Connected ({app_config.lite6_ip})"
            arm_status_color = "#2E7D32"  # Green 800
        else:
            arm_status_text = "Arm: Not connected"
            arm_status_color = "#F57C00"  # Orange 700

        self.arm_status_text = ft.Text(
            arm_status_text,
            size=12,
            color=arm_status_color,
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
                    # Main content area
                    ft.Row(
                        [
                            # Left: Video feed (responsive, takes available space)
                            ft.Container(
                                content=ft.Column(
                                    [
                                        # Video container with loading overlay
                                        self.video_container,
                                        ft.Row(
                                            [
                                                self.camera_dropdown,
                                                self.toggle_mode_btn,
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                    ],
                                    spacing=10,
                                    expand=True,
                                    alignment=ft.MainAxisAlignment.START,  # Align to top
                                ),
                                padding=0,
                                expand=2,  # Takes 2/3 of available space
                                # border=ft.border.all(2, "#FF0000"),  # Red debug border
                            ),
                            # Right: Control panel (fixed width)
                            control_panel,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=20,
                        expand=True,
                    ),
                    # Footer: Status
                    ft.Container(
                        content=ft.Row(
                            [
                                self.status_text,
                                ft.Text(" | ", size=12),
                                self.arm_status_text,
                            ],
                            spacing=5,
                        ),
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
        """Build the robotic arm control panel with Manual/Auto tabs"""

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
                                    icon_size=30,
                                    width=50,
                                    height=50,
                                ),
                                ft.Icon(icon, size=40),
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    tooltip=f"{direction} positive",
                                    on_click=lambda e,
                                    d=direction: self._on_button_press(d, "pos"),
                                    bgcolor="#A5D6A7",  # Green 200
                                    icon_color="#1B5E20",  # Green 900
                                    icon_size=30,
                                    width=50,
                                    height=50,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5,
                ),
                padding=10,
                border=ft.border.all(2, "#CFD8DC"),  # Blue Grey 100
                border_radius=10,
            )

        # Grip state toggle
        grip_toggle = ft.Container(
            content=ft.Column(
                [
                    ft.Text("GRIP STATE", weight=ft.FontWeight.BOLD, size=16),
                    ft.Switch(
                        label="Open/Close",
                        label_style=ft.TextStyle(size=14),
                        on_change=lambda e: self._on_grip_state_changed(
                            e.control.value
                        ),
                        scale=1.0,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=10,
            border=ft.border.all(2, "#CFD8DC"),  # Blue Grey 100
            border_radius=10,
        )

        # Manual controls tab content
        manual_tab_content = ft.Container(
            content=ft.Column(
                [
                    create_direction_controls("x", ft.Icons.SWAP_HORIZ),
                    create_direction_controls("y", ft.Icons.SWAP_VERT),
                    create_direction_controls("z", ft.Icons.HEIGHT),
                    create_direction_controls("grip", ft.Icons.BACK_HAND),
                    grip_toggle,
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

        # Auto controls tab content (placeholder for now)
        auto_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Automatic Controls",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Auto mode controls will be added here",
                        size=12,
                        color="#607D8B",
                        italic=True,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            padding=20,
        )

        # Create tabs
        control_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Manual",
                    icon=ft.Icons.TOUCH_APP,
                    content=manual_tab_content,
                ),
                ft.Tab(
                    text="Auto",
                    icon=ft.Icons.AUTO_MODE,
                    content=auto_tab_content,
                ),
            ],
            height=650,  # Fixed height for tab content (includes tab bar)
        )

        return ft.Container(
            content=control_tabs,
            width=220,
            padding=5,
            bgcolor="#ECEFF1",  # Blue Grey 50
            border_radius=10,
        )

    def _start_image_processor(self):
        """Initialize and start image processing"""
        # Update loading message
        if self.loading_placeholder.visible:
            self.loading_text.value = "Starting camera..."
            self.page.update()

        self.image_processor = ImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
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

            # Hide loading placeholder on first frame
            if not self._first_frame_received:
                self.loading_placeholder.visible = False
                self._first_frame_received = True

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
        self.button_controller.update_button_state("pressed", start_time, button_name)

        # Simulate release after brief moment and execute arm command
        def on_release():
            duration = time.time() - start_time
            self.button_controller.update_button_state("released", 0, button_name)
            self._handle_arm_command(button_name, duration)

        threading.Timer(0.1, on_release).start()

    def _on_grip_state_changed(self, is_closed: bool):
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

    def _handle_arm_command(self, button_name: str, duration: float):
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
        step = (app_config.tap_step_size if duration < app_config.button_hold_threshold
                else app_config.hold_step_size)

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
            # Grip controls are handled separately via gripper position
            current_grip = self.arm_controller.arm.get_gripper_position() or 400
            new_grip = min(800, current_grip + 100)
            self.arm_controller.set_gripper(new_grip, wait=False)
            return
        elif button_name == "grip_neg":
            current_grip = self.arm_controller.arm.get_gripper_position() or 400
            new_grip = max(0, current_grip - 100)
            self.arm_controller.set_gripper(new_grip, wait=False)
            return

        # Send move command
        print(f"Moving to: ({x:.1f}, {y:.1f}, {z:.1f})")
        self.arm_controller.move_to(
            x, y, z, roll, pitch, yaw,
            speed=app_config.movement_speed,
            wait=False
        )

    def _on_arm_connection_status(self, connected: bool, message: str):
        """Handle arm connection status updates"""
        print(f"Arm connection status: {message}")

        # Update initial loading message if still building UI
        if hasattr(self, 'loading_text'):
            if connected:
                self.loading_text.value = "Arm connected. Building interface..."
            else:
                self.loading_text.value = "Arm connection failed. Building interface..."
            self.page.update()

        if self.arm_status_text:
            if connected:
                self.arm_status_text.value = f"Arm: ✓ Connected ({app_config.lite6_ip})"
                self.arm_status_text.color = "#2E7D32"  # Green 800
            else:
                self.arm_status_text.value = f"Arm: ✗ {message}"
                self.arm_status_text.color = "#C62828"  # Red 800
            self.page.update()

    def _on_arm_error(self, error_message: str):
        """Handle arm errors"""
        print(f"Arm error: {error_message}")
        if self.arm_status_text:
            self.arm_status_text.value = f"Arm Error: {error_message}"
            self.arm_status_text.color = "#C62828"  # Red 800
            self.page.update()

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        if self.image_processor:
            self.image_processor.toggle_detection_mode()
            self._update_status()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard shortcuts"""
        if (e.key == "T" and e.shift is False and
                e.ctrl is False and e.alt is False):
            self._toggle_detection_mode()

    def cleanup(self):
        """Clean up resources"""
        if self.image_processor:
            self.image_processor.stop()
        if self.arm_controller:
            self.arm_controller.disconnect_arm()
