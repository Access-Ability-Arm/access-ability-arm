import sys
import time
import warnings

import cv2
from PyQt6 import QtCore, QtGui, QtWidgets, uic

warnings.simplefilter("ignore", UserWarning)
sys.coinit_flags = 2
import asyncio
import platform

import cv2
import numpy as np

if platform.system() == "Windows":
    import winsdk.windows.devices.enumeration as windows_devices

import mediapipe as mp

# Try to import RealSense and segmentation models (optional)
REALSENSE_AVAILABLE = False
SEGMENTATION_AVAILABLE = False
SEGMENTATION_MODEL = None

try:
    from realsense_camera import RealsenseCamera

    REALSENSE_AVAILABLE = True
    print("RealSense camera support available")
except ImportError:
    print("RealSense camera not available - using standard webcam only")

# Try YOLOv12-seg first (preferred), fallback to Mask R-CNN
try:
    from yolov12_seg import YOLOv12Seg

    SEGMENTATION_AVAILABLE = True
    SEGMENTATION_MODEL = "yolov12"
    print("YOLOv12-seg object detection available (recommended)")
except ImportError as e:
    print(f"YOLOv12-seg not available: {e}")
    try:
        from mask_rcnn import MaskRCNN

        SEGMENTATION_AVAILABLE = True
        SEGMENTATION_MODEL = "maskrcnn"
        print("Mask R-CNN object detection available (legacy)")
    except ImportError:
        print("No segmentation model available - face tracking only")

# creating the main window


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # loading the qtdesigner GUI I made

        uic.loadUi("draftGUI.ui", self)
        # mapping the buttons to a function--probably a better way of doing this but ¯\_(ツ)_/¯ for the mmt
        self.armDirections = ["x", "y", "z", "grip"]

        # starting button monitor qthread

        for button_direction in self.armDirections:
            button = getattr(
                self, f"{button_direction}_pos"
            )  # Assuming buttons have names like x_pos, y_pos, etc.
            button.pressed.connect(
                lambda button_name=button_direction: self.Button_Action(
                    button_name, "pressed"
                )
            )
            button.released.connect(
                lambda button_name=button_direction: self.Button_Action(
                    button_name, "released"
                )
            )

            button = getattr(self, f"{button_direction}_neg")
            button.pressed.connect(
                lambda button_name=button_direction: self.Button_Action(
                    button_name, "pressed"
                )
            )
            button.released.connect(
                lambda button_name=button_direction: self.Button_Action(
                    button_name, "released"
                )
            )

        self.grip_state.clicked.connect(
            lambda: self.Button_Action("grip_state", "clicked")
        )

        # Starting a second thread to run the camera video

        self.camera_tracker = camera_tracker()
        self.cameras_object = self.camera_tracker.get_camera_info()

        # adding the options to the QComboBox

        for i in self.cameras_object:
            camera_name = str(i.get("camera_index")) + " " + i.get("camera_name")
            self.comboCamera.addItem(camera_name)

        self.comboCamera.currentIndexChanged.connect(self.on_combo_box_changed)

        self.imageMonitor = imageMonitor()
        self.imageMonitor.start()
        self.imageMonitor.ImageUpdate.connect(self.ImageUpdateSlot)

        self.button_monitor = button_monitor()

        # Print camera and detection mode info
        print(f"\n=== Camera Setup ===")
        print(
            f"RealSense: {'Available' if self.imageMonitor.use_realsense else 'Not available'}"
        )
        seg_model_name = SEGMENTATION_MODEL.upper() if SEGMENTATION_MODEL else "None"
        print(
            f"Segmentation Model: {seg_model_name if self.imageMonitor.segmentation_model else 'Not available'}"
        )
        print(f"Detection mode: {self.imageMonitor.detection_mode}")
        print(f"===================\n")

    def on_combo_box_changed(self, selection):
        # splitting the selected text into an index of strings to access the first value, the camera index
        selection = self.comboCamera.currentText().split()
        new_camera_index = int(selection[0])
        print(new_camera_index)
        self.imageMonitor.camera_changed(new_camera_index)

    def ImageUpdateSlot(self, Image):
        self.labelFeed.setPixmap(QtGui.QPixmap.fromImage(Image))

    def toggle_detection_mode(self):
        """Toggle between face tracking and object detection modes"""
        if self.imageMonitor.segmentation_model:
            if self.imageMonitor.detection_mode == "face":
                self.imageMonitor.detection_mode = "objects"
                print("Switched to object detection mode")
            else:
                self.imageMonitor.detection_mode = "face"
                print("Switched to face tracking mode")
        else:
            print("Object detection not available - No segmentation model loaded")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        # Press 'T' to toggle between face tracking and object detection
        if event.key() == QtCore.Qt.Key.Key_T:
            self.toggle_detection_mode()
        super().keyPressEvent(event)

        # basic button function

    def Button_Action(self, button_name, action_type):
        print(f"Button {button_name} {action_type}")

        if action_type == "pressed":
            self.start_time = time.time()
            self.button_monitor.start()

        self.button_monitor.button_state(action_type, self.start_time, button_name)


# button monitor to monitor whether a button is being held or just pressed


class button_monitor(QtCore.QThread):
    button_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super(button_monitor, self).__init__()
        print("button_monitor thread started")
        self.currentState = None
        self.start_time = 0
        self.elapsed_time = 0

    def run(self):
        while self.currentState == "pressed":
            self.elapsed_time = time.time() - self.start_time

            if self.buttonPushed and self.elapsed_time > 0.5:
                print("button is being held")
                self.buttonPushed = False

            time.sleep(0.1)

    def button_state(self, currentState, start_time, button_name):
        self.currentState = currentState

        if self.currentState == "pressed":
            self.start_time = start_time
            self.buttonPushed = True

        elif self.currentState == "released":
            if self.elapsed_time < 0.5:
                print(f"{button_name} was pressed")
                self.buttonPushed = False
            else:
                print(f"{button_name} held for {self.elapsed_time} seconds")


# Thank you to SH for helping me learn how to embed a OpenCV video


class imageMonitor(QtCore.QThread):
    # essentially retrieving the video from the camera using OpenCV and then putting it in a format PyQt can read

    ImageUpdate = QtCore.pyqtSignal(QtGui.QImage)
    mpMesh = mp.solutions.face_mesh
    Mesh = mpMesh.FaceMesh()
    mpDraw = mp.solutions.drawing_utils

    # mouthpoints were found using https://raw.githubusercontent.com/google/mediapipe/a908d668c730da128dfa8d9f6bd25d519d006692/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
    # can also be found using https://github.com/tensorflow/tfjs-models/blob/838611c02f51159afdd77469ce67f0e26b7bbb23/face-landmarks-detection/src/mediapipe-facemesh/keypoints.ts

    mouthPoints = [
        78,
        191,
        80,
        81,
        82,
        13,
        312,
        311,
        310,
        415,
        308,
        324,
        318,
        402,
        317,
        14,
        87,
        178,
        88,
        95,
    ]

    def __init__(self):
        super(imageMonitor, self).__init__()
        print("imageMonitor initialized")

        # Camera detection and initialization
        self.use_realsense = False
        self.rs_camera = None
        self.camera = None
        self.depth_frame = None

        # Try to initialize RealSense first
        if REALSENSE_AVAILABLE:
            try:
                self.rs_camera = RealsenseCamera()
                self.use_realsense = True
                print("Using RealSense camera")
            except Exception as e:
                print(f"RealSense initialization failed: {e}")
                print("Falling back to standard webcam")
                self.camera = cv2.VideoCapture(0)
        else:
            self.camera = cv2.VideoCapture(0)
            print("Using standard webcam")

        # Initialize segmentation model if available
        self.segmentation_model = None
        if SEGMENTATION_AVAILABLE:
            try:
                if SEGMENTATION_MODEL == "yolov12":
                    self.segmentation_model = YOLOv12Seg(
                        model_size="n"
                    )  # 'n'=nano (fastest)
                elif SEGMENTATION_MODEL == "maskrcnn":
                    self.segmentation_model = MaskRCNN()
                print(f"{SEGMENTATION_MODEL} initialized")
            except Exception as e:
                print(f"Segmentation model initialization failed: {e}")

        # Detection mode: 'face' or 'objects'
        self.detection_mode = "objects" if self.segmentation_model else "face"
        print(f"Detection mode: {self.detection_mode}")

    def camera_changed(self, camera_index):
        # Only works with standard webcam, not RealSense
        if not self.use_realsense and self.camera:
            self.camera.release()
            self.camera = cv2.VideoCapture(camera_index)

    def run(self):
        print("imageMonitor is running")
        self.ThreadActive = True

        while self.ThreadActive:
            # Get frame from camera (RealSense or webcam)
            ret = False
            frame = None
            depth_frame = None

            if self.use_realsense and self.rs_camera:
                ret, frame, depth_frame = self.rs_camera.get_frame_stream()
                self.depth_frame = depth_frame
            elif self.camera:
                ret, frame = self.camera.read()

            if ret and frame is not None:
                # Convert to RGB
                Image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Apply detection based on mode
                if self.detection_mode == "objects" and self.segmentation_model:
                    Image = self.object_detection(Image, depth_frame)
                else:
                    Image = self.face_landmarks(Image)

                FlippedImage = cv2.flip(Image, 1)
                ConvertToQtFormat = QtGui.QImage(
                    FlippedImage.data,
                    FlippedImage.shape[1],
                    FlippedImage.shape[0],
                    QtGui.QImage.Format.Format_RGB888,
                )
                Pic = ConvertToQtFormat.scaled(
                    800, 650, QtCore.Qt.AspectRatioMode.KeepAspectRatio
                )
                self.ImageUpdate.emit(Pic)

    def object_detection(self, image, depth_frame=None):
        """Perform object detection with optional depth information"""
        # Get object masks
        boxes, classes, contours, centers = self.segmentation_model.detect_objects_mask(
            image
        )

        # Draw object masks
        image = self.segmentation_model.draw_object_mask(image)

        # Show depth info if available
        if depth_frame is not None:
            self.segmentation_model.draw_object_info(image, depth_frame)

        return image

    def face_landmarks(self, Image):
        results = self.Mesh.process(Image)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # mpDraw.draw_landmarks(img, face_landmarks, mpMesh.FACEMESH_TESSELATION)
                tx = 0
                ty = 0
                for id, lm in enumerate(face_landmarks.landmark):
                    if id in self.mouthPoints:
                        h, w, c = Image.shape
                        px, py = int(lm.x * w), int(lm.y * h)
                        if id in [13, 14]:
                            tx += px
                            ty += py
                        if id == 14:
                            tx = int(tx / 2)
                            ty = int(ty / 2)
                            cv2.circle(Image, (tx, ty), 10, (0, 255, 255), cv2.FILLED)

                        cv2.circle(Image, (px, py), 4, (0, 255, 0), cv2.FILLED)
        return Image


VIDEO_DEVICES = 4

# Big thanks to https://stackoverflow.com/questions/52558617/enumerate-over-cameras-in-python for helping figuring out how to enumrate over cameras
# camera tracker class to get cameras so user can choose which camera to display


class camera_tracker:
    def __init__(self):
        print("camera tracker initialized")
        self.cameras = []

    def get_camera_info(self) -> list:
        self.cameras = []

        camera_indexes = self.get_camera_indexes()

        if len(camera_indexes) == 0:
            return self.cameras

        self.cameras = self.add_camera_information(camera_indexes)

        return self.cameras

    def get_camera_indexes(self):
        index = 0
        camera_indexes = []
        max_numbers_of_cameras_to_check = 3

        # adding all camera indexes to a list
        while max_numbers_of_cameras_to_check > 0:
            capture = cv2.VideoCapture(index)
            if capture.read()[0]:
                camera_indexes.append(index)
                capture.release()
            index += 1
            max_numbers_of_cameras_to_check -= 1

        return camera_indexes

    def add_camera_information(self, camera_indexes: list) -> list:
        platform_name = platform.system()
        cameras = []

        if platform_name == "Windows":
            cameras_info_windows = asyncio.run(
                self.get_camera_information_for_windows()
            )

            for camera_index in camera_indexes:
                if camera_index < len(cameras_info_windows):
                    camera_name = cameras_info_windows.get_at(
                        camera_index
                    ).name.replace("\n", "")
                    cameras.append(
                        {"camera_index": camera_index, "camera_name": camera_name}
                    )
        else:
            # For macOS and Linux, use generic camera names
            for camera_index in camera_indexes:
                camera_name = f"Camera {camera_index}"
                cameras.append(
                    {"camera_index": camera_index, "camera_name": camera_name}
                )

        return cameras

    async def get_camera_information_for_windows(self):
        return await windows_devices.DeviceInformation.find_all_async(VIDEO_DEVICES)


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
