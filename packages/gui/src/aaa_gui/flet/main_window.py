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

        # Set window position from config
        self.page.window.left = app_config.window_left
        self.page.window.top = app_config.window_top

        # Listen for window events (resize, move, etc.)
        self.page.window.on_event = self._on_window_event

        # Initialize components
        self.button_controller = None
        self.arm_controller = None
        self.camera_manager = None
        self.image_processor = None
        self.video_feed = None
        self.status_text = None
        self.camera_dropdown = None
        self.arm_status_text = None

        # Movement speed percentage (1-100%)
        self.movement_speed_percent = 20  # Default 20%

        # Video freeze state for object detection
        self.video_frozen = False
        self.frozen_frame = None
        self.frozen_detections = None  # Store detection data when frozen
        self.object_buttons = []  # Store overlay buttons for frozen objects
        self.selected_object = None  # Currently selected object index

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
            self.arm_controller = ArmControllerFlet(
                arm_ip=app_config.lite6_ip,
                port=app_config.lite6_port,
                on_connection_status=self._on_arm_connection_status,
                on_error=self._on_arm_error
            )
            # Connect asynchronously in background thread if auto-connect enabled
            if app_config.lite6_auto_connect:
                def connect_async():
                    print(f"[Arm] Connecting to arm at {app_config.lite6_ip}...")
                    self.arm_controller.connect_arm()

                threading.Thread(target=connect_async, daemon=True).start()

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
        # Set fixed height to prevent layout shift when camera loads
        self.video_container = ft.Container(
            content=ft.Stack(
                [
                    self.video_feed,
                    self.loading_placeholder,
                ],
                expand=True,
            ),
            height=app_config.display_height,  # Fixed height from config (650px)
            expand=True,
        )

        # Object selection buttons (shown when frozen)
        self.object_buttons_row = ft.Row(
            controls=[],
            spacing=10,
            wrap=True,
            visible=False,
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
                                        # Object selection buttons (shown when frozen)
                                        self.object_buttons_row,
                                        # Camera controls and status
                                        ft.Column(
                                            [
                                                ft.Row(
                                                    [
                                                        self.camera_dropdown,
                                                        self.toggle_mode_btn,
                                                    ],
                                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                ),
                                                # Status row
                                                ft.Row(
                                                    [
                                                        self.status_text,
                                                        ft.Text(" | ", size=12),
                                                        self.arm_status_text,
                                                    ],
                                                    spacing=5,
                                                ),
                                            ],
                                            spacing=5,
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

        # Speed slider
        self.speed_label = ft.Text(
            f"Speed: {self.movement_speed_percent}%",
            size=14,
            weight=ft.FontWeight.BOLD,
        )

        speed_slider = ft.Slider(
            min=1,
            max=100,
            value=self.movement_speed_percent,
            divisions=99,
            label="{value}%",
            on_change=self._on_speed_changed,
        )

        speed_control = ft.Container(
            content=ft.Column(
                [
                    self.speed_label,
                    speed_slider,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            padding=10,
            border=ft.border.all(2, "#CFD8DC"),  # Blue Grey 100
            border_radius=10,
        )

        # Manual controls tab content
        manual_tab_content = ft.Container(
            content=ft.Column(
                [
                    speed_control,
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

        # Auto controls tab content
        auto_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Automatic Controls",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    # Find Objects button
                    ft.ElevatedButton(
                        text="Find Objects",
                        icon=ft.Icons.SEARCH,
                        on_click=lambda e: self._on_find_objects(),
                        bgcolor="#2196F3",  # Blue 500
                        color="#FFFFFF",
                        width=180,
                        height=50,
                    ),
                    # Execute button
                    ft.ElevatedButton(
                        text="Execute",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=lambda e: self._on_execute(),
                        bgcolor="#4CAF50",  # Green 500
                        color="#FFFFFF",
                        width=180,
                        height=50,
                    ),
                    # Stop button
                    ft.ElevatedButton(
                        text="Stop",
                        icon=ft.Icons.STOP,
                        on_click=lambda e: self._on_stop(),
                        bgcolor="#F44336",  # Red 500
                        color="#FFFFFF",
                        width=180,
                        height=50,
                    ),
                    # Home button
                    ft.ElevatedButton(
                        text="Home",
                        icon=ft.Icons.HOME,
                        on_click=lambda e: self._on_home(),
                        bgcolor="#FF9800",  # Orange 500
                        color="#FFFFFF",
                        width=180,
                        height=50,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
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
            height=750,  # Fixed height for tab content (includes tab bar + speed slider)
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
            "combined": "Combined (Face + Objects)",
            "camera": "Camera Only"
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
            img_array: Numpy array (RGB format from image processor)
        """
        try:
            # If video is frozen, store current frame and display frozen frame with enhanced labels
            if self.video_frozen:
                if self.frozen_frame is None:
                    # First frame after freezing - store it and enhance labels
                    self.frozen_frame, self.frozen_detections = self._enhance_frozen_labels(img_array.copy())
                    self._create_object_buttons()
                    print("Find Objects: Frame captured and frozen")
                # Display the frozen frame
                img_array = self.frozen_frame

            # Image is already in RGB format from image_processor
            # Convert to PIL Image
            pil_image = Image.fromarray(img_array)

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

    def _enhance_frozen_labels(self, img_array):
        """
        Enhance object labels for frozen frame with larger numbered labels

        Args:
            img_array: Numpy array (RGB format) with existing detections

        Returns:
            Tuple of (image with enhanced labels, detection data dict)
        """
        if not self.image_processor or self.image_processor.detection_mode != "objects":
            return img_array, None

        # Get detection manager
        detection_mgr = self.image_processor.detection_manager
        if not detection_mgr.segmentation_model:
            return img_array, None

        # Get a fresh frame without labels - re-detect on original image
        # First, detect objects to get data
        (boxes, classes, contours, centers) = detection_mgr.segmentation_model.detect_objects_mask(img_array)

        # Store detection data for button creation
        detections = {
            'classes': classes,
            'centers': centers,
            'boxes': boxes,
            'contours': contours
        }

        # Draw only the masks, not the labels
        img_with_masks = detection_mgr.segmentation_model.draw_object_mask(
            img_array, boxes, classes, contours
        )

        # Now draw our enhanced numbered labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.1  # 3x larger than typical 0.7
        thickness = 4  # Thicker for readability
        padding = 10  # Padding around text

        for i, (center, class_name) in enumerate(zip(centers, classes), start=1):
            x, y = center

            # Create numbered label
            label = f"#{i}: {class_name}"

            # Get text size for background
            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, font_scale, thickness
            )

            # Calculate background rectangle with proper padding
            # Text origin is at bottom-left, so we need to adjust for that
            bg_x1 = x - padding
            bg_y1 = y - text_height - padding
            bg_x2 = x + text_width + padding
            bg_y2 = y + baseline + padding

            # Draw background rectangle
            cv2.rectangle(
                img_with_masks,
                (bg_x1, bg_y1),
                (bg_x2, bg_y2),
                (0, 0, 0),  # Black background
                -1
            )

            # Draw text (origin at bottom-left of text)
            cv2.putText(
                img_with_masks,
                label,
                (x, y),
                font,
                font_scale,
                (0, 255, 0),  # Green text
                thickness
            )

        return img_with_masks, detections

    def _create_object_buttons(self):
        """Create clickable buttons for each detected object"""
        if not self.frozen_detections:
            return

        # Clear existing buttons
        self.object_buttons_row.controls.clear()

        # Create a button for each detected object
        classes = self.frozen_detections['classes']
        for i, class_name in enumerate(classes, start=1):
            btn = ft.ElevatedButton(
                text=f"#{i}: {class_name}",
                on_click=lambda e, idx=i-1: self._on_object_selected(idx),
                bgcolor=ft.Colors.BLUE_GREY_800,
                color=ft.Colors.WHITE,
            )
            self.object_buttons_row.controls.append(btn)

        # Show the button row
        self.object_buttons_row.visible = True
        self.page.update()

    def _on_object_selected(self, object_index: int):
        """Handle object button click"""
        self.selected_object = object_index
        classes = self.frozen_detections['classes']
        class_name = classes[object_index]

        print(f"Selected object #{object_index + 1}: {class_name}")

        # Highlight the selected button
        for i, btn in enumerate(self.object_buttons_row.controls):
            if i == object_index:
                btn.bgcolor = ft.Colors.GREEN_700
            else:
                btn.bgcolor = ft.Colors.BLUE_GREY_800

        self.page.update()

    def _clear_object_buttons(self):
        """Clear object selection buttons when unfreezing"""
        self.object_buttons_row.controls.clear()
        self.object_buttons_row.visible = False
        self.selected_object = None
        self.page.update()

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

    def _on_speed_changed(self, e):
        """Handle speed slider change"""
        self.movement_speed_percent = int(e.control.value)
        self.speed_label.value = f"Speed: {self.movement_speed_percent}%"
        self.page.update()
        print(f"Movement speed set to: {self.movement_speed_percent}%")

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
        base_step = (app_config.tap_step_size if duration < app_config.button_hold_threshold
                     else app_config.hold_step_size)

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
        movement_speed = app_config.movement_speed * (self.movement_speed_percent / 100.0)
        print(f"Moving to: ({x:.1f}, {y:.1f}, {z:.1f}) at {self.movement_speed_percent}% speed")
        self.arm_controller.move_to(
            x, y, z, roll, pitch, yaw,
            speed=movement_speed,
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

    def _on_window_event(self, e):
        """Handle window events (resized, moved, etc.)"""
        from aaa_core.config.settings import save_window_geometry

        # Save geometry on resized or moved events
        if e.data in ("resized", "moved"):
            if (self.page.window.width and self.page.window.height and
                self.page.window.left is not None and self.page.window.top is not None):
                save_window_geometry(
                    width=int(self.page.window.width),
                    height=int(self.page.window.height),
                    left=int(self.page.window.left),
                    top=int(self.page.window.top)
                )

    def _on_find_objects(self):
        """Handle Find Objects button - switch to object detection and capture for 1 second"""
        if not self.image_processor:
            print("Find Objects: Image processor not ready")
            return

        if not self.video_frozen:
            # First click: switch to object detection mode, capture for 1 second, then freeze
            print("Find Objects: Switching to object detection mode...")

            # Switch to object detection mode
            current_mode = self.image_processor.detection_mode
            if current_mode != "objects":
                self.image_processor.set_detection_mode("objects")
                self._update_status()

            # Capture video for 1 second then freeze
            def capture_and_freeze():
                time.sleep(1.0)
                self.video_frozen = True
                print("Find Objects: Video frozen on detected objects")

            threading.Thread(target=capture_and_freeze, daemon=True).start()
        else:
            # Second click: unfreeze and capture for 1 second, then freeze again
            print("Find Objects: Capturing new frame...")
            self.video_frozen = False
            self.frozen_frame = None
            self._clear_object_buttons()

            # Capture video for 1 second then freeze again
            def capture_and_freeze():
                time.sleep(1.0)
                self.video_frozen = True
                print("Find Objects: Video frozen on new frame")

            threading.Thread(target=capture_and_freeze, daemon=True).start()

    def _on_execute(self):
        """Handle Execute button - confirms grasp plan and begins arm motion"""
        print("Execute: Beginning grasp motion...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected - cannot execute grasp")
            return

        # TODO: Implement grasp execution logic
        # - Move to pre-grasp position
        # - Approach target object
        # - Close gripper
        # - Lift object
        # - Move to drop position
        print("Grasp execution not yet implemented")

    def _on_stop(self):
        """Handle Stop button - immediately halts all arm movement"""
        print("Stop: Halting all arm movement...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected")
            return

        # Emergency stop - halt all motion immediately
        self.arm_controller.emergency_stop()
        print("Arm stopped")

    def _on_home(self):
        """Handle Home button - returns arm to safe rest position"""
        print("Home: Returning to rest position...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected - cannot move to home")
            return

        # Move to home position
        self.arm_controller.home()
        print("Moving to home position")

    def cleanup(self):
        """Clean up resources"""
        if self.image_processor:
            self.image_processor.stop()
        if self.arm_controller:
            self.arm_controller.disconnect_arm()
