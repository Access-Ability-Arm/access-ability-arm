"""
Flet Main Window
Modern cross-platform GUI using Flet framework
"""

import sys
import threading
import time

from aaa_core.config.settings import app_config
from aaa_core.hardware.button_controller import ButtonController
from aaa_core.hardware.camera_manager import CameraManager
from aaa_core.workers.image_processor import ImageProcessor

# Try to import daemon components (may not be available)
try:
    from aaa_core.daemon.camera_client import CameraClient
    from aaa_core.workers.daemon_image_processor import DaemonImageProcessor

    DAEMON_AVAILABLE = True
except ImportError:
    DAEMON_AVAILABLE = False

import flet as ft

# Import Flet-compatible arm controller
if app_config.lite6_available:
    from aaa_core.workers.arm_controller_flet import ArmControllerFlet

# Import mixins
from ._mixin_arm_control import ArmControlMixin
from ._mixin_camera import CameraMixin
from ._mixin_object_detection import ObjectDetectionMixin
from ._mixin_point_cloud import PointCloudMixin
from ._mixin_video_display import VideoDisplayMixin


class FletMainWindow(
    PointCloudMixin,
    ObjectDetectionMixin,
    ArmControlMixin,
    CameraMixin,
    VideoDisplayMixin,
):
    """Main application window using Flet.

    Composes behavior from mixins:
    - PointCloudMixin: Point cloud extraction, export (NPZ/PLY), preview
    - ObjectDetectionMixin: Object selection, 3D analysis, gripper overlay
    - ArmControlMixin: Arm movement, gripper, connection management
    - CameraMixin: Camera switching, daemon, exposure control
    - VideoDisplayMixin: Video feed rendering, label drawing
    """

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
        self.frozen_display_depth = None  # Store display depth (1920x1080) at freeze time
        self.object_analysis = None  # ObjectAnalysis result for selected object
        self._analysis_in_progress = False  # Flag for background analysis thread
        self.last_exported_ply = None  # Path to the last exported PLY file
        self._overlay_points = None  # Temporary overlay points to show on frozen frame
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
                        width=135,
                        height=38,
                    ),
                    # Object selection buttons (shown when frozen)
                    self.object_buttons_row,
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
            ),
            padding=20,
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

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        if self.image_processor:
            self.image_processor.toggle_detection_mode()
            self._update_status()

    def _toggle_detection_logging(self):
        """Toggle detection logging for stability analysis (Press 'L')"""
        if self.image_processor:
            self.image_processor.toggle_detection_logging()

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
