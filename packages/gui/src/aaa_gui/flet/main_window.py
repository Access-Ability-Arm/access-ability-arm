"""
Flet Main Window
Modern cross-platform GUI using Flet framework
"""

import sys
import threading
import time
from enum import Enum

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

# Import screen builders
from ._screen_live_view import build_screen_live_view
from ._screen_object_selection import build_screen_object_selection
from ._screen_grasp_preview import build_screen_grasp_preview
from ._screen_manual_control import build_screen_manual_control
from ._screen_settings import build_screen_settings, build_settings_dimmer


class Screen(Enum):
    """Application screens for the state machine."""
    LIVE_VIEW = "live_view"
    OBJECT_SELECTION = "object_selection"
    GRASP_PREVIEW = "grasp_preview"
    MANUAL_CONTROL = "manual_control"
    SETTINGS = "settings"


class FletMainWindow(
    PointCloudMixin,
    ObjectDetectionMixin,
    ArmControlMixin,
    CameraMixin,
    VideoDisplayMixin,
):
    """Main application window using Flet.

    Composes behavior from mixins:
    - PointCloudMixin: Point cloud extraction, PLY export, preview
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
        self.page.padding = 0
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
        self._hovered_object = None  # Currently hovered object card index
        self._camera_hovered_object = None  # Object hovered via camera label

        # Screen state machine
        self.current_screen = Screen.LIVE_VIEW
        self._screen_containers = {}

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

    # ------------------------------------------------------------------ #
    #  Object action buttons (kept for compatibility with mixins)         #
    # ------------------------------------------------------------------ #

    def _create_object_action_buttons(self):
        """Create action buttons that appear only when an object is selected.
        These are now embedded in the grasp preview screen's 'More' menu,
        but we keep them for backward compatibility with mixin references.
        """
        self.export_ply_btn = None
        self.export_mesh_btn = None
        self.complete_shape_btn = None
        if self.show_points_btn is None:
            self.show_points_btn = None
        self.object_action_buttons = ft.Column(controls=[], visible=False)
        return self.object_action_buttons

    def _update_object_action_visibility(self):
        """Show/hide object action buttons based on current selection state."""
        # In the new UI, this is handled by screen navigation
        pass

    # ------------------------------------------------------------------ #
    #  Build UI — Screen-based Stack layout                               #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        """Build the Flet UI layout using screen-based Stack architecture."""

        # Update loading message
        self.loading_text.value = "Building interface..."
        self.page.update()
        # Clear the initial loading screen
        self.page.clean()

        # Video feed display (full-screen, responsive)
        self.video_feed = ft.Image(
            src_base64="",  # Will be updated by image processor
            fit=ft.ImageFit.COVER,
            expand=True,
        )

        # Loading placeholder (shown until first frame arrives)
        self.camera_loading_text = ft.Text(
            "Loading camera feed...",
            size=16,
            color="#607D8B",
            weight=ft.FontWeight.W_400,
        )
        self.loading_placeholder = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(color="#607D8B"),
                    self.camera_loading_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#1A2327",
            alignment=ft.alignment.center,
            visible=True,
            expand=True,
        )

        # Video container (base layer)
        self.video_container = ft.Container(
            content=ft.Stack(
                [self.video_feed, self.loading_placeholder],
                expand=True,
            ),
            expand=True,
        )

        # Object selection buttons row (kept for mixin compatibility)
        self.object_buttons_row = ft.Row(
            controls=[], spacing=10, wrap=True, visible=False,
        )

        # Track if first frame has been received
        self._first_frame_received = False

        # Check if daemon is running to determine camera options
        daemon_running = self._check_daemon_running()

        # Build camera dropdown (needed by _start_image_processor)
        cameras = self.camera_manager.get_camera_info()
        camera_options = []

        if daemon_running:
            camera_options.append(
                ft.dropdown.Option(
                    key="daemon",
                    text="RealSense D435 (via daemon - with depth)",
                )
            )

        for cam in cameras:
            if cam.get("color_type") == "Infrared":
                continue
            if sys.platform == "darwin" and "RealSense" in cam["camera_name"]:
                continue
            name = cam["camera_name"]
            if len(name) > 70:
                name = name[:67] + "..."
            resolution = cam["resolution"]
            if "RealSense" in cam["camera_name"] and resolution == "640x480":
                resolution = "1920x1080"
            display_text = (
                f"[{cam['camera_index']}] {name} - {resolution} ({cam['color_type']})"
            )
            camera_options.append(
                ft.dropdown.Option(
                    key=str(cam["camera_index"]),
                    text=display_text,
                )
            )

        if len(camera_options) == 1:
            camera_display_text = f"Camera: {camera_options[0].text}"
            self.camera_dropdown = ft.Text(
                camera_display_text, size=14, weight=ft.FontWeight.W_500, color="#1976D2",
            )
            self.camera_dropdown.value = camera_options[0].key
        else:
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
                width=600,
                disabled=False,
            )

        # Status text (kept for mixin compatibility)
        self.status_text = ft.Text("Initializing...", size=12, color="#455A64")

        # Arm status text (kept for mixin compatibility)
        arm_connected = (
            app_config.lite6_available
            and self.arm_controller
            and self.arm_controller.is_connected()
        )
        self.arm_status_text = ft.Text(
            f"Arm: {'✓ Connected' if arm_connected else 'Not connected'}",
            size=12,
            color="#2E7D32" if arm_connected else "#F57C00",
        )

        # Connect button (kept for mixin compatibility)
        self.arm_connect_btn = ft.ElevatedButton(
            text="Disconnect Arm" if arm_connected else "Connect Arm",
            on_click=lambda e: self._on_connect_arm(e),
            width=140,
        )

        # Camera control buttons (kept for mixin/handler compatibility)
        self.flip_camera_btn = ft.IconButton(
            icon=ft.Icons.FLIP,
            tooltip="Flip camera horizontally (mirror)",
            on_click=lambda _: self._on_flip_camera(),
            bgcolor="#E0E0E0",
            icon_color="#424242",
        )
        self.depth_toggle_btn = ft.IconButton(
            icon=ft.Icons.LAYERS,
            tooltip="Toggle RGB/Depth view",
            on_click=lambda _: self._on_toggle_depth_view(),
            bgcolor="#E0E0E0",
            icon_color="#424242",
            visible=False,
        )
        self.refresh_camera_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refresh camera view",
            on_click=lambda _: self._on_refresh_camera(),
            bgcolor="#E0E0E0",
            icon_color="#424242",
            visible=False,
        )

        # Exposure controls (kept for mixin compatibility)
        self.exposure_value_text = ft.Text("Exposure: 800", size=12, color="#666")
        self.exposure_slider = ft.Slider(
            min=100, max=4000, value=800, divisions=78,
            label="Exposure: {value}", on_change=self._on_exposure_change,
            visible=False, width=300,
        )
        self.auto_exposure_enabled = False
        self.auto_exposure_thread = None
        self.auto_exposure_btn = ft.IconButton(
            icon=ft.Icons.AUTO_MODE,
            tooltip="Auto-adjust exposure",
            on_click=lambda _: self._auto_adjust_exposure(),
            bgcolor="#E0E0E0", icon_color="#424242", visible=False,
        )
        self.exposure_controls = ft.Row(
            [self.exposure_slider, self.exposure_value_text, self.auto_exposure_btn],
            visible=False, spacing=10,
        )

        # Speed label (kept for mixin compatibility)
        self.speed_label = ft.Text(
            f"Speed: {self.movement_speed_percent}%", size=14, weight=ft.FontWeight.BOLD,
        )

        # Show Points button (kept for mixin compatibility)
        self.show_points_btn = None

        # Create object action buttons (kept for mixin compatibility)
        self._create_object_action_buttons()

        # --- Build screen containers ---
        self._screen_containers[Screen.LIVE_VIEW] = build_screen_live_view(self)
        self._screen_containers[Screen.OBJECT_SELECTION] = build_screen_object_selection(self)
        self._screen_containers[Screen.GRASP_PREVIEW] = build_screen_grasp_preview(self)
        self._screen_containers[Screen.MANUAL_CONTROL] = build_screen_manual_control(self)

        # Settings has a dimmer + panel
        self._settings_dimmer = build_settings_dimmer(self)
        self._settings_dimmer.visible = False
        self._screen_containers[Screen.SETTINGS] = build_screen_settings(self)

        # Set initial visibility
        for screen, container in self._screen_containers.items():
            container.visible = (screen == Screen.LIVE_VIEW)

        # --- Assemble the full-screen Stack ---
        self.page.add(
            ft.Stack(
                [
                    # Base layer: video
                    self.video_container,
                    # Screen overlays
                    self._screen_containers[Screen.LIVE_VIEW],
                    self._screen_containers[Screen.OBJECT_SELECTION],
                    self._screen_containers[Screen.GRASP_PREVIEW],
                    self._screen_containers[Screen.MANUAL_CONTROL],
                    # Settings overlay (dimmer + panel)
                    self._settings_dimmer,
                    self._screen_containers[Screen.SETTINGS],
                ],
                expand=True,
            )
        )

        # Keyboard shortcuts
        self.page.on_keyboard_event = self._on_keyboard_event

        # Mark UI as built to allow page.update() in callbacks
        self._ui_built = True

    # ------------------------------------------------------------------ #
    #  Screen Navigation                                                  #
    # ------------------------------------------------------------------ #

    def _navigate_to(self, screen: Screen):
        """Navigate to a screen by toggling visibility."""
        prev = self.current_screen
        self.current_screen = screen

        # Hide all screens
        for s, container in self._screen_containers.items():
            container.visible = (s == screen)

        # Settings dimmer
        self._settings_dimmer.visible = (screen == Screen.SETTINGS)

        # If leaving settings, show the previous screen underneath
        if screen != Screen.SETTINGS and prev == Screen.SETTINGS:
            # Settings was overlay — restore whichever screen was underneath
            pass

        # Reset object panel to loading state on each visit
        if screen == Screen.OBJECT_SELECTION and hasattr(self, "cards_loading_indicator"):
            self.object_card_row.controls.clear()
            self.cards_loading_indicator.visible = True

        # Handle detection mode changes
        if screen == Screen.LIVE_VIEW:
            if self.image_processor:
                self.image_processor.set_detection_mode("camera")
            if self.video_frozen:
                self._unfreeze_video()
        elif screen == Screen.MANUAL_CONTROL:
            if self.image_processor:
                self.image_processor.set_detection_mode("camera")

        self._update_status()
        self.page.update()

    def _navigate_to_settings(self):
        """Show settings as an overlay (doesn't hide the current screen)."""
        self._settings_dimmer.visible = True
        self._screen_containers[Screen.SETTINGS].visible = True
        # Update settings panel state
        self._sync_settings_panel()
        self.page.update()

    def _close_settings(self):
        """Close the settings overlay."""
        self._settings_dimmer.visible = False
        self._screen_containers[Screen.SETTINGS].visible = False
        self.page.update()

    def _navigate_to_manual_control(self):
        """Navigate to manual control screen."""
        self._navigate_to(Screen.MANUAL_CONTROL)

    def _back_from_manual_control(self):
        """Go back from manual control to live view."""
        self._navigate_to(Screen.LIVE_VIEW)

    def _on_find_objects_and_navigate(self):
        """Find objects then navigate to object selection screen."""
        self._on_find_objects()
        # Navigate after a brief delay to let detection start
        def navigate_after_freeze():
            # Wait for video to freeze (1 second capture + small buffer)
            time.sleep(1.5)
            self._navigate_to(Screen.OBJECT_SELECTION)
        threading.Thread(target=navigate_after_freeze, daemon=True).start()

    def _back_from_object_selection(self):
        """Go back from object selection to live view, unfreezing video."""
        self._unfreeze_video()
        self._navigate_to(Screen.LIVE_VIEW)

    def _on_object_card_tapped(self, object_index: int):
        """Handle tapping an object card — select it and go to grasp preview."""
        self._on_object_selected(object_index)
        self._update_grasp_info_card()
        self._navigate_to(Screen.GRASP_PREVIEW)

    def _back_from_grasp_preview(self):
        """Go back from grasp preview to object selection."""
        self.selected_object = None
        self.object_analysis = None
        self._analysis_in_progress = False
        self._update_frozen_frame_highlight()
        self._navigate_to(Screen.OBJECT_SELECTION)

    def _retry_grasp(self):
        """Re-scan: unfreeze, recapture, and go back to object selection."""
        self._unfreeze_video()
        self._on_find_objects()
        def navigate_after_freeze():
            time.sleep(1.5)
            self._navigate_to(Screen.OBJECT_SELECTION)
        threading.Thread(target=navigate_after_freeze, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  Object Card Population (for Screen 2)                              #
    # ------------------------------------------------------------------ #

    def _populate_object_cards(self):
        """Create styled card containers in the object_card_row for Screen 2.

        Prototype spec (2-select-a-cards.html):
        - Cards: min-w-[160px], border-2 rounded-2xl p-4, bg-white
        - Number badge: w-8 h-8 (32px) rounded-full, colored bg, text-lg font-bold
        - Title: text-lg font-semibold, text color matches badge
        - Subtitle: text-sm text-gray-400
        """
        from . import _design_tokens as T

        if not self.frozen_detections:
            return

        self.object_card_row.controls.clear()
        self.cards_loading_indicator.visible = False
        classes = self.frozen_detections["classes"]

        for i, class_name in enumerate(classes):
            color = T.CARD_COLORS[i % len(T.CARD_COLORS)]

            # Number badge: w-8 h-8 rounded-full
            badge = ft.Container(
                content=ft.Text(
                    str(i + 1), size=T.TEXT_LG, color=T.WHITE, weight=ft.FontWeight.W_700,
                ),
                bgcolor=color,
                border_radius=T.RADIUS_FULL,
                width=32,
                height=32,
                alignment=ft.alignment.center,
            )

            card = ft.Container(
                content=ft.Row(
                    [
                        badge,
                        ft.Column(
                            [
                                ft.Text(
                                    class_name.capitalize(),
                                    size=T.TEXT_LG,
                                    color=T.GRAY_700,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    "Tap to select",
                                    size=T.TEXT_SM,
                                    color=T.GRAY_400,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=T.WHITE,
                border=ft.border.all(2, T.GRAY_200),
                border_radius=T.RADIUS_2XL,
                width=T.CARD_MIN_W,
                height=T.CARD_MIN_H,
                alignment=ft.alignment.center_left,
                padding=ft.padding.all(T.CARD_PADDING),
                on_click=lambda _, idx=i: self._on_object_card_tapped(idx),
                on_hover=lambda e, idx=i, c=color: self._on_object_card_hover(e, idx, c),
                ink=True,
            )
            self.object_card_row.controls.append(card)

        self.page.update()

    def _on_object_card_hover(self, e, object_index: int, card_color: str):
        """Handle hover enter/leave on an object card — highlight in camera view."""
        from . import _design_tokens as T

        # Clear camera-hover state so the two sources don't conflict
        self._camera_hovered_object = None

        card = e.control
        if e.data == "true":
            # Hover enter
            self._hovered_object = object_index
            card.border = ft.border.all(3, card_color)
            card.bgcolor = ft.Colors.with_opacity(0.08, card_color)
        else:
            # Hover leave
            self._hovered_object = None
            card.border = ft.border.all(2, T.GRAY_200)
            card.bgcolor = T.WHITE
        card.update()
        # Update camera overlay to highlight hovered object
        self._update_frozen_frame_highlight()
        self._update_video_feed(self.frozen_frame)

    def _on_camera_label_hover(self, e):
        """Handle hover on the camera area — highlight card for nearest object label."""
        from . import _design_tokens as T
        import math

        if not self.frozen_detections or not hasattr(self, "object_card_row"):
            return

        centers = self.frozen_detections.get("centers", [])
        if not centers:
            return

        # Map display coordinates to image coordinates (1920x1080).
        # The video uses ImageFit.COVER in the camera area container.
        page_w = self.page.width or 1920
        # Estimate camera area height: page height minus card panel (~172px)
        card_panel_h = 172
        cam_h = (self.page.height or 1080) - card_panel_h
        cam_w = page_w

        # COVER fit: scale to fill, crop overflow
        scale = max(cam_w / 1920, cam_h / 1080)
        offset_x = (cam_w - 1920 * scale) / 2
        offset_y = (cam_h - 1080 * scale) / 2

        img_x = (e.local_x - offset_x) / scale
        img_y = (e.local_y - offset_y) / scale

        # Find nearest object center within threshold
        hit_radius = 80  # pixels in image coords
        nearest_idx = None
        nearest_dist = float("inf")
        for i, (cx, cy) in enumerate(centers):
            dist = math.sqrt((img_x - cx) ** 2 + (img_y - cy) ** 2)
            if dist < hit_radius and dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        # Skip if hover state hasn't changed
        prev = getattr(self, "_camera_hovered_object", None)
        if nearest_idx == prev:
            return
        self._camera_hovered_object = nearest_idx

        # Reset previous card highlight
        if prev is not None and prev < len(self.object_card_row.controls):
            card = self.object_card_row.controls[prev]
            card.border = ft.border.all(2, T.GRAY_200)
            card.bgcolor = T.WHITE
            card.update()

        # Highlight new card
        if nearest_idx is not None and nearest_idx < len(self.object_card_row.controls):
            color = T.CARD_COLORS[nearest_idx % len(T.CARD_COLORS)]
            card = self.object_card_row.controls[nearest_idx]
            card.border = ft.border.all(3, color)
            card.bgcolor = ft.Colors.with_opacity(0.08, color)
            card.update()

        # Update camera overlay too
        self._hovered_object = nearest_idx
        self._update_frozen_frame_highlight()
        self._update_video_feed(self.frozen_frame)

    def _on_camera_label_tap(self, e):
        """Handle tap on the camera area — select nearest object."""
        import math

        if not self.frozen_detections:
            return

        centers = self.frozen_detections.get("centers", [])
        if not centers:
            return

        page_w = self.page.width or 1920
        card_panel_h = 172
        cam_h = (self.page.height or 1080) - card_panel_h
        cam_w = page_w

        scale = max(cam_w / 1920, cam_h / 1080)
        offset_x = (cam_w - 1920 * scale) / 2
        offset_y = (cam_h - 1080 * scale) / 2

        img_x = (e.local_x - offset_x) / scale
        img_y = (e.local_y - offset_y) / scale

        hit_radius = 80
        nearest_idx = None
        nearest_dist = float("inf")
        for i, (cx, cy) in enumerate(centers):
            dist = math.sqrt((img_x - cx) ** 2 + (img_y - cy) ** 2)
            if dist < hit_radius and dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        if nearest_idx is not None:
            self._on_object_card_tapped(nearest_idx)

    # ------------------------------------------------------------------ #
    #  Grasp Info Card Update (for Screen 3)                              #
    # ------------------------------------------------------------------ #

    def _update_grasp_info_card(self):
        """Update the grasp preview info card with current object data."""
        from . import _design_tokens as T

        if self.selected_object is None or not self.frozen_detections:
            return

        classes = self.frozen_detections["classes"]
        class_name = classes[self.selected_object]
        self.grasp_object_name.value = class_name.capitalize()

        # Update badge color and number
        color = T.CARD_COLORS[self.selected_object % len(T.CARD_COLORS)]
        self.grasp_badge_container.bgcolor = color
        self.grasp_badge_container.content.value = f"#{self.selected_object + 1}"

        if self.object_analysis:
            analysis = self.object_analysis
            # Update confidence
            conf = analysis.grasp_confidence
            self.grasp_confidence_bar.value = conf
            self.grasp_confidence_text.value = f"Confidence: {conf:.0%}"
            # Color the bar
            if conf >= 0.7:
                self.grasp_confidence_bar.color = "#4CAF50"
                self.grasp_status_text.value = "Ready to grasp"
                self.grasp_status_text.color = "#4CAF50"
            elif conf >= 0.4:
                self.grasp_confidence_bar.color = "#FF9800"
                self.grasp_status_text.value = "Grasp possible"
                self.grasp_status_text.color = "#FF9800"
            else:
                self.grasp_confidence_bar.color = "#F44336"
                self.grasp_status_text.value = "Uncertain grasp"
                self.grasp_status_text.color = "#F44336"

            if not analysis.graspable:
                self.grasp_status_text.value = "Not graspable"
                self.grasp_status_text.color = "#F44336"

            # Dimensions
            width_mm = analysis.grasp_width * 1000
            self.grasp_dimensions_text.value = f"Grasp width: {width_mm:.0f}mm"
        else:
            self.grasp_status_text.value = "Analyzing..."
            self.grasp_status_text.color = "#FF9800"
            self.grasp_confidence_bar.value = 0
            self.grasp_confidence_text.value = "Confidence: --"
            self.grasp_dimensions_text.value = "Dimensions: --"

        self.page.update()

    # ------------------------------------------------------------------ #
    #  Speed Segment Control                                              #
    # ------------------------------------------------------------------ #

    def _on_speed_segment_changed(self, e):
        """Handle speed segment button change (Slow/Med/Fast)."""
        selected = e.control.selected
        if not selected:
            return
        value = list(selected)[0]
        speed_map = {"slow": 20, "med": 50, "fast": 100}
        self.movement_speed_percent = speed_map.get(value, 20)
        self.speed_label.value = f"Speed: {self.movement_speed_percent}%"
        print(f"Movement speed set to: {self.movement_speed_percent}%")

    # ------------------------------------------------------------------ #
    #  Settings Panel Sync                                                #
    # ------------------------------------------------------------------ #

    def _sync_settings_panel(self):
        """Sync settings panel widgets with current state."""
        if hasattr(self, "settings_mirror_switch"):
            self.settings_mirror_switch.value = (
                self.image_processor.flip_horizontal if self.image_processor else False
            )
        if hasattr(self, "settings_depth_switch"):
            self.settings_depth_switch.value = (
                getattr(self.image_processor, "show_depth_visualization", False)
                if self.image_processor else False
            )
        # Arm status
        if hasattr(self, "settings_arm_status"):
            arm_connected = (
                app_config.lite6_available
                and self.arm_controller
                and self.arm_controller.is_connected()
            )
            if arm_connected:
                self.settings_arm_status.value = f"Connected ({app_config.lite6_ip})"
                self.settings_arm_status.color = "#4CAF50"
                self.settings_arm_btn.text = "Disconnect Arm"
            else:
                self.settings_arm_status.value = "Not connected"
                self.settings_arm_status.color = "#FF9800"
                self.settings_arm_btn.text = "Connect Arm"

    def _on_settings_camera_changed(self, e):
        """Handle camera change from the settings panel dropdown."""
        # Delegate to the same handler
        self._on_camera_changed(e)

    # ------------------------------------------------------------------ #
    #  Image processor start (unchanged logic)                            #
    # ------------------------------------------------------------------ #

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
                self.using_realsense = True
            except (ConnectionRefusedError, FileNotFoundError, OSError) as e:
                print(f"[WARN] Daemon connection failed: {e}")
                print("[INFO] Falling back to direct camera access (RGB only)")
                daemon_running = False

        if not daemon_running:
            print("[INFO] No daemon - using direct camera access (RGB only)")
            self.image_processor = ImageProcessor(
                display_width=app_config.display_width,
                display_height=app_config.display_height,
                callback=self._update_video_feed,
            )
        print("[DEBUG MainWindow] ImageProcessor created")

        # Set initial camera name for flip detection and trigger camera initialization
        is_daemon_processor = (
            isinstance(self.image_processor, DaemonImageProcessor)
            if DAEMON_AVAILABLE
            else False
        )

        if not is_daemon_processor and self.camera_manager.cameras:
            print(
                "[DEBUG MainWindow] Setting initial camera name for flip detection..."
            )
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
            self.flip_camera_btn.bgcolor = "#4CAF50"
            self.flip_camera_btn.icon_color = "#FFFFFF"
        else:
            self.flip_camera_btn.bgcolor = "#E0E0E0"
            self.flip_camera_btn.icon_color = "#424242"

        # Start processing thread
        print("[DEBUG MainWindow] Starting ImageProcessor thread...")
        self.image_processor.start()
        print("[DEBUG MainWindow] ImageProcessor thread started")

        # Set initial detection mode to "camera" (Live View default)
        self.image_processor.set_detection_mode("camera")
        print("[DEBUG MainWindow] Set initial detection mode to 'camera' (Live View)")

        # Update status
        print("[DEBUG MainWindow] Updating status...")
        self._update_status()
        print("[DEBUG MainWindow] _start_image_processor complete")

    # ------------------------------------------------------------------ #
    #  Status Updates                                                     #
    # ------------------------------------------------------------------ #

    def _update_status(self):
        """Update status displays — both the old status_text and the new status pill."""
        if not self.image_processor:
            return

        has_depth = self.image_processor.use_realsense
        self.depth_toggle_btn.visible = has_depth

        mode = self.image_processor.detection_mode
        mode_display = {
            "face": "Face Tracking",
            "objects": "Object Detection",
            "combined": "Combined",
            "camera": "Camera Only",
        }.get(mode, mode.upper())

        # Update legacy status text
        seg_model = (
            app_config.segmentation_model.upper()
            if app_config.segmentation_model
            else "None"
        )
        seg_status = (
            seg_model
            if self.image_processor.has_object_detection
            else "Not available"
        )
        realsense_status = "With Depth" if has_depth else "RGB Only"
        self.status_text.value = (
            f"RealSense: {realsense_status} | Detection: {seg_status} | Mode: {mode_display}"
        )

        # Update new status pill on live view
        if hasattr(self, "status_pill_text"):
            self.status_pill_text.value = mode_display
            # Green dot for active detection, grey for camera only
            if hasattr(self, "status_pill_dot"):
                self.status_pill_dot.bgcolor = (
                    "#4CAF50" if mode != "camera" else "#78909C"
                )

        # Update arm badge on live view
        if hasattr(self, "arm_badge_icon"):
            arm_connected = (
                app_config.lite6_available
                and self.arm_controller
                and self.arm_controller.is_connected()
            )
            if arm_connected:
                self.arm_badge_icon.name = ft.Icons.LINK
                self.arm_badge_icon.color = "#4CAF50"
            else:
                self.arm_badge_icon.name = ft.Icons.LINK_OFF
                self.arm_badge_icon.color = "#FF9800"

        if self._ui_built:
            self.page.update()

    # ------------------------------------------------------------------ #
    #  Keyboard and Window events                                         #
    # ------------------------------------------------------------------ #

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        if self.image_processor:
            self.image_processor.toggle_detection_mode()
            self._update_status()

    def _toggle_detection_logging(self):
        """Toggle detection logging for stability analysis (Press 'L')"""
        if self.image_processor:
            self.image_processor.toggle_detection_logging()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """Handle keyboard shortcuts"""
        if e.key == "T" and e.shift is False and e.ctrl is False and e.alt is False:
            self._toggle_detection_mode()
        elif e.key == "L" and e.shift is False and e.ctrl is False and e.alt is False:
            self._toggle_detection_logging()
        elif e.key == "Escape":
            # Escape goes back from any screen to live view
            if self.current_screen == Screen.SETTINGS:
                self._close_settings()
            elif self.current_screen != Screen.LIVE_VIEW:
                self._navigate_to(Screen.LIVE_VIEW)
                if self.video_frozen:
                    self._unfreeze_video()

    def _on_window_event(self, e):
        """Handle window events (resized, moved, close, etc.)"""
        from aaa_core.config.settings import save_window_geometry

        print(f"[DEBUG] Window event: {e.data}", flush=True)

        if e.data == "close":
            print("[DEBUG] Window close event received, cleaning up...", flush=True)
            self.cleanup()
            print("[DEBUG] Destroying window...", flush=True)
            self.page.window.destroy()
            return

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

    # ------------------------------------------------------------------ #
    #  Arm commands (kept for mixin compatibility)                        #
    # ------------------------------------------------------------------ #

    def _on_execute(self):
        """Handle Execute button - confirms grasp plan and begins arm motion"""
        print("Execute: Beginning grasp motion...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected - cannot execute grasp")
            return
        print("Grasp execution not yet implemented")

    def _on_stop(self):
        """Handle Stop button - immediately halts all arm movement"""
        print("Stop: Halting all arm movement...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected")
            return
        self.arm_controller.emergency_stop()
        print("Arm stopped")

    def _on_home(self):
        """Handle Home button - returns arm to safe rest position"""
        print("Home: Returning to rest position...")
        if not self.arm_controller or not self.arm_controller.arm:
            print("Arm not connected - cannot move to home")
            return
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
