"""
Main Window GUI
PyQt6 main window handling UI and event connections
"""

import time

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from config.settings import app_config
from hardware.button_controller import ButtonController
from hardware.camera_manager import CameraManager
from workers.image_processor import ImageProcessor


class MainWindow(QtWidgets.QMainWindow):
    """Main application window"""

    ARM_DIRECTIONS = ["x", "y", "z", "grip"]

    def __init__(self, *args, **kwargs):
        """Initialize main window and components"""
        super(MainWindow, self).__init__(*args, **kwargs)

        # Load Qt Designer GUI
        # Load UI file from same directory as this module
        import os

        ui_path = os.path.join(os.path.dirname(__file__), "draftGUI.ui")
        uic.loadUi(ui_path, self)

        # Initialize components
        self._setup_button_controls()
        self._setup_camera_selection()
        self._setup_image_processor()
        self._print_system_status()

    def _setup_button_controls(self):
        """Connect robotic arm control buttons"""
        self.button_controller = ButtonController(
            hold_threshold=app_config.button_hold_threshold
        )

        for button_direction in self.ARM_DIRECTIONS:
            # Positive direction buttons
            button = getattr(self, f"{button_direction}_pos")
            button.pressed.connect(
                lambda name=button_direction: self._on_button_action(name, "pressed")
            )
            button.released.connect(
                lambda name=button_direction: self._on_button_action(name, "released")
            )

            # Negative direction buttons
            button = getattr(self, f"{button_direction}_neg")
            button.pressed.connect(
                lambda name=button_direction: self._on_button_action(name, "pressed")
            )
            button.released.connect(
                lambda name=button_direction: self._on_button_action(name, "released")
            )

        # Grip state toggle
        self.grip_state.clicked.connect(
            lambda: self._on_button_action("grip_state", "clicked")
        )

    def _setup_camera_selection(self):
        """Setup camera selection dropdown"""
        self.camera_manager = CameraManager(
            max_cameras_to_check=app_config.max_cameras_to_check
        )
        cameras = self.camera_manager.get_camera_info()

        # Populate camera dropdown
        for camera_info in cameras:
            camera_name = (
                f"{camera_info.get('camera_index')} {camera_info.get('camera_name')}"
            )
            self.comboCamera.addItem(camera_name)

        self.comboCamera.currentIndexChanged.connect(self._on_camera_changed)

    def _setup_image_processor(self):
        """Initialize and start image processing thread"""
        self.image_processor = ImageProcessor(
            display_width=app_config.display_width,
            display_height=app_config.display_height,
        )
        self.image_processor.ImageUpdate.connect(self._update_image_display)
        self.image_processor.start()

    def _print_system_status(self):
        """Print system capabilities and settings"""
        print("\n" + "=" * 40)
        print("SYSTEM STATUS")
        print("=" * 40)
        print(
            f"RealSense:         {'✓ Available' if self.image_processor.use_realsense else '✗ Not available'}"
        )

        seg_model = (
            app_config.segmentation_model.upper()
            if app_config.segmentation_model
            else "None"
        )
        print(
            f"Segmentation:      {seg_model if self.image_processor.has_object_detection else '✗ Not available'}"
        )
        print(f"Detection Mode:    {self.image_processor.detection_mode}")
        print(f"Toggle Key:        Press 'T' to switch modes")
        print("=" * 40 + "\n")

    def _on_camera_changed(self, selection_index: int):
        """Handle camera selection change"""
        selection_text = self.comboCamera.currentText().split()
        if len(selection_text) > 0:
            new_camera_index = int(selection_text[0])
            print(f"Switching to camera {new_camera_index}")
            self.image_processor.camera_changed(new_camera_index)

    def _update_image_display(self, image: QtGui.QImage):
        """Update the video feed display"""
        self.labelFeed.setPixmap(QtGui.QPixmap.fromImage(image))

    def _on_button_action(self, button_name: str, action_type: str):
        """Handle robotic arm button actions"""
        print(f"Button {button_name} {action_type}")

        if action_type == "pressed":
            self.start_time = time.time()
            self.button_controller.start()

        self.button_controller.update_button_state(
            action_type, self.start_time if action_type == "pressed" else 0, button_name
        )

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == QtCore.Qt.Key.Key_T:
            self._toggle_detection_mode()
        super().keyPressEvent(event)

    def _toggle_detection_mode(self):
        """Toggle between face tracking and object detection"""
        self.image_processor.toggle_detection_mode()

    def closeEvent(self, event):
        """Clean up on window close"""
        print("Shutting down...")
        self.image_processor.stop()
        event.accept()
