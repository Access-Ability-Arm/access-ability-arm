"""
Flet Main Window
Modern cross-platform GUI using Flet framework
"""

import base64
import sys
import threading
import time
from io import BytesIO

import cv2
import numpy as np
from aaa_core.config.settings import app_config
from aaa_core.hardware.button_controller import ButtonController
from aaa_core.hardware.camera_manager import CameraManager
from aaa_core.workers.image_processor import ImageProcessor
from PIL import Image, ImageDraw, ImageFont

# Try to import daemon components (may not be available)
try:
    from aaa_core.daemon.camera_client import CameraClient
    from aaa_core.workers.daemon_image_processor import DaemonImageProcessor

    DAEMON_AVAILABLE = True
except ImportError:
    DAEMON_AVAILABLE = False

# Try to detect a default calibration if present
try:
    from aaa_vision.calibration import try_load_calibration
except Exception:
    try_load_calibration = None

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

        # Intercept window close to cleanup properly
        self.page.window.prevent_close = True

        # Listen for window events (resize, move, close, etc.)
        self.page.window.on_event = self._on_window_event

        # Initialize components
        self.button_controller = None
        self.arm_controller = None
        self.arm_connect_btn = None
        self.camera_manager = None
        self.image_processor = None
        self.video_feed = None
        self.status_text = None
        self.camera_dropdown = None
        self.arm_status_text = None
        self.show_points_btn = (
            None  # Button to show sampled mask points on frozen frame
        )

        # Movement speed percentage (1-100%)
        self.movement_speed_percent = 20  # Default 20%

        # RealSense exposure control
        self.exposure_slider = None
        self.exposure_value_text = None
        self.using_realsense = False

        # Video freeze state for object detection
        self.video_frozen = False
        self.frozen_frame = None
        self.frozen_detections = None  # Store detection data when frozen
        self.frozen_raw_frame = None  # Store the raw frozen frame for re-highlighting
        self.frozen_depth_frame = (
            None  # Store depth frame at freeze time (if available)
        )
        self.frozen_aligned_color = None  # Store aligned color (848x480) at freeze time
        self.object_analysis = None  # ObjectAnalysis result for selected object
        self._analysis_in_progress = False  # Flag for background analysis thread
        self.last_exported_ply = None  # Path to the last exported PLY file
        self._overlay_points = None  # Temporary overlay points to show on frozen frame
        # Whether to apply the depth->color calibration when aligning views
        self.apply_calibration_enabled = bool(app_config.camera_calibration_enabled)
        self.object_buttons = []  # Store overlay buttons for frozen objects
        self.selected_object = None  # Currently selected object index

        # Track if UI is built to avoid page.update() during initialization
        self._ui_built = False

        # Show loading screen immediately
        print("[DEBUG] Showing initial loading screen...")
        self._show_initial_loading_screen()

        print("[DEBUG] Setting up components...")
        self._setup_components()

        print("[DEBUG] Building UI...", flush=True)
        self._build_ui()
        print("[DEBUG] Starting image processor...")
        self._start_image_processor()
        print("[DEBUG] Initialization complete!")

    def _show_initial_loading_screen(self):
        """Show loading screen immediately on startup"""
        print("[DEBUG] _show_initial_loading_screen: creating widgets...", flush=True)
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

        print("[DEBUG] _show_initial_loading_screen: adding to page...", flush=True)
        self.page.add(loading_screen)
        print(
            "[DEBUG] _show_initial_loading_screen: calling page.update()...", flush=True
        )
        self.page.update()
        print("[DEBUG] _show_initial_loading_screen: done", flush=True)

    def _setup_components(self):
        """Initialize hardware and processing components"""
        # Button controller
        print("[DEBUG] Creating button controller...")
        self.button_controller = ButtonController(
            hold_threshold=app_config.button_hold_threshold
        )
        self.button_controller.start()  # Start the thread once

        # Arm controller (if available)
        if app_config.lite6_available:
            print("[DEBUG] Creating arm controller...")
            self.arm_controller = ArmControllerFlet(
                arm_ip=app_config.lite6_ip,
                port=app_config.lite6_port,
                on_connection_status=self._on_arm_connection_status,
                on_error=self._on_arm_error,
            )
            print("[DEBUG] Arm controller created")
            # Auto-connect to arm in a background thread if enabled in config.
            if app_config.lite6_auto_connect:
                print(
                    "[DEBUG] Auto-connect enabled - starting background connection thread for arm..."
                )
                try:

                    def connect_async():
                        try:
                            print(
                                f"[Arm] Connecting to arm at {app_config.lite6_ip}:{app_config.lite6_port}..."
                            )
                            self.arm_controller.connect_arm()
                        except Exception as e:
                            print(f"[Arm] Async connect failed: {e}")

                    t = threading.Thread(target=connect_async, daemon=True)
                    print("[DEBUG] About to start arm thread...", flush=True)
                    t.start()
                    print(
                        "[DEBUG] Background arm connection thread started", flush=True
                    )
                except Exception as e:
                    print(
                        f"[DEBUG] Failed to start arm connection thread: {e}",
                        flush=True,
                    )

        print("[DEBUG] After arm controller section", flush=True)

        # Debug: write to file since stdout/stderr might be captured
        import sys
        import time

        print("[DEBUG] step A", file=sys.stderr, flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        # Camera manager
        time.sleep(0.1)  # Small delay to let arm thread settle

        # NOTE: Skipping print() here - Flet blocks stdout after page.update()
        try:
            self.camera_manager = CameraManager(
                max_cameras_to_check=app_config.max_cameras_to_check
            )
            print("[DEBUG] Camera manager created", flush=True)
        except Exception as e:
            print(f"[DEBUG] CameraManager failed: {e}", flush=True)
            import traceback

            traceback.print_exc()
            raise

        # Check for RealSense without daemon on macOS
        self._check_realsense_daemon_warning()
        print("[DEBUG] _setup_components complete")

    def _check_realsense_daemon_warning(self):
        """Check if RealSense is detected but daemon isn't running on macOS"""
        import os
        import platform

        # Only check on macOS
        if platform.system() != "Darwin":
            return

        # Check if any RealSense cameras are detected
        has_realsense = any(
            "RealSense" in cam.get("camera_name", "")
            for cam in self.camera_manager.cameras
        )

        if not has_realsense:
            return

        # Check if daemon is running
        daemon_running = os.path.exists("/tmp/aaa_camera.sock")

        if not daemon_running:
            # Show warning to user
            from aaa_core.config.console import info, warning

            print("")
            warning("=" * 60)
            warning("RealSense camera detected but daemon is not running!")
            warning("=" * 60)
            info("On macOS, RealSense requires the camera daemon for proper access.")
            info("Without the daemon, the camera will crash or show only infrared.")
            print("")
            info("To use RealSense with depth sensing:")
            info("  1. Stop this app (Ctrl+C)")
            info("  2. Run: make daemon-start")
            info("  3. Then run: make run")
            print("")
            info("Or use the combined command: make run-with-daemon")
            warning("=" * 60)
            print("")

            # Store flag so we can show in-app warning too
            self._realsense_daemon_warning = True
        else:
            self._realsense_daemon_warning = False

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

        # Check if daemon is running to determine camera options
        daemon_running = self._check_daemon_running()
        # Skip print - Flet blocks stdout

        # Camera selection - build list of available cameras
        cameras = self.camera_manager.get_camera_info()
        camera_options = []

        # If daemon is running, add it as the first option
        if daemon_running:
            camera_options.append(
                ft.dropdown.Option(
                    key="daemon",
                    text="RealSense D435 (via daemon - with depth)",
                )
            )

        # Add other available cameras
        for cam in cameras:
            # Hide infrared cameras - they cause crashes and aren't useful for this app
            if cam.get("color_type") == "Infrared":
                print(
                    f"[DEBUG] Hiding infrared camera from dropdown: [{cam['camera_index']}] {cam['camera_name']}"
                )
                continue

            # On macOS, RealSense cameras crash when accessed via OpenCV and require
            # sudo for USB access. Hide them from dropdown - use daemon instead.
            # On Windows/Linux, RealSense can be accessed directly via OpenCV.
            if sys.platform == "darwin" and "RealSense" in cam["camera_name"]:
                print(
                    f"[DEBUG] Hiding RealSense camera from dropdown (macOS requires daemon): {cam['camera_name']}"
                )
                continue

            # Shorten long camera names for better display
            name = cam["camera_name"]
            if len(name) > 70:
                # Truncate but keep important parts
                name = name[:67] + "..."

            # For RealSense cameras, show actual SDK resolution (not OpenCV default)
            resolution = cam["resolution"]
            if "RealSense" in cam["camera_name"] and resolution == "640x480":
                resolution = "1920x1080"  # RealSense SDK uses this for RGB

            display_text = (
                f"[{cam['camera_index']}] {name} - {resolution} ({cam['color_type']})"
            )
            camera_options.append(
                ft.dropdown.Option(
                    key=str(cam["camera_index"]),
                    text=display_text,
                )
            )

        # Create dropdown or text based on number of options
        if len(camera_options) == 1:
            # Single camera: show as text
            camera_display_text = f"Camera: {camera_options[0].text}"
            self.camera_dropdown = ft.Text(
                camera_display_text,
                size=14,
                weight=ft.FontWeight.W_500,
                color="#1976D2",  # Blue 700
            )
            self.camera_dropdown.value = camera_options[0].key
            print(f"[DEBUG] Single camera detected: {camera_options[0].text}")
        else:
            # Multiple cameras: show dropdown
            # Default to daemon if available, otherwise first camera
            dropdown_value = (
                "daemon"
                if daemon_running
                else (str(app_config.default_camera) if camera_options else None)
            )
            self.camera_dropdown = ft.Dropdown(
                label="Select Camera",
                options=camera_options,
                value=dropdown_value,
                on_change=self._on_camera_changed,
                width=600,  # Increased width to accommodate more info
                disabled=False,
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

        # Connect/Disconnect button (created here so it can be placed inline)
        def _connect_click(e):
            self._on_connect_arm(e)

        self.arm_connect_btn = ft.ElevatedButton(
            text="Connect Arm" if not arm_connected else "Disconnect Arm",
            on_click=_connect_click,
            width=140,
        )

        # Flip camera button
        self.flip_camera_btn = ft.IconButton(
            icon=ft.Icons.FLIP,
            tooltip="Flip camera horizontally (mirror)",
            on_click=lambda _: self._on_flip_camera(),
            bgcolor="#E0E0E0",  # Grey 300
            icon_color="#424242",  # Grey 800
        )

        # Depth visualization toggle button (only shown when depth available)
        self.depth_toggle_btn = ft.IconButton(
            icon=ft.Icons.LAYERS,
            tooltip="Toggle RGB/Depth view",
            on_click=lambda _: self._on_toggle_depth_view(),
            bgcolor="#E0E0E0",  # Grey 300
            icon_color="#424242",  # Grey 800
            visible=False,  # Hidden until depth is available
        )

        # Calibration apply toggle (next to depth toggle) - hidden until a calibration file is configured
        self.calib_toggle_btn = ft.IconButton(
            icon=ft.Icons.LINK,
            tooltip=(
                "Apply depth->color calibration (enabled)"
                if app_config.camera_calibration_enabled
                else "Apply depth->color calibration (disabled)"
            ),
            on_click=lambda _: self._on_toggle_apply_calibration(),
            bgcolor=("#2196F3" if app_config.camera_calibration_enabled else "#E0E0E0"),
            icon_color=("#FFFFFF" if app_config.camera_calibration_enabled else "#424242"),
            visible=False,
        )

        # Refresh camera view button (only shown on Auto tab when frozen)
        self.refresh_camera_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refresh camera view",
            on_click=lambda _: self._on_refresh_camera(),
            bgcolor="#E0E0E0",  # Grey 300
            icon_color="#424242",  # Grey 800
            visible=False,  # Hidden by default (Manual tab is default)
        )

        # RealSense exposure slider (hidden by default, shown when RealSense detected)
        self.exposure_value_text = ft.Text("Exposure: 800", size=12, color="#666")
        self.exposure_slider = ft.Slider(
            min=100,
            max=4000,
            value=800,
            divisions=78,
            label="Exposure: {value}",
            on_change=self._on_exposure_change,
            visible=False,  # Hidden until RealSense detected
            width=300,
        )

        # Auto-exposure state
        self.auto_exposure_enabled = False
        self.auto_exposure_thread = None

        # Auto-exposure button
        self.auto_exposure_btn = ft.IconButton(
            icon=ft.Icons.AUTO_MODE,
            tooltip="Auto-adjust exposure based on image brightness",
            on_click=lambda _: self._auto_adjust_exposure(),
            bgcolor="#E0E0E0",
            icon_color="#424242",
            visible=False,
        )
        self.exposure_controls = ft.Row(
            [
                ft.Icon(ft.Icons.BRIGHTNESS_6, size=16, color="#666"),
                self.exposure_slider,
                self.exposure_value_text,
                self.auto_exposure_btn,
            ],
            visible=False,  # Hidden until RealSense detected
            spacing=10,
        )

        # Show Points button (created here so reference can be enabled/disabled later)
        self.show_points_btn = ft.ElevatedButton(
            text="Show Points",
            icon=ft.Icons.VISIBILITY,
            on_click=lambda e: self._on_show_points(e),
            bgcolor="#795548",  # Brown 500
            color="#FFFFFF",
            width=135,
            height=38,
            disabled=True,
        )

        # Control panel with robotic arm buttons
        control_panel = self._build_control_panel()

        # RealSense daemon warning banner (shown if RealSense detected but daemon not running)
        realsense_warning_banner = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING, color="#FFFFFF", size=20),
                    ft.Text(
                        "RealSense detected but daemon not running. Run 'make daemon-start' then 'make run' for depth sensing.",
                        color="#FFFFFF",
                        size=13,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=10,
            ),
            bgcolor="#E65100",  # Orange 900
            padding=10,
            border_radius=5,
            visible=getattr(self, "_realsense_daemon_warning", False),
        )

        # Main layout

        self.page.add(
            ft.Column(
                [
                    # RealSense warning banner (if applicable)
                    realsense_warning_banner,
                    # Main content area
                    ft.Row(
                        [
                            # Left: Video feed (responsive, takes available space)
                            ft.Container(
                                content=ft.Column(
                                    [
                                        # Video container with loading overlay
                                        self.video_container,
                                        # Camera controls and status
                                        ft.Column(
                                            [
                                                ft.Row(
                                                    [
                                                        self.camera_dropdown,
                                                        self.flip_camera_btn,
                                                        self.depth_toggle_btn,
                                                        self.refresh_camera_btn,
                                                        self.arm_connect_btn,
                                                        # RealSense exposure controls (shown only for RealSense, inline with buttons)
                                                        self.exposure_controls,
                                                    ],
                                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                ),
                                                # Calibration toggle (placed below the main controls for visibility)
                                                ft.Row(
                                                    [
                                                        self.calib_toggle_btn,
                                                    ],
                                                    alignment=ft.MainAxisAlignment.START,
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

        # Mark UI as built to allow page.update() in callbacks
        self._ui_built = True

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
                                    on_click=lambda e, d=direction: (
                                        self._on_button_press(d, "neg")
                                    ),
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
                                    on_click=lambda e, d=direction: (
                                        self._on_button_press(d, "pos")
                                    ),
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
                scroll=ft.ScrollMode.ALWAYS,  # Always show scrollbar for menu buttons
                expand=True,  # Fill available space in parent
            ),
            padding=10,
            expand=True,  # Expand to fill tab space
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
                        width=135,
                        height=38,
                    ),
                    # Object selection buttons (shown when frozen)
                    self.object_buttons_row,
                    # Execute button
                    ft.ElevatedButton(
                        text="Execute",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=lambda e: self._on_execute(),
                        bgcolor="#4CAF50",  # Green 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    # Stop button
                    ft.ElevatedButton(
                        text="Stop",
                        icon=ft.Icons.STOP,
                        on_click=lambda e: self._on_stop(),
                        bgcolor="#F44336",  # Red 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    # Home button
                    ft.ElevatedButton(
                        text="Home",
                        icon=ft.Icons.HOME,
                        on_click=lambda e: self._on_home(),
                        bgcolor="#FF9800",  # Orange 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    # Export point cloud for selected object
                    ft.ElevatedButton(
                        text="Export PointCloud",
                        icon=ft.Icons.CLOUD_UPLOAD,
                        on_click=lambda e: self._export_selected_object_pointcloud(e),
                        bgcolor="#3F51B5",  # Indigo 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    # Export full depth frame as NPZ (whole point cloud)
                    ft.ElevatedButton(
                        text="Export Full PC",
                        icon=ft.Icons.CLOUD_DOWNLOAD,
                        on_click=lambda e: self._export_full_pointcloud(e),
                        bgcolor="#283593",  # Indigo 800
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    ft.ElevatedButton(
                        text="Export PLY",
                        icon=ft.Icons.FILE_DOWNLOAD,
                        on_click=lambda e: self._export_selected_object_ply(e),
                        bgcolor="#009688",  # Teal 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    ft.ElevatedButton(
                        text="Preview PLY",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda e: self._preview_selected_object_ply(e),
                        bgcolor="#607D8B",  # Blue Grey 500
                        color="#FFFFFF",
                        width=135,
                        height=38,
                    ),
                    # Show sampled mask points overlay for selected object
                    (
                        self.show_points_btn
                        if self.show_points_btn is not None
                        else ft.ElevatedButton(
                            text="Show Points",
                            icon=ft.Icons.VISIBILITY,
                            on_click=lambda e: self._on_show_points(e),
                            bgcolor="#795548",  # Brown 500
                            color="#FFFFFF",
                            width=135,
                            height=38,
                            disabled=True,
                        )
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                scroll=ft.ScrollMode.ALWAYS,  # Always show scrollbar for menu buttons
                expand=True,  # Fill available space in parent
            ),
            padding=20,
            expand=True,  # Expand to fill tab space
        )

        # Create tabs
        control_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            on_change=self._on_tab_changed,
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

    def _check_daemon_running(self):
        """
        Check if camera daemon is running and responding

        Returns:
            bool: True if daemon is running and accepting connections, False otherwise
        """
        # Daemon is only used on macOS (RealSense requires sudo there)
        # On Windows/Linux, RealSense can be accessed directly
        if sys.platform != "darwin":
            print("[DEBUG] _check_daemon_running: Not macOS, daemon not needed")
            return False

        print(f"[DEBUG] _check_daemon_running: DAEMON_AVAILABLE={DAEMON_AVAILABLE}")
        if not DAEMON_AVAILABLE:
            print("[DEBUG] _check_daemon_running: Daemon components not available")
            return False

        import os
        import socket

        SOCKET_PATH = "/tmp/aaa_camera.sock"

        try:
            # Check if socket file exists
            print(
                f"[DEBUG] _check_daemon_running: Checking for socket at {SOCKET_PATH}..."
            )
            if not os.path.exists(SOCKET_PATH):
                print("[DEBUG] _check_daemon_running: Socket not found")
                return False

            # Socket file exists - verify daemon is actually responding
            print("[DEBUG] _check_daemon_running: Socket found, testing connection...")
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.settimeout(1.0)
            try:
                test_socket.connect(SOCKET_PATH)
                test_socket.close()
                print("[DEBUG] _check_daemon_running: Daemon is responding")
                return True
            except (ConnectionRefusedError, OSError) as e:
                print(f"[DEBUG] _check_daemon_running: Daemon not responding: {e}")
                return False
        except Exception as e:
            print(f"[DEBUG] _check_daemon_running: Error checking daemon - {e}")
            return False

    def _start_image_processor(self):
        """Initialize and start image processing"""
        print("[DEBUG MainWindow] Creating ImageProcessor...")

        # Check if daemon is running
        daemon_running = self._check_daemon_running()

        if daemon_running:
            print("[INFO] Camera daemon detected - using RealSense with depth")
            try:
                self.image_processor = DaemonImageProcessor(
                    display_width=app_config.display_width,
                    display_height=app_config.display_height,
                    callback=self._update_video_feed,
                )
                # RealSense detected - using auto-exposure (manual controls hidden)
                self.using_realsense = True
                # Exposure controls hidden - relying on RealSense auto-exposure

                # Uncomment below to enable manual exposure controls:
                # self.exposure_controls.visible = True
                # self.exposure_slider.visible = True
                # self.auto_exposure_btn.visible = True
            except (ConnectionRefusedError, FileNotFoundError, OSError) as e:
                # Daemon socket exists but daemon isn't responding - fall back to regular camera
                print(f"[WARN] Daemon connection failed: {e}")
                print("[INFO] Falling back to direct camera access (RGB only)")
                daemon_running = False

        if not daemon_running:
            print("[INFO] No daemon - using direct camera access (RGB only)")
            self.image_processor = ImageProcessor(
                display_width=app_config.display_width,
                display_height=app_config.display_height,
                callback=self._update_video_feed,  # Use callback for Flet
            )
        print("[DEBUG MainWindow] ImageProcessor created")

        # Set initial camera name for flip detection and trigger camera initialization
        # (only for regular ImageProcessor, not DaemonImageProcessor)
        is_daemon_processor = (
            isinstance(self.image_processor, DaemonImageProcessor)
            if DAEMON_AVAILABLE
            else False
        )

        if not is_daemon_processor and self.camera_manager.cameras:
            print(
                "[DEBUG MainWindow] Setting initial camera name for flip detection..."
            )
            # Use the dropdown value if set (handles auto-selection and default)
            selected_cam_index = None
            if self.camera_dropdown.value and self.camera_dropdown.value != "daemon":
                selected_cam_index = int(self.camera_dropdown.value)
            else:
                selected_cam_index = app_config.default_camera

            print(f"[DEBUG MainWindow] Selected camera index: {selected_cam_index}")
            for cam in self.camera_manager.cameras:
                if cam["camera_index"] == selected_cam_index:
                    print(f"[DEBUG MainWindow] Found camera: {cam['camera_name']}")
                    self.image_processor.current_camera_name = cam["camera_name"]
                    self.image_processor._update_flip_for_camera(cam["camera_name"])
                    # Trigger camera change to actually start the camera
                    self.image_processor.camera_changed(
                        selected_cam_index, cam["camera_name"]
                    )
                    print(
                        f"[DEBUG MainWindow] Triggered camera change for index {selected_cam_index}"
                    )
                    break

        # Update flip button appearance based on initial state
        print(
            f"[DEBUG MainWindow] Flip horizontal: {self.image_processor.flip_horizontal}"
        )
        if self.image_processor.flip_horizontal:
            self.flip_camera_btn.bgcolor = "#4CAF50"  # Green 500 when enabled
            self.flip_camera_btn.icon_color = "#FFFFFF"  # White icon
        else:
            self.flip_camera_btn.bgcolor = "#E0E0E0"  # Grey 300 when disabled
            self.flip_camera_btn.icon_color = "#424242"  # Grey 800

        # Start processing thread
        print("[DEBUG MainWindow] Starting ImageProcessor thread...")
        self.image_processor.start()
        print("[DEBUG MainWindow] ImageProcessor thread started")

        # Set initial detection mode to "camera" (Manual tab is default)
        # This saves CPU/GPU by not running detection until Auto tab is selected
        self.image_processor.set_detection_mode("camera")
        print("[DEBUG MainWindow] Set initial detection mode to 'camera' (Manual tab)")

        # Update status
        print("[DEBUG MainWindow] Updating status...")
        self._update_status()
        print("[DEBUG MainWindow] _start_image_processor complete")

    def _update_status(self):
        """Update status display"""
        # Determine RealSense status:
        # - "✓ With Depth" = using RealSense SDK (has depth data)
        # - "✓ RGB Only" = using RealSense via OpenCV (no depth data)
        # - "✗ Not detected" = no RealSense camera in use
        has_depth = self.image_processor.use_realsense
        if has_depth:
            realsense_status = "✓ With Depth"
        elif (
            hasattr(self.image_processor, "current_camera_name")
            and self.image_processor.current_camera_name
            and "RealSense" in self.image_processor.current_camera_name
        ):
            realsense_status = "✓ RGB Only"
        else:
            realsense_status = "✗ Not detected"

        # Show/hide depth toggle button based on depth availability
        self.depth_toggle_btn.visible = has_depth
        # Show calibration toggle only when depth is available and a calibration file is configured
        try:
            has_cal_file = bool(getattr(app_config, "camera_calibration_file", None))
            # If no explicit config file, check default calibration location
            if not has_cal_file and try_load_calibration is not None:
                try:
                    has_cal_file = try_load_calibration() is not None
                except Exception:
                    has_cal_file = False
        except Exception:
            has_cal_file = False
        self.calib_toggle_btn.visible = has_depth and has_cal_file

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
            "camera": "Camera Only",
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
                    # First frame after freezing - store raw frame and enhance labels
                    # Store the raw frame at freeze time for later re-highlighting
                    if hasattr(self.image_processor, "_last_rgb_frame"):
                        self.frozen_raw_frame = (
                            self.image_processor._last_rgb_frame.copy()
                        )

                    self.frozen_frame, self.frozen_detections = (
                        self._enhance_frozen_labels(img_array.copy())
                    )
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

    def _draw_text_pil(
        self,
        img,
        text,
        position,
        font_size=48,
        text_color=(0, 255, 0),
        bg_color=(0, 0, 0),
        border_color=None,
        border_width=2,
        padding=12,
        corner_radius=8,
    ):
        """
        Draw text using PIL for better font rendering with rounded corners

        Args:
            img: numpy array (RGB)
            text: text to draw
            position: (x, y) position for text center
            font_size: size of font
            text_color: RGB tuple for text
            bg_color: RGB tuple for background
            border_color: RGB tuple for border (None for no border)
            border_width: width of border
            padding: padding around text
            corner_radius: radius for rounded corners

        Returns:
            Modified image
        """
        # Convert to PIL Image
        pil_img = Image.fromarray(img)
        draw = ImageDraw.Draw(pil_img)

        # Try to use a system font, fallback to default
        try:
            # Try common modern fonts
            font = ImageFont.truetype(
                "/System/Library/Fonts/SFNS.ttf", font_size
            )  # macOS San Francisco
        except:
            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Helvetica.ttc", font_size
                )  # macOS Helvetica
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)  # Windows
                except:
                    font = ImageFont.load_default()  # Fallback

        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        bbox_top_offset = bbox[1]  # Distance from baseline to top of bbox

        x, y = position

        # Calculate background rectangle centered vertically on position
        total_width = text_width + 2 * padding
        total_height = text_height + 2 * padding

        bg_x1 = x - padding
        bg_y1 = y - total_height // 2
        bg_x2 = bg_x1 + total_width
        bg_y2 = bg_y1 + total_height

        # Draw borders if specified (layered approach)
        if border_color:
            # Draw white outer outline on EXPANDED rectangle (sits outside colored border)
            white_rim = 3  # Width of visible white rim
            draw.rounded_rectangle(
                [
                    bg_x1 - white_rim,
                    bg_y1 - white_rim,
                    bg_x2 + white_rim,
                    bg_y2 + white_rim,
                ],
                radius=corner_radius + white_rim,
                outline=(255, 255, 255),  # White outer outline
                width=white_rim,
            )

        # Draw rounded rectangle background
        draw.rounded_rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2], radius=corner_radius, fill=bg_color
        )

        # Draw colored border on top
        if border_color:
            draw.rounded_rectangle(
                [bg_x1, bg_y1, bg_x2, bg_y2],
                radius=corner_radius,
                outline=border_color,
                width=border_width,
            )

        # Draw text centered vertically in the box, accounting for bbox offset
        text_x = x
        text_y = bg_y1 + padding - bbox_top_offset
        draw.text((text_x, text_y), text, font=font, fill=text_color)

        # Convert back to numpy array
        return np.array(pil_img)

    def _calculate_label_positions(
        self, centers, classes, img_shape, font_size=42, padding=12
    ):
        """
        Calculate non-overlapping label positions using force-directed algorithm (ggrepel-style)

        Args:
            centers: List of (x, y) tuples for object centers
            classes: List of class names
            img_shape: Image shape (height, width, channels)
            font_size: Font size for labels
            padding: Padding around labels

        Returns:
            List of (x, y) tuples for label positions
        """
        if not centers:
            return []

        img_height, img_width = img_shape[:2]

        # Estimate label dimensions (rough approximation)
        # PIL font rendering will vary, but this is good enough for collision detection
        char_width = font_size * 0.6
        char_height = font_size * 1.2

        labels_info = []
        for cx, cy, class_name in zip(
            [c[0] for c in centers], [c[1] for c in centers], classes
        ):
            # Estimate label size
            label_text = f"#{len(labels_info) + 1}: {class_name}"
            label_w = int(len(label_text) * char_width + padding * 2)
            label_h = int(char_height + padding * 2)

            # Initial position (centered above object)
            label_x = cx - label_w // 2
            label_y = cy - 30

            labels_info.append(
                {
                    "cx": cx,
                    "cy": cy,
                    "x": float(label_x),
                    "y": float(label_y),
                    "w": label_w,
                    "h": label_h,
                }
            )

        # Apply force-directed layout
        iterations = 50
        for iteration in range(iterations):
            forces = [{"x": 0.0, "y": 0.0} for _ in labels_info]

            # Repulsion between overlapping labels
            for i, label1 in enumerate(labels_info):
                for j in range(i + 1, len(labels_info)):
                    label2 = labels_info[j]

                    # Check overlap with padding
                    pad = 10
                    l1_x1, l1_y1 = label1["x"] - pad, label1["y"] - pad
                    l1_x2, l1_y2 = (
                        label1["x"] + label1["w"] + pad,
                        label1["y"] + label1["h"] + pad,
                    )
                    l2_x1, l2_y1 = label2["x"] - pad, label2["y"] - pad
                    l2_x2, l2_y2 = (
                        label2["x"] + label2["w"] + pad,
                        label2["y"] + label2["h"] + pad,
                    )

                    overlap = not (
                        l1_x2 < l2_x1 or l2_x2 < l1_x1 or l1_y2 < l2_y1 or l2_y2 < l1_y1
                    )

                    if overlap:
                        # Calculate centers
                        l1_cx = label1["x"] + label1["w"] / 2
                        l1_cy = label1["y"] + label1["h"] / 2
                        l2_cx = label2["x"] + label2["w"] / 2
                        l2_cy = label2["y"] + label2["h"] / 2

                        dx = l2_cx - l1_cx
                        dy = l2_cy - l1_cy
                        dist = np.sqrt(dx**2 + dy**2)

                        if dist < 1:
                            dx, dy = 20, 10
                            dist = np.sqrt(dx**2 + dy**2)

                        # Strong repulsion
                        repulsion = 15.0
                        fx = (dx / dist) * repulsion
                        fy = (dy / dist) * repulsion

                        forces[i]["x"] -= fx
                        forces[i]["y"] -= fy
                        forces[j]["x"] += fx
                        forces[j]["y"] += fy

            # Spring force toward anchor
            spring = 0.15
            for i, label in enumerate(labels_info):
                desired_x = label["cx"] - label["w"] // 2
                desired_y = label["cy"] - 30
                forces[i]["x"] += (desired_x - label["x"]) * spring
                forces[i]["y"] += (desired_y - label["y"]) * spring

            # Apply forces with damping
            damping = 0.8
            for i, label in enumerate(labels_info):
                label["x"] += forces[i]["x"] * damping
                label["y"] += forces[i]["y"] * damping

                # Keep in bounds
                label["x"] = max(10, min(label["x"], img_width - label["w"] - 10))
                label["y"] = max(10, min(label["y"], img_height - label["h"] - 10))

        # Return positions as (x, y) tuples (center of label area)
        return [
            (int(l["x"] + l["w"] // 2), int(l["y"] + l["h"] // 2)) for l in labels_info
        ]

    def _enhance_frozen_labels(self, img_array):
        """
        Enhance object labels for frozen frame with larger numbered labels

        Args:
            img_array: Numpy array (RGB format) with existing detections (will be re-processed)

        Returns:
            Tuple of (image with enhanced labels, detection data dict)
        """
        if not self.image_processor or self.image_processor.detection_mode != "objects":
            return img_array, None

        # Get detection manager
        detection_mgr = self.image_processor.detection_manager
        if not detection_mgr.segmentation_model:
            return img_array, None

        # Get the clean raw frame to detect on
        if hasattr(self.image_processor, "_last_rgb_frame"):
            clean_img = self.image_processor._last_rgb_frame.copy()
        else:
            # Fallback: use current image (will have old labels)
            clean_img = img_array.copy()

        # Detect on clean image - this is the ONLY detection we do
        (boxes, classes, contours, centers) = (
            detection_mgr.segmentation_model.detect_objects_mask(clean_img)
        )

        # Store detection data for button creation
        detections = {
            "classes": classes,
            "centers": centers,
            "boxes": boxes,
            "contours": contours,
        }

        # Draw masks and get the colors used for each object
        # Only draw mask for selected object if one is selected
        selected_indices = (
            [self.selected_object] if self.selected_object is not None else None
        )
        img_with_masks, mask_colors = detection_mgr.segmentation_model.draw_object_mask(
            clean_img,
            boxes,
            classes,
            contours,
            return_colors=True,
            selected_indices=selected_indices,
        )

        # Calculate label positions with overlap avoidance (ggrepel-style)
        label_positions = self._calculate_label_positions(
            centers, classes, img_with_masks.shape
        )

        # Now draw our enhanced numbered labels with PIL for professional font rendering
        # Only draw labels for selected object if one is selected
        for i, (center, class_name, label_pos, mask_color) in enumerate(
            zip(centers, classes, label_positions, mask_colors), start=1
        ):
            # Skip this label if an object is selected and this isn't it
            if self.selected_object is not None and (i - 1) != self.selected_object:
                continue

            x, y = center
            label_x, label_y = label_pos
            label = f"#{i}: {class_name}"

            # Convert BGR to RGB for consistency
            border_color_rgb = (mask_color[2], mask_color[1], mask_color[0])

            # Draw connector line if label moved significantly (using mask color)
            distance = np.sqrt((label_x - x) ** 2 + (label_y - y) ** 2)
            if distance > 30:
                cv2.line(
                    img_with_masks,
                    (x, y),
                    (label_x, label_y),
                    mask_color,
                    2,
                    cv2.LINE_AA,
                )

            # Draw using PIL for much better font rendering
            img_with_masks = self._draw_text_pil(
                img_with_masks,
                label,
                (label_x, label_y),
                font_size=42,
                text_color=(70, 70, 70),  # Dark gray text
                bg_color=(255, 255, 255),  # White background
                border_color=border_color_rgb,  # Match segmentation contour color
                border_width=5,  # Thick border for visibility
                padding=12,
            )

        return img_with_masks, detections

    def _create_object_buttons(self):
        """Create clickable buttons for each detected object"""
        if not self.frozen_detections:
            return

        # Clear existing buttons
        self.object_buttons_row.controls.clear()

        # Create a button for each detected object
        classes = self.frozen_detections["classes"]
        for i, class_name in enumerate(classes, start=1):
            btn = ft.ElevatedButton(
                text=f"#{i}: {class_name}",
                on_click=lambda e, idx=i - 1: self._on_object_selected(idx),
                bgcolor=ft.Colors.BLUE_GREY_800,
                color=ft.Colors.WHITE,
            )
            self.object_buttons_row.controls.append(btn)

        # Show the button row
        self.object_buttons_row.visible = True
        self.page.update()

    def _on_object_selected(self, object_index: int):
        """Handle object button click - toggle selection if already selected"""
        classes = self.frozen_detections["classes"]
        class_name = classes[object_index]

        # Toggle selection if clicking the same object
        if self.selected_object == object_index:
            self.selected_object = None
            self.object_analysis = None
            self._analysis_in_progress = False
            print(f"Deselected object #{object_index + 1}: {class_name}")
        else:
            self.selected_object = object_index
            self.object_analysis = None
            print(f"Selected object #{object_index + 1}: {class_name}")

        # Highlight the selected button
        for i, btn in enumerate(self.object_buttons_row.controls):
            if i == self.selected_object:
                btn.bgcolor = ft.Colors.GREEN_700
            else:
                btn.bgcolor = ft.Colors.BLUE_GREY_800

        # Enable or disable the Show Points button depending on selection and depth availability
        try:
            if self.show_points_btn is not None:
                self.show_points_btn.disabled = (
                    self.selected_object is None or self.frozen_depth_frame is None
                )
        except Exception:
            pass

        # Redraw frozen frame with highlighted label
        self._update_frozen_frame_highlight()

        self.page.update()

        # Auto-trigger analysis if an object is selected and depth is available
        if (
            self.selected_object is not None
            and self.frozen_depth_frame is not None
            and not self._analysis_in_progress
        ):
            # Show "Analyzing..." state on button immediately
            try:
                btn = self.object_buttons_row.controls[self.selected_object]
                btn.bgcolor = "#FF8F00"  # Amber 800
                btn.text = f"Analyzing..."
                self.page.update()
            except Exception:
                pass
            # Spawn background analysis thread
            self._analysis_in_progress = True
            threading.Thread(
                target=self._analyze_selected_object,
                args=(object_index,),
                daemon=True,
            ).start()

    def _analyze_selected_object(self, object_index: int):
        """Run 3D object analysis in background thread."""
        try:
            from aaa_vision.object_analyzer import ObjectAnalyzer
            from aaa_vision.point_cloud import PointCloudProcessor

            classes = self.frozen_detections["classes"]
            class_name = classes[object_index]
            contours = self.frozen_detections.get("contours", [])

            if object_index >= len(contours):
                raise ValueError("No contour data for selected object")

            depth = self.frozen_depth_frame
            aligned_color = self.frozen_aligned_color
            if depth is None:
                raise ValueError("No depth frame available")

            processor = PointCloudProcessor()

            # Build binary mask from contour (in RGB space 1920x1080, scale to 848x480)
            contour = contours[object_index]
            h_depth, w_depth = depth.shape[:2]
            mask_rgb = np.zeros((1080, 1920), dtype=np.uint8)
            cv2.drawContours(
                mask_rgb,
                [np.array(contour, dtype=np.int32)],
                -1,
                255,
                thickness=cv2.FILLED,
            )
            mask_depth = cv2.resize(
                mask_rgb, (w_depth, h_depth), interpolation=cv2.INTER_NEAREST
            )

            # Create object point cloud using aligned pair
            object_pcd = processor.extract_object(depth, mask_depth, aligned_color)

            # If calibration is available, transform object cloud to color frame
            if getattr(processor, "calibration", None) is not None:
                object_pcd = processor.apply_calibration(object_pcd)

            # Create scene point cloud
            scene_pcd = processor.create_from_depth(depth, aligned_color)

            # If calibration is available, transform scene cloud to color frame before preprocessing
            if getattr(processor, "calibration", None) is not None:
                scene_pcd = processor.apply_calibration(scene_pcd)

            scene_pcd = processor.preprocess(scene_pcd)

            # Run analysis
            analyzer = ObjectAnalyzer(processor)
            analysis = analyzer.analyze(object_pcd, scene_pcd)

            # Store result (only if same object is still selected)
            if self.selected_object == object_index:
                self.object_analysis = analysis
                self._analysis_in_progress = False

                print(
                    f"Analysis complete: {class_name} -> {analysis.shape.shape_type} "
                    f"(conf={analysis.shape.confidence:.2f}, "
                    f"width={analysis.grasp_width * 1000:.1f}mm, "
                    f"graspable={analysis.graspable}, "
                    f"confidence={analysis.grasp_confidence})"
                )

                # Update button text
                try:
                    btn = self.object_buttons_row.controls[object_index]
                    btn.text = f"{class_name} \u2713"
                    btn.bgcolor = ft.Colors.GREEN_700
                    self._update_frozen_frame_highlight()
                    self.page.update()
                except Exception:
                    pass

        except Exception as e:
            self._analysis_in_progress = False
            print(f"Object analysis failed: {e}")
            import traceback

            traceback.print_exc()

            # Update button to show failure
            if self.selected_object == object_index:
                self.object_analysis = None
                try:
                    classes = self.frozen_detections["classes"]
                    btn = self.object_buttons_row.controls[object_index]
                    btn.text = f"{classes[object_index]} (analysis failed)"
                    btn.bgcolor = ft.Colors.GREEN_700
                    self.page.update()
                except Exception:
                    pass

    def _project_to_pixel(self, point_3d: np.ndarray) -> tuple:
        """
        Project a 3D point in camera coordinates to 2D pixel in RGB frame.

        Returns (pixel_x, pixel_y) in 1920x1080 RGB coordinates.
        """
        # Try to get RealSense depth intrinsics
        intr = None
        try:
            import pyrealsense2 as rs

            if (
                hasattr(self.image_processor, "rs_camera")
                and self.image_processor.rs_camera
            ):
                profile = self.image_processor.rs_camera.profile
                depth_stream = profile.get_stream(
                    rs.stream.depth
                ).as_video_stream_profile()
                intr = depth_stream.get_intrinsics()
        except Exception:
            pass

        if intr is not None:
            import pyrealsense2 as rs

            pixel = rs.rs2_project_point_to_pixel(
                intr, [float(point_3d[0]), float(point_3d[1]), float(point_3d[2])]
            )
            px_depth, py_depth = int(pixel[0]), int(pixel[1])
        else:
            # Fallback: default D435 intrinsics at 848x480
            fx, fy = 425.19, 425.19
            cx, cy = 423.86, 239.87
            if point_3d[2] != 0:
                px_depth = int(point_3d[0] * fx / point_3d[2] + cx)
                py_depth = int(point_3d[1] * fy / point_3d[2] + cy)
            else:
                px_depth, py_depth = int(cx), int(cy)

        # Scale from depth (848x480) to display (1920x1080)
        px_rgb = int(px_depth * 1920 / 848)
        py_rgb = int(py_depth * 1080 / 480)

        return px_rgb, py_rgb

    def _draw_gripper_icon(self, img: np.ndarray, analysis) -> np.ndarray:
        """Draw gripper overlay at projected grasp point on the image."""
        px, py = self._project_to_pixel(analysis.grasp_point)

        # Clamp to image bounds
        h, w = img.shape[:2]
        px = max(0, min(px, w - 1))
        py = max(0, min(py, h - 1))

        # Color based on graspability and confidence
        if not analysis.graspable:
            color = (0, 0, 255)  # Red (BGR)
            label = (
                "Too large for gripper"
                if analysis.grasp_width > 0.066
                else "Too small to grasp"
            )
        elif analysis.grasp_confidence >= 0.7:
            color = (0, 220, 0)  # Green
            label = f"Ready to grasp ({analysis.grasp_confidence:.0%})"
        elif analysis.grasp_confidence >= 0.4:
            color = (0, 220, 220)  # Yellow (BGR)
            label = f"Grasp possible ({analysis.grasp_confidence:.0%})"
        else:
            color = (0, 140, 255)  # Orange (BGR)
            label = f"Uncertain grasp ({analysis.grasp_confidence:.0%})"

        # Draw gripper fingers (two parallel rectangles)
        finger_len = 30  # pixels
        finger_width = 8
        gap = 20  # half-gap between fingers

        # White outer border (3px) + colored inner fill (2px)
        # Left finger
        cv2.rectangle(
            img,
            (px - gap - finger_width, py - finger_len),
            (px - gap, py + finger_len),
            (255, 255, 255),
            3,
        )
        cv2.rectangle(
            img,
            (px - gap - finger_width, py - finger_len),
            (px - gap, py + finger_len),
            color,
            2,
        )
        # Right finger
        cv2.rectangle(
            img,
            (px + gap, py - finger_len),
            (px + gap + finger_width, py + finger_len),
            (255, 255, 255),
            3,
        )
        cv2.rectangle(
            img,
            (px + gap, py - finger_len),
            (px + gap + finger_width, py + finger_len),
            color,
            2,
        )

        # Center crosshair
        cv2.circle(img, (px, py), 5, (255, 255, 255), 3)
        cv2.circle(img, (px, py), 5, color, 2)

        # X overlay for non-graspable
        if not analysis.graspable:
            cv2.line(img, (px - 25, py - 25), (px + 25, py + 25), (0, 0, 255), 3)
            cv2.line(img, (px - 25, py + 25), (px + 25, py - 25), (0, 0, 255), 3)

        # Label text (min 24px at 1080p)
        font_scale = 0.9
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        label_x = px - text_w // 2
        label_y = py + finger_len + 30 + text_h

        # Clamp label position
        label_x = max(5, min(label_x, w - text_w - 5))
        label_y = max(text_h + 5, min(label_y, h - 5))

        # Background rectangle for text
        cv2.rectangle(
            img,
            (label_x - 4, label_y - text_h - 4),
            (label_x + text_w + 4, label_y + baseline + 4),
            (0, 0, 0),
            -1,
        )
        cv2.rectangle(
            img,
            (label_x - 4, label_y - text_h - 4),
            (label_x + text_w + 4, label_y + baseline + 4),
            (255, 255, 255),
            1,
        )
        cv2.putText(
            img,
            label,
            (label_x, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

        return img

    def _update_frozen_frame_highlight(self):
        """Redraw frozen frame with selected object highlighted"""
        if not self.frozen_detections:
            return

        # Get detection manager
        detection_mgr = self.image_processor.detection_manager
        if not detection_mgr.segmentation_model:
            return

        # Use the stored frozen raw frame, not the current one
        if self.frozen_raw_frame is None:
            return

        clean_img = self.frozen_raw_frame.copy()
        boxes = self.frozen_detections["boxes"]
        classes = self.frozen_detections["classes"]
        contours = self.frozen_detections["contours"]
        centers = self.frozen_detections["centers"]

        # Draw masks and get colors
        # Only draw mask for selected object if one is selected
        selected_indices = (
            [self.selected_object] if self.selected_object is not None else None
        )
        img_with_masks, mask_colors = detection_mgr.segmentation_model.draw_object_mask(
            clean_img,
            boxes,
            classes,
            contours,
            return_colors=True,
            selected_indices=selected_indices,
        )

        # Calculate label positions with overlap avoidance
        label_positions = self._calculate_label_positions(
            centers, classes, img_with_masks.shape
        )

        # Draw numbered labels with highlighting for selected object using PIL
        # Only draw labels for selected object if one is selected
        for i, (center, class_name, label_pos, mask_color) in enumerate(
            zip(centers, classes, label_positions, mask_colors), start=1
        ):
            # Skip this label if an object is selected and this isn't it
            if self.selected_object is not None and (i - 1) != self.selected_object:
                continue

            x, y = center
            label_x, label_y = label_pos
            label = f"#{i}: {class_name}"
            is_selected = (i - 1) == self.selected_object

            # Convert BGR to RGB
            mask_color_rgb = (mask_color[2], mask_color[1], mask_color[0])

            # Draw connector line if label moved significantly
            distance = np.sqrt((label_x - x) ** 2 + (label_y - y) ** 2)
            if distance > 30:
                cv2.line(
                    img_with_masks,
                    (x, y),
                    (label_x, label_y),
                    mask_color,
                    2,
                    cv2.LINE_AA,
                )

            # Set colors based on selection
            if is_selected:
                text_color = (255, 255, 255)  # White text
                bg_color = (100, 149, 237)  # Blue background (Cornflower blue)
                border_color = (25, 25, 112)  # Dark blue border (Midnight blue)
            else:
                text_color = (70, 70, 70)  # Dark gray text
                bg_color = (255, 255, 255)  # White background
                border_color = mask_color_rgb  # Match segmentation contour color

            # Draw using PIL for professional font rendering
            img_with_masks = self._draw_text_pil(
                img_with_masks,
                label,
                (label_x, label_y),
                font_size=42,
                text_color=text_color,
                bg_color=bg_color,
                border_color=border_color,
                border_width=5,  # Thick border for visibility
                padding=12,
            )

        # If depth visualization is active and we have a frozen depth frame, show overlay on depth image
        is_depth_view = (
            getattr(self.image_processor, "show_depth_visualization", False)
            if getattr(self, "image_processor", None)
            else False
        )
        if is_depth_view and getattr(self, "frozen_depth_frame", None) is not None:
            try:
                depth_img = self.image_processor._colorize_depth(
                    self.frozen_depth_frame, self.frozen_raw_frame.shape
                )
                # Draw overlay points (green) and optionally highlight selected object's center
                overlay_img = depth_img.copy()
                if getattr(self, "_overlay_points", None):
                    for x, y, z in self._overlay_points:
                        try:
                            cv2.circle(
                                overlay_img, (int(x), int(y)), 3, (0, 255, 0), -1
                            )
                        except Exception:
                            pass
                # Draw selected object center for reference
                if (
                    self.selected_object is not None
                    and len(centers) > self.selected_object
                ):
                    try:
                        cx, cy = centers[self.selected_object]
                        cv2.circle(
                            overlay_img, (int(cx), int(cy)), 8, (255, 255, 255), 2
                        )
                    except Exception:
                        pass
                self.frozen_frame = overlay_img
            except Exception:
                # Fallback to regular RGB overlay if something fails
                overlay_img = img_with_masks.copy()
                if getattr(self, "_overlay_points", None):
                    for x, y, z in self._overlay_points:
                        try:
                            cv2.circle(
                                overlay_img, (int(x), int(y)), 3, (0, 255, 0), -1
                            )
                        except Exception:
                            pass
                self.frozen_frame = overlay_img
        else:
            # If overlay points are present, draw them on the image for visual verification
            if getattr(self, "_overlay_points", None):
                overlay_img = img_with_masks.copy()
                for x, y, z in self._overlay_points:
                    # Draw small circle at (x, y) in BGR (green)
                    try:
                        cv2.circle(overlay_img, (int(x), int(y)), 3, (0, 255, 0), -1)
                    except Exception:
                        pass
                # Draw gripper overlay if analysis is available
                if getattr(self, "object_analysis", None) is not None:
                    try:
                        overlay_img = self._draw_gripper_icon(
                            overlay_img, self.object_analysis
                        )
                    except Exception as e:
                        logger.debug(f"Gripper overlay failed: {e}")
                self.frozen_frame = overlay_img
            else:
                # Update frozen frame
                final_img = img_with_masks
                # Draw gripper overlay if analysis is available
                if getattr(self, "object_analysis", None) is not None:
                    try:
                        final_img = self._draw_gripper_icon(
                            img_with_masks.copy(), self.object_analysis
                        )
                    except Exception as e:
                        logger.debug(f"Gripper overlay failed: {e}")
                self.frozen_frame = final_img

    def get_object_depth_points(
        self, object_index: int, subsample: int = 4, to_meters: bool = False
    ):
        """Return list of (x, y, depth_mm) or (X, Y, Z) if to_meters and RealSense available for selected frozen object."""
        import cv2
        import numpy as np

        if not getattr(self, "frozen_detections", None):
            return []

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return []

        contour = contours[object_index]

        rgb = getattr(self, "frozen_raw_frame", None)
        depth = getattr(self, "frozen_depth_frame", None)
        if rgb is None or depth is None:
            print("No frozen RGB or depth frame available for point extraction")
            return []

        h_rgb, w_rgb = rgb.shape[:2]
        h_depth, w_depth = depth.shape[:2]

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return []

        xs = xs[::subsample]
        ys = ys[::subsample]

        scale_x = w_depth / w_rgb
        scale_y = h_depth / h_rgb
        xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
        ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)

        depths = depth[ys_d, xs_d]

        points = []
        use_realsense = getattr(
            self.image_processor, "use_realsense", False
        ) and getattr(self.image_processor, "rs_camera", None)
        intr = None
        rs_mod = None
        if to_meters and use_realsense:
            try:
                import pyrealsense2 as rs_mod

                profile = self.image_processor.rs_camera.profile
                depth_stream = profile.get_stream(
                    rs_mod.stream.depth
                ).as_video_stream_profile()
                intr = depth_stream.get_intrinsics()
            except Exception as e:
                intr = None
                print(f"Failed to get RealSense intrinsics: {e}")

        for u_d, v_d, z in zip(xs_d, ys_d, depths):
            if z == 0:
                continue
            if to_meters and use_realsense and intr is not None:
                try:
                    pt = rs_mod.rs2_deproject_pixel_to_point(
                        intr, [int(u_d), int(v_d)], float(z) / 1000.0
                    )
                    points.append((float(pt[0]), float(pt[1]), float(pt[2])))
                except Exception:
                    points.append((int(u_d), int(v_d), int(z)))
            else:
                points.append((int(u_d), int(v_d), int(z)))

        return points

    def _extract_object_colors(
        self, object_index: int, subsample: int = 4,
        aligned_color: "np.ndarray | None" = None,
        depth: "np.ndarray | None" = None,
    ) -> "np.ndarray | None":
        """Extract RGB colors from aligned color frame for object mask pixels.

        Returns Nx3 uint8 array matching the points from get_object_depth_points,
        or None if color data is unavailable.
        """
        import cv2
        import numpy as np

        if aligned_color is None or depth is None:
            return None

        if not getattr(self, "frozen_detections", None):
            return None

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return None

        contour = contours[object_index]
        rgb = getattr(self, "frozen_raw_frame", None)
        if rgb is None:
            return None

        h_rgb, w_rgb = rgb.shape[:2]
        h_depth, w_depth = depth.shape[:2]

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return None

        xs = xs[::subsample]
        ys = ys[::subsample]

        scale_x = w_depth / w_rgb
        scale_y = h_depth / h_rgb
        xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
        ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)

        depths = depth[ys_d, xs_d]
        valid = depths > 0

        # Aligned color is BGR (from RealSense), convert to RGB
        colors_bgr = aligned_color[ys_d[valid], xs_d[valid]]
        colors_rgb = colors_bgr[:, ::-1].copy()

        return colors_rgb

    def get_object_mask_pixels(self, object_index: int, subsample: int = 8):
        """Return list of (x, y, depth_mm or 0 if unavailable) in RGB image coordinates for the object mask."""
        import cv2
        import numpy as np

        if not getattr(self, "frozen_detections", None):
            return []

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return []

        contour = contours[object_index]
        rgb = getattr(self, "frozen_raw_frame", None)
        depth = getattr(self, "frozen_depth_frame", None)
        if rgb is None:
            return []

        h_rgb, w_rgb = rgb.shape[:2]
        h_depth = depth.shape[0] if depth is not None else None
        w_depth = depth.shape[1] if depth is not None else None

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return []

        xs = xs[::subsample]
        ys = ys[::subsample]

        points = []
        if depth is not None:
            # Map to depth coords
            scale_x = w_depth / w_rgb
            scale_y = h_depth / h_rgb
            xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
            ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)
            depths = depth[ys_d, xs_d]
            for x, y, z in zip(xs, ys, depths):
                points.append((int(x), int(y), int(z)))
        else:
            for x, y in zip(xs, ys):
                points.append((int(x), int(y), 0))

        return points

    def _clear_object_buttons(self):
        """Clear object selection buttons when unfreezing"""
        self.object_buttons_row.controls.clear()
        self.object_buttons_row.visible = False
        self.selected_object = None
        self.frozen_raw_frame = None
        # Disable Show Points button when no objects are present
        try:
            if self.show_points_btn is not None:
                self.show_points_btn.disabled = True
        except Exception:
            pass
        self.page.update()

    def _on_camera_changed(self, e):
        """Handle camera selection change"""
        if not e.control.value:
            return

        selected_value = e.control.value

        # Check if switching to daemon or regular camera
        if selected_value == "daemon":
            print("Switching to RealSense daemon...")
            self._switch_to_daemon()
        else:
            camera_index = int(selected_value)
            print(f"Switching to camera {camera_index}")

            # Get camera name from camera manager
            camera_name = None
            for cam in self.camera_manager.cameras:
                if cam["camera_index"] == camera_index:
                    camera_name = cam["camera_name"]
                    break

            # Check if currently using daemon - need to switch processor type
            is_using_daemon = (
                isinstance(self.image_processor, DaemonImageProcessor)
                if DAEMON_AVAILABLE
                else False
            )

            if is_using_daemon:
                # Switch from daemon to regular ImageProcessor
                self._switch_to_regular_camera(camera_index, camera_name)
            elif self.image_processor:
                # Already using regular processor, just change camera
                self.image_processor.camera_changed(camera_index, camera_name)
                self._update_status()
                if self.video_frozen:
                    self._unfreeze_video()

    def _switch_to_daemon(self):
        """Switch from regular camera to daemon (RealSense with depth)"""
        if not DAEMON_AVAILABLE:
            print("[ERROR] Daemon components not available")
            return

        # Stop current image processor
        if self.image_processor:
            self.image_processor.stop()

        # Create new DaemonImageProcessor
        self.image_processor = DaemonImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
            callback=self._update_video_feed,
        )
        self.image_processor.start()
        self.using_realsense = True

        # Set detection mode to camera only (Manual tab default)
        self.image_processor.set_detection_mode("camera")

        # Update status
        self._update_status()
        if self.video_frozen:
            self._unfreeze_video()
        print("Switched to RealSense daemon (with depth)")

    def _switch_to_regular_camera(self, camera_index: int, camera_name: str):
        """Switch from daemon to regular camera"""
        # Stop current image processor
        if self.image_processor:
            self.image_processor.stop()

        # Create new ImageProcessor
        self.image_processor = ImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
            callback=self._update_video_feed,
        )

        # Set camera before starting
        self.image_processor.current_camera_name = camera_name
        self.image_processor._update_flip_for_camera(camera_name)
        self.image_processor.camera_changed(camera_index, camera_name)

        # Start processor
        self.image_processor.start()

        # Set detection mode to camera only (Manual tab default)
        self.image_processor.set_detection_mode("camera")

        # Update status
        self._update_status()
        if self.video_frozen:
            self._unfreeze_video()
        print(f"Switched to regular camera: {camera_name}")

    def _on_refresh_camera(self):
        """Handle refresh camera button - capture new frame"""
        if self.video_frozen:
            self._unfreeze_video()
        print("Camera view refreshed")

    def _unfreeze_video(self):
        """Unfreeze video to show live camera feed"""
        self.video_frozen = False
        self.frozen_frame = None
        self.frozen_raw_frame = None
        self.frozen_detections = None
        self.frozen_depth_frame = None
        self.frozen_aligned_color = None
        self._clear_object_buttons()
        print("Video unfrozen - showing live camera feed")

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

    def _on_arm_connection_status(self, connected: bool, message: str):
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
                self.arm_status_text.value = f"Arm: ✓ Connected ({app_config.lite6_ip})"
                self.arm_status_text.color = "#2E7D32"  # Green 800
            else:
                self.arm_status_text.value = f"Arm: ✗ {message}"
                self.arm_status_text.color = "#C62828"  # Red 800
            # Update connect button state as well
            try:
                self._set_connect_button_state(connected, connecting=False)
            except Exception:
                pass
            self.page.update()

    def _on_arm_error(self, error_message: str):
        """Handle arm errors"""
        print(f"Arm error: {error_message}")
        if self.arm_status_text:
            self.arm_status_text.value = f"Arm Error: {error_message}"
            self.arm_status_text.color = "#C62828"  # Red 800
            self.page.update()

    def _set_connect_button_state(self, connected: bool, connecting: bool = False):
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

    def _on_connect_arm(self, e):
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

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        if self.image_processor:
            self.image_processor.toggle_detection_mode()
            self._update_status()

    def _toggle_detection_logging(self):
        """Toggle detection logging for stability analysis (Press 'L')"""
        if self.image_processor:
            self.image_processor.toggle_detection_logging()

    def _on_flip_camera(self):
        """Toggle horizontal flip for camera"""
        if self.image_processor:
            self.image_processor.toggle_flip()
            # Update button appearance to show flip state
            if self.image_processor.flip_horizontal:
                self.flip_camera_btn.bgcolor = "#4CAF50"  # Green 500 when enabled
                self.flip_camera_btn.icon_color = "#FFFFFF"  # White icon
            else:
                self.flip_camera_btn.bgcolor = "#E0E0E0"  # Grey 300 when disabled
                self.flip_camera_btn.icon_color = "#424242"  # Grey 800
            self.page.update()

    def _on_toggle_depth_view(self):
        """Toggle between RGB and depth visualization"""
        if self.image_processor:
            is_depth = self.image_processor.toggle_depth_visualization()
            # Update button appearance to show current view mode
            if is_depth:
                self.depth_toggle_btn.bgcolor = "#2196F3"  # Blue 500 when showing depth
                self.depth_toggle_btn.icon_color = "#FFFFFF"  # White icon
                self.depth_toggle_btn.tooltip = "Showing Depth view (click for RGB)"
            else:
                self.depth_toggle_btn.bgcolor = "#E0E0E0"  # Grey 300 when showing RGB
                self.depth_toggle_btn.icon_color = "#424242"  # Grey 800
                self.depth_toggle_btn.tooltip = "Showing RGB view (click for Depth)"
            self.page.update()

    def _on_toggle_apply_calibration(self):
        """Toggle applying the depth->color calibration at runtime"""
        # Flip state
        self.apply_calibration_enabled = not getattr(
            self, "apply_calibration_enabled", False
        )

        # Update button appearance
        if self.apply_calibration_enabled:
            self.calib_toggle_btn.bgcolor = "#2196F3"
            self.calib_toggle_btn.icon_color = "#FFFFFF"
            self.calib_toggle_btn.tooltip = "Calibration enabled (click to disable)"
        else:
            self.calib_toggle_btn.bgcolor = "#E0E0E0"
            self.calib_toggle_btn.icon_color = "#424242"
            self.calib_toggle_btn.tooltip = "Calibration disabled (click to enable)"

        # Propagate to image processor if it supports runtime toggling
        try:
            if getattr(self, "image_processor", None):
                if hasattr(self.image_processor, "set_apply_calibration"):
                    self.image_processor.set_apply_calibration(self.apply_calibration_enabled)
                else:
                    setattr(self.image_processor, "apply_calibration_enabled", self.apply_calibration_enabled)
        except Exception:
            pass

        # Persist flag in app_config and user config file
        try:
            app_config.camera_calibration_enabled = bool(self.apply_calibration_enabled)
            # Save to config.yaml so the preference persists across runs
            try:
                from aaa_core.config.settings import save_camera_config

                save_camera_config(enabled=self.apply_calibration_enabled)
            except Exception:
                pass
        except Exception:
            pass

        if getattr(self, "_ui_built", False):
            self.page.update()

    def _on_exposure_change(self, e):
        """Handle RealSense exposure slider change"""
        if not self.using_realsense or not self.image_processor:
            return

        exposure_value = int(e.control.value)
        self.exposure_value_text.value = f"Exposure: {exposure_value}"

        # Update RealSense camera exposure
        if self.image_processor.set_realsense_exposure(exposure_value):
            print(f"✓ RealSense exposure set to {exposure_value}")

        self.page.update()

    def _auto_adjust_exposure(self):
        """Run auto-exposure adjustment once"""
        if not self.using_realsense or not self.image_processor:
            return

        # Run once
        self._run_auto_exposure_once()

    def _run_auto_exposure_once(self):
        """Run auto-exposure adjustment once without enabling continuous mode"""
        if not self.using_realsense or not self.image_processor:
            return

        try:
            # Get current frame brightness
            if hasattr(self.image_processor, "get_recent_brightness"):
                avg_brightness = self.image_processor.get_recent_brightness()
            else:
                return

            # Calculate optimal exposure
            current_exposure = int(self.exposure_slider.value)
            # Target: 90 (lower than 128) for better noise/clarity tradeoff
            # Segmentation models prioritize clean edges over brightness
            target_brightness = 90
            brightness_ratio = target_brightness / max(avg_brightness, 1)
            new_exposure = int(current_exposure * brightness_ratio)

            # Clamp with max 2500 to avoid excessive noise (high exposure = worse segmentation)
            new_exposure = max(100, min(2500, new_exposure))

            print(
                f"Startup auto-exposure: brightness={avg_brightness:.1f}, {current_exposure} → {new_exposure}"
            )

            # Update slider and camera
            self.exposure_slider.value = new_exposure
            self.exposure_value_text.value = f"Exposure: {new_exposure}"

            if self.image_processor.set_realsense_exposure(new_exposure):
                print(f"✓ Exposure set to {new_exposure}")
                print(
                    f"   (Wait ~2 seconds for camera to adjust and buffer to refill before clicking auto-exposure again)"
                )

            self.page.update()

        except Exception as e:
            print(f"Startup auto-exposure failed: {e}")

    def _continuous_auto_exposure(self):
        """Continuously adjust exposure until disabled"""
        while self.auto_exposure_enabled:
            try:
                # Get current frame brightness
                if hasattr(self.image_processor, "get_recent_brightness"):
                    avg_brightness = self.image_processor.get_recent_brightness()
                else:
                    # Fallback: analyze current displayed frame
                    if self.video_feed.src_base64:
                        import base64
                        from io import BytesIO

                        import numpy as np
                        from PIL import Image

                        img_data = base64.b64decode(
                            self.video_feed.src_base64.split(",")[1]
                        )
                        img = Image.open(BytesIO(img_data))
                        img_array = np.array(img.convert("RGB"))
                        avg_brightness = np.mean(img_array)
                    else:
                        time.sleep(10)
                        continue

                # Calculate optimal exposure
                current_exposure = int(self.exposure_slider.value)
                target_brightness = 128
                brightness_ratio = target_brightness / max(avg_brightness, 1)
                new_exposure = int(current_exposure * brightness_ratio)

                # Clamp to slider range
                new_exposure = max(100, min(4000, new_exposure))

                # Only adjust if change is significant (>5%)
                if abs(new_exposure - current_exposure) / current_exposure > 0.05:
                    print(
                        f"Auto-exposure: brightness={avg_brightness:.1f}, {current_exposure} → {new_exposure}"
                    )

                    # Update slider and camera
                    self.exposure_slider.value = new_exposure
                    self.exposure_value_text.value = f"Exposure: {new_exposure}"

                    if self.image_processor.set_realsense_exposure(new_exposure):
                        pass  # Success

                    self.page.update()

                # Wait 10 seconds before next check (sporadic to improve responsiveness)
                time.sleep(10)

            except Exception as e:
                print(f"Auto-exposure error: {e}")
                time.sleep(10)

    def _on_tab_changed(self, e):
        """Handle tab change - switch detection mode based on tab"""
        if e.control.selected_index == 0:  # Manual tab (index 0)
            # Unfreeze video if frozen
            if self.video_frozen:
                print("Switching to Manual mode - resuming real-time camera")
                self._unfreeze_video()
            # Switch to camera-only mode (no detection) to save CPU/GPU
            if self.image_processor:
                self.image_processor.set_detection_mode("camera")
                self._update_status()
                print("Manual mode: Detection disabled (camera only)")
            # Hide refresh button on Manual tab
            self.refresh_camera_btn.visible = False
            self.page.update()
        elif e.control.selected_index == 1:  # Auto tab (index 1)
            # Switch to object detection mode
            if self.image_processor:
                self.image_processor.set_detection_mode("objects")
                self._update_status()
                print("Auto mode: Object detection enabled")
            # Show refresh button on Auto tab
            self.refresh_camera_btn.visible = True
            self.page.update()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard shortcuts"""
        if e.key == "T" and e.shift is False and e.ctrl is False and e.alt is False:
            self._toggle_detection_mode()
        elif e.key == "L" and e.shift is False and e.ctrl is False and e.alt is False:
            self._toggle_detection_logging()

    def _on_window_event(self, e):
        """Handle window events (resized, moved, close, etc.)"""
        from aaa_core.config.settings import save_window_geometry

        # Debug: log all window events
        print(f"[DEBUG] Window event: {e.data}", flush=True)

        # Handle window close - clean up resources and destroy window
        if e.data == "close":
            print("[DEBUG] Window close event received, cleaning up...", flush=True)
            self.cleanup()
            print("[DEBUG] Destroying window...", flush=True)
            self.page.window.destroy()
            return

        # Save geometry on resized or moved events
        if e.data in ("resized", "moved"):
            if (
                self.page.window.width
                and self.page.window.height
                and self.page.window.left is not None
                and self.page.window.top is not None
            ):
                save_window_geometry(
                    width=int(self.page.window.width),
                    height=int(self.page.window.height),
                    left=int(self.page.window.left),
                    top=int(self.page.window.top),
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
                # Copy latest depth frame if available for later point cloud extraction
                try:
                    if (
                        hasattr(self.image_processor, "depth_frame")
                        and self.image_processor.depth_frame is not None
                    ):
                        self.frozen_depth_frame = (
                            self.image_processor.depth_frame.copy()
                        )
                    else:
                        self.frozen_depth_frame = None
                except Exception as ex:
                    self.frozen_depth_frame = None
                    print(f"Find Objects: could not copy depth frame: {ex}")
                # Copy aligned color frame (848x480, pixel-aligned to depth)
                self.frozen_aligned_color = getattr(
                    self.image_processor, "_last_aligned_color", None
                )
                if self.frozen_aligned_color is not None:
                    self.frozen_aligned_color = self.frozen_aligned_color.copy()
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
                # Copy latest depth frame if available for later point cloud extraction
                try:
                    if (
                        hasattr(self.image_processor, "depth_frame")
                        and self.image_processor.depth_frame is not None
                    ):
                        self.frozen_depth_frame = (
                            self.image_processor.depth_frame.copy()
                        )
                    else:
                        self.frozen_depth_frame = None
                except Exception as ex:
                    self.frozen_depth_frame = None
                    print(f"Find Objects: could not copy depth frame: {ex}")
                # Copy aligned color frame (848x480, pixel-aligned to depth)
                self.frozen_aligned_color = getattr(
                    self.image_processor, "_last_aligned_color", None
                )
                if self.frozen_aligned_color is not None:
                    self.frozen_aligned_color = self.frozen_aligned_color.copy()
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

    def _export_selected_object_pointcloud(
        self, e=None, subsample: int = 4, to_meters: bool = True
    ):
        """Export selected object's point cloud to logs/pointclouds as compressed .npz"""
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=to_meters
        )
        if not pts:
            print("No points available to export")
            return

        # Show overlay of sampled points for user verification before saving
        try:
            self._show_point_overlay(
                self.selected_object, subsample=max(1, subsample), duration=1.5
            )
            # Give user a brief moment to see overlay
            import time

            time.sleep(1.0)
        except Exception as ex:
            print(f"Overlay failed: {ex}")

        arr = np.array(pts)
        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_obj{self.selected_object + 1}_{timestamp}.npz"
        try:
            # Extract RGB colors from aligned color frame (848x480, same grid as depth)
            save_kwargs = {"points": arr}
            aligned_color = getattr(self, "frozen_aligned_color", None)
            depth = getattr(self, "frozen_depth_frame", None)
            if aligned_color is not None and depth is not None:
                colors = self._extract_object_colors(
                    self.selected_object, subsample=subsample, aligned_color=aligned_color, depth=depth
                )
                if colors is not None and len(colors) == len(arr):
                    save_kwargs["colors"] = colors

            np.savez_compressed(out_path, **save_kwargs)
            has_colors = "colors" in save_kwargs
            print(f"✓ Point cloud saved: {out_path} ({arr.shape[0]} points, rgb={'yes' if has_colors else 'no'})")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Point cloud saved: {out_path.name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to save point cloud: {ex}")

    def _export_full_pointcloud(
        self, e=None, subsample: int = 1, to_meters: bool = True
    ):
        """Export the full depth frame as a compressed .npz containing points (X,Y,Z) in meters when available.

        This exports all non-zero depth pixels (optionally subsampled) from the current frozen depth frame (if frozen)
        or the latest depth frame from the image processor.
        """
        import time
        from pathlib import Path

        import numpy as np

        # Choose depth frame: prefer frozen depth frame if video is frozen
        depth = None
        if (
            getattr(self, "video_frozen", False)
            and getattr(self, "frozen_depth_frame", None) is not None
        ):
            depth = self.frozen_depth_frame.copy()
        else:
            depth = (
                getattr(self.image_processor, "depth_frame", None)
                if getattr(self, "image_processor", None)
                else None
            )

        if depth is None:
            print("No depth frame available to export")
            if hasattr(self, "status_text"):
                self.status_text.value = "No depth frame available to export"
                self.page.update()
            return

        h, w = depth.shape[:2]

        # Get all non-zero depth pixels
        ys, xs = np.nonzero(depth)
        if subsample > 1:
            ys = ys[::subsample]
            xs = xs[::subsample]

        depths = depth[ys, xs]

        points_list = []
        use_realsense = getattr(
            self.image_processor, "use_realsense", False
        ) and getattr(self.image_processor, "rs_camera", None)
        intr = None
        rs_mod = None
        if to_meters and use_realsense:
            try:
                import pyrealsense2 as rs_mod

                profile = self.image_processor.rs_camera.profile
                depth_stream = profile.get_stream(
                    rs_mod.stream.depth
                ).as_video_stream_profile()
                intr = depth_stream.get_intrinsics()
            except Exception as e:
                intr = None
                print(f"Failed to get RealSense intrinsics: {e}")

        # Build points list (deproject if intrinsics available)
        for u, v, z in zip(xs, ys, depths):
            if z == 0:
                continue
            if to_meters and use_realsense and intr is not None:
                try:
                    pt = rs_mod.rs2_deproject_pixel_to_point(
                        intr, [int(u), int(v)], float(z) / 1000.0
                    )
                    points_list.append((float(pt[0]), float(pt[1]), float(pt[2])))
                except Exception:
                    points_list.append((int(u), int(v), int(z)))
            else:
                points_list.append((int(u), int(v), int(z)))

        arr = np.array(points_list)
        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_full_{timestamp}.npz"
        try:
            # Extract RGB colors from aligned color frame (same 848x480 grid as depth)
            save_kwargs = {"points": arr}
            aligned_color = None
            if getattr(self, "video_frozen", False):
                aligned_color = getattr(self, "frozen_aligned_color", None)
            else:
                aligned_color = getattr(self.image_processor, "_last_aligned_color", None) if getattr(self, "image_processor", None) else None

            if aligned_color is not None:
                # xs, ys are in depth coordinates; filter to valid (z > 0) same as points_list
                valid = depths > 0
                xs_valid = xs[valid]
                ys_valid = ys[valid]
                colors_bgr = aligned_color[ys_valid, xs_valid]
                colors_rgb = colors_bgr[:, ::-1].copy()
                if len(colors_rgb) == len(arr):
                    save_kwargs["colors"] = colors_rgb

            np.savez_compressed(out_path, **save_kwargs)
            has_colors = "colors" in save_kwargs
            print(f"✓ Full point cloud saved: {out_path} ({arr.shape[0]} points, rgb={'yes' if has_colors else 'no'})")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Full point cloud saved: {out_path.name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to save full point cloud: {ex}")

    def _export_selected_object_ply(self, e=None, subsample: int = 4):
        """Export selected object's point cloud to PLY (XYZ in meters when available)."""
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=True
        )
        if not pts:
            print("No points available to export")
            return

        # Show overlay of sampled points for user verification before saving
        try:
            self._show_point_overlay(
                self.selected_object, subsample=max(1, subsample), duration=1.5
            )
            import time

            time.sleep(1.0)
        except Exception as ex:
            print(f"Overlay failed: {ex}")

        arr = np.array(pts, dtype=float)

        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_obj{self.selected_object + 1}_{timestamp}.ply"

        try:
            with open(out_path, "w") as f:
                f.write("ply\nformat ascii 1.0\n")
                f.write(f"element vertex {arr.shape[0]}\n")
                f.write("property float x\nproperty float y\nproperty float z\n")
                f.write("end_header\n")
                for x, y, z in arr:
                    f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

            print(f"✓ PLY saved: {out_path} ({arr.shape[0]} points)")
            # Record last exported path for preview
            try:
                self.last_exported_ply = str(out_path)
            except Exception:
                self.last_exported_ply = None

            if hasattr(self, "status_text"):
                self.status_text.value = f"PLY saved: {out_path.name}"
                self.page.update()
            return str(out_path)
        except Exception as ex:
            print(f"Failed to save PLY: {ex}")
            return None

    def _preview_selected_object_ply(self, e=None):
        """Preview the last exported PLY file using Cloudview.py as a subprocess."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        # Ensure there is an exported file; try to export if not present
        if not getattr(self, "last_exported_ply", None):
            print("No previously exported PLY found - exporting now...")
            path = self._export_selected_object_ply(e)
        else:
            path = self.last_exported_ply

        if not path:
            print("No PLY available to preview")
            return

        # Resolve Cloudview script path
        cwd = Path.cwd()
        cloudview_candidate = cwd / "Cloudview.py"
        if not cloudview_candidate.exists():
            # Try to locate Cloudview anywhere in repo
            import glob

            matches = glob.glob("**/Cloudview.py", recursive=True)
            if matches:
                cloudview_candidate = Path(matches[0])
            else:
                print("Cloudview.py not found in repo - cannot preview")
                return

        try:
            # Launch Cloudview in background
            subprocess.Popen(
                [sys.executable, str(cloudview_candidate), str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Launching Cloudview for: {path}")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Previewing: {Path(path).name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to launch Cloudview: {ex}")

    def _on_show_points(self, e=None):
        """UI handler for the Show Points button - switch to depth view and show overlay for selected object."""
        if self.selected_object is None:
            print("No object selected to show points")
            return
        # Switch to depth view when showing points so we can highlight depth pixels
        self._show_point_overlay(
            self.selected_object, subsample=8, duration=2.0, switch_to_depth=True
        )

    def _show_point_overlay(
        self,
        object_index: int,
        subsample: int = 8,
        duration: float = 1.5,
        switch_to_depth: bool = True,
    ):
        """Temporarily overlay sampled mask pixels on the frozen frame for visual verification.

        object_index: index of selected object
        subsample: keep every Nth mask pixel for performance
        duration: seconds to display overlay before clearing
        switch_to_depth: if True, temporarily switch display to depth visualization while overlay is shown
        """
        import threading

        if object_index is None:
            return

        # If requested, switch to depth view temporarily (only if RealSense is available)
        prev_depth_view = None
        try:
            if (
                switch_to_depth
                and getattr(self, "image_processor", None)
                and self.image_processor.use_realsense
            ):
                prev_depth_view = getattr(
                    self.image_processor, "show_depth_visualization", False
                )
                if not prev_depth_view:
                    # Turn on depth visualization
                    try:
                        self.image_processor.toggle_depth_visualization()
                        # Update depth toggle button appearance
                        self.depth_toggle_btn.bgcolor = "#2196F3"
                        self.depth_toggle_btn.icon_color = "#FFFFFF"
                        self.depth_toggle_btn.tooltip = (
                            "Showing Depth view (click for RGB)"
                        )
                        if self._ui_built:
                            self.page.update()
                    except Exception:
                        prev_depth_view = None
        except Exception:
            prev_depth_view = None

        points = self.get_object_mask_pixels(object_index, subsample=subsample)
        if not points:
            print("No mask pixels available for overlay")
            return

        # Store overlay points and refresh display
        self._overlay_points = points
        try:
            self._update_frozen_frame_highlight()
            if self._ui_built:
                self.page.update()
        except Exception:
            pass

        # Clear overlay after duration in background thread and optionally restore depth view
        def clear_overlay():
            import time

            time.sleep(duration)
            self._overlay_points = None
            try:
                self._update_frozen_frame_highlight()
                if self._ui_built:
                    self.page.update()
            except Exception:
                pass

            # Restore previous depth view if we changed it
            try:
                if (
                    prev_depth_view is False
                    and getattr(self, "image_processor", None)
                    and getattr(self.image_processor, "use_realsense", False)
                ):
                    # Toggle back to previous (RGB) view
                    self.image_processor.toggle_depth_visualization()
                    # Update depth toggle button appearance
                    self.depth_toggle_btn.bgcolor = "#E0E0E0"
                    self.depth_toggle_btn.icon_color = "#424242"
                    self.depth_toggle_btn.tooltip = "Showing RGB view (click for Depth)"
                    if self._ui_built:
                        self.page.update()
            except Exception:
                pass

        threading.Thread(target=clear_overlay, daemon=True).start()

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
        print("[DEBUG] Cleaning up resources...")
        if self.image_processor:
            print("[DEBUG] Stopping image processor...")
            self.image_processor.stop()
        if self.button_controller:
            print("[DEBUG] Stopping button controller...")
            self.button_controller.stop()
        if self.arm_controller:
            print("[DEBUG] Disconnecting arm...")
            self.arm_controller.disconnect_arm()
        print("[DEBUG] Cleanup complete")
