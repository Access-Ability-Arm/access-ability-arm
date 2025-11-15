"""
YOLOv11 Instance Segmentation Wrapper
Provides interface compatible with mask_rcnn.py for easy drop-in replacement
"""

import os
import sys
import warnings
from contextlib import contextmanager

import cv2
import numpy as np

# Suppress TensorFlow Lite warnings at the C++ level
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TF logs (INFO, WARNING, ERROR)
os.environ['GLOG_minloglevel'] = '3'  # Suppress GLOG (Google Logging)
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf')

@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output (for C++ level warnings)"""
    stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        sys.stderr = stderr

from ultralytics import YOLO


class YOLOv11Seg:
    def __init__(self, model_size="n"):
        """
        Initialize YOLOv11 segmentation model

        Args:
            model_size: Model size - 'n' (nano), 's' (small), 'm' (medium), 'l' (large), 'x' (xlarge)
                       Nano is fastest, XLarge is most accurate
        """
        print(f"Loading YOLOv11-{model_size}-seg model...")

        # Detect available device (MPS for Apple Silicon, CUDA for NVIDIA, CPU fallback)
        import torch

        if torch.backends.mps.is_available():
            self.device = "mps"
            print("YOLOv11: Using Apple Metal (MPS) for GPU acceleration")
        elif torch.cuda.is_available():
            self.device = "cuda"
            print("YOLOv11: Using NVIDIA CUDA for GPU acceleration")
        else:
            self.device = "cpu"
            print("YOLOv11: Using CPU (no GPU acceleration available)")

        # Load YOLOv11 segmentation model from models/ directory
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        local_model = os.path.join(models_dir, f"yolo11{model_size}-seg.pt")

        # Suppress verbose output and C++ warnings during model loading
        import logging
        logging.getLogger("ultralytics").setLevel(logging.WARNING)

        with suppress_stderr():
            if os.path.exists(local_model):
                self.model = YOLO(local_model, verbose=False)
            else:
                # Auto-download if not found locally
                # YOLO downloads to current directory, so we need to move it
                model_name = f"yolo11{model_size}-seg.pt"
                print(f"Downloading {model_name}...")
                self.model = YOLO(model_name, verbose=False)

                # Move downloaded model to models/ directory for future use
                if os.path.exists(model_name) and not os.path.exists(local_model):
                    import shutil
                    shutil.move(model_name, local_model)
                    print(f"Moved {model_name} to models/ directory")
                    # Reload from correct location
                    self.model = YOLO(local_model, verbose=False)

        print(f"✓ YOLOv11-{model_size}-seg ready")

        # Detection confidence threshold
        self.detection_threshold = 0.5

        # Generate random colors for visualization (80 COCO classes)
        np.random.seed(42)
        self.colors = np.random.randint(0, 255, (80, 3))

        # COCO class names
        self.classes = [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ]

        # Storage for detection results
        self.obj_boxes = []
        self.obj_classes = []
        self.obj_confidences = []
        self.obj_centers = []
        self.obj_contours = []
        self.obj_masks = []

        # Confidence smoothing - store history per track ID
        self.confidence_history = {}  # {track_id: smoothed_confidence}
        self.smoothing_alpha = 0.05  # Weight for new confidence (0.0 = ignore new, 1.0 = no smoothing)
                                      # 0.05 = 5% new, 95% historical (effective window ~20-40 frames)

        # Spatial smoothing - store previous positions per track ID
        self.position_history = {}  # {track_id: (prev_x, prev_y)}
        self.position_alpha = 0.2  # Weight for new position (higher than confidence for responsiveness)

    def detect_objects_mask(self, bgr_frame):
        """
        Detect objects and generate segmentation masks

        Args:
            bgr_frame: Input BGR image from camera

        Returns:
            boxes: List of [x1, y1, x2, y2] bounding boxes
            classes: List of class IDs
            contours: List of contours for each detection
            centers: List of (cx, cy) center points
        """
        # Run inference with tracking for smoother video segmentation
        # Tracker reduces jitter and provides more stable bounding boxes/masks
        # YOLO requires dimensions divisible by 32 (stride requirement)
        #
        # imgsz recommendations (Ultralytics official):
        # - 640: Default, optimal for real-time webcam segmentation (recommended)
        # - 1280: 2x size, better coverage but slower (~4x more pixels)
        # - 1920: Full HD, best coverage but very slow, may cause detection issues
        #
        # References:
        # - https://docs.ultralytics.com/tasks/segment/
        # - https://docs.ultralytics.com/models/yolo11/
        results = self.model.track(
            bgr_frame,
            conf=self.detection_threshold,
            iou=0.5,  # IoU threshold for NMS - higher values merge overlapping detections
            verbose=False,
            device=self.device,
            persist=True,  # Persist tracks between frames
            tracker="bytetrack.yaml",  # Use ByteTrack for smooth tracking
            imgsz=640,  # Ultralytics recommended default for real-time segmentation
        )

        # Clear previous results
        self.obj_boxes = []
        self.obj_classes = []
        self.obj_confidences = []
        self.obj_centers = []
        self.obj_contours = []
        self.obj_masks = []

        # Process results
        if len(results) > 0 and results[0].masks is not None:
            result = results[0]
            boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
            classes = result.boxes.cls.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            masks = result.masks.data.cpu().numpy()  # Segmentation masks

            # Get track IDs if available (ByteTrack provides these)
            track_ids = None
            if result.boxes.id is not None:
                track_ids = result.boxes.id.cpu().numpy()

            # Process each detection
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i].astype(int)
                class_id = int(classes[i])
                raw_confidence = float(confidences[i])

                # Apply temporal smoothing to confidence score
                track_id = int(track_ids[i]) if track_ids is not None else None

                if track_id is not None:
                    # Use exponential moving average for smoothing
                    if track_id in self.confidence_history:
                        # Smooth: new = alpha * current + (1-alpha) * previous
                        confidence = (self.smoothing_alpha * raw_confidence +
                                    (1 - self.smoothing_alpha) * self.confidence_history[track_id])
                    else:
                        # First time seeing this track, use raw confidence
                        confidence = raw_confidence

                    # Update history
                    self.confidence_history[track_id] = confidence
                else:
                    # No track ID, use raw confidence
                    confidence = raw_confidence

                # Store box
                self.obj_boxes.append([x1, y1, x2, y2])

                # Store class and confidence
                self.obj_classes.append(class_id)
                self.obj_confidences.append(confidence)

                # Calculate center
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                self.obj_centers.append((cx, cy))

                # Get mask and convert to contours
                mask = masks[i]
                # Resize mask to original image size
                mask_resized = cv2.resize(
                    mask, (bgr_frame.shape[1], bgr_frame.shape[0])
                )
                mask_uint8 = (mask_resized * 255).astype(np.uint8)

                # Apply morphological operations for better continuity and temporal stability
                # Larger kernel (9x9) provides stronger smoothing and better temporal consistency
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
                mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
                mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)

                # Apply stronger Gaussian blur for smoother edges and reduced jitter
                mask_uint8 = cv2.GaussianBlur(mask_uint8, (7, 7), 0)

                # Re-threshold after blur
                _, mask_uint8 = cv2.threshold(mask_uint8, 127, 255, cv2.THRESH_BINARY)

                # Find contours
                contours, _ = cv2.findContours(
                    mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                # Keep only contours with significant area (filter noise)
                min_area = 100  # Minimum 100 pixels
                contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]

                self.obj_contours.append(contours)

                # Convert back to normalized mask for drawing
                mask_resized = mask_uint8.astype(float) / 255.0
                self.obj_masks.append(mask_resized)

        return self.obj_boxes, self.obj_classes, self.obj_contours, self.obj_centers

    def draw_object_mask(self, bgr_frame):
        """
        Draw colored segmentation masks on the frame

        Args:
            bgr_frame: Input BGR image

        Returns:
            bgr_frame: Image with masks drawn
        """
        # Draw masks with transparency
        for mask, class_id in zip(self.obj_masks, self.obj_classes):
            color = self.colors[class_id % len(self.colors)]

            # Create colored mask
            colored_mask = np.zeros_like(bgr_frame)
            mask_bool = mask > 0.5
            colored_mask[mask_bool] = color

            # Blend with original image
            alpha = 0.4
            bgr_frame = cv2.addWeighted(bgr_frame, 1, colored_mask, alpha, 0)

        # Draw contours
        for contours, class_id in zip(self.obj_contours, self.obj_classes):
            color = self.colors[class_id % len(self.colors)]
            color = (int(color[0]), int(color[1]), int(color[2]))
            cv2.drawContours(bgr_frame, contours, -1, color, 2)

        return bgr_frame

    def draw_object_info(self, bgr_frame, depth_frame=None):
        """
        Draw bounding boxes, labels, and depth information

        Args:
            bgr_frame: Input BGR image
            depth_frame: Optional depth frame for distance measurement

        Returns:
            bgr_frame: Image with info drawn
        """
        # Need to get track IDs again for spatial smoothing
        # Re-run detection to get current track IDs (lightweight, just box access)
        results = self.model.track(
            bgr_frame,
            conf=self.detection_threshold,
            iou=0.5,  # IoU threshold for NMS
            verbose=False,
            device=self.device,
            persist=True,
            tracker="bytetrack.yaml",
            imgsz=640,  # Match detection size
        )

        track_ids = None
        if len(results) > 0 and results[0].boxes.id is not None:
            track_ids = results[0].boxes.id.cpu().numpy()

        for idx, (box, class_id, confidence, center, contours, mask) in enumerate(zip(
            self.obj_boxes, self.obj_classes, self.obj_confidences, self.obj_centers, self.obj_contours, self.obj_masks
        )):
            x1, y1, x2, y2 = box
            cx, cy = center

            # Get color
            color = self.colors[class_id % len(self.colors)]
            color = (int(color[0]), int(color[1]), int(color[2]))

            # Get class name
            class_name = (
                self.classes[class_id]
                if class_id < len(self.classes)
                else f"Class {class_id}"
            )

            # Calculate dynamic label size based on text content
            h, w = bgr_frame.shape[:2]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.9  # Increased from 0.6 for better legibility
            font_thickness = 2
            padding = 12  # Slightly more padding for larger text

            # Build label text
            label_text = f"{class_name.capitalize()} {confidence*100:.0f}%"
            (text_width, text_height), baseline = cv2.getTextSize(
                label_text, font, font_scale, font_thickness
            )

            # Calculate label dimensions with padding
            label_width = text_width + padding * 2
            label_height = text_height + baseline + padding * 2

            # Add extra height for depth text if available
            if depth_frame is not None:
                depth_text = "999.9 cm"  # Max width estimate
                (depth_width, depth_height), _ = cv2.getTextSize(
                    depth_text, font, 0.7, font_thickness
                )
                label_height += depth_height + padding
                label_width = max(label_width, depth_width + padding * 2)

            # Find actual mask pixels for better label positioning
            # This ensures label is near actual object, not just bounding box
            mask_bool = mask > 0.5
            mask_y, mask_x = np.where(mask_bool)

            if len(mask_y) > 0:
                # Find top center of actual mask pixels
                # Use median X for stability, min Y for top placement
                raw_top_y = int(np.min(mask_y))
                raw_center_x = int(np.median(mask_x))

                # Apply spatial smoothing for temporal stability (reduces label jitter)
                track_id = int(track_ids[idx]) if track_ids is not None and idx < len(track_ids) else None

                if track_id is not None and track_id in self.position_history:
                    # Smooth position using exponential moving average
                    prev_x, prev_y = self.position_history[track_id]
                    center_x = int(self.position_alpha * raw_center_x + (1 - self.position_alpha) * prev_x)
                    top_y = int(self.position_alpha * raw_top_y + (1 - self.position_alpha) * prev_y)
                else:
                    # First frame or no track ID, use raw position
                    center_x = raw_center_x
                    top_y = raw_top_y

                # Update position history
                if track_id is not None:
                    self.position_history[track_id] = (center_x, top_y)

                # Position label slightly below and centered on top of mask
                label_x = center_x - label_width // 2
                label_y = top_y + 10  # 10 pixels below top of mask
            else:
                # Fallback to bounding box if mask is empty
                label_x = x1 + (x2 - x1) // 2 - label_width // 2
                label_y = y1 + 10

            # Final screen bounds check
            label_x = max(10, min(label_x, w - label_width - 10))
            label_y = max(10, min(label_y, h - label_height - 10))

            # Draw label background
            cv2.rectangle(
                bgr_frame,
                (label_x, label_y),
                (label_x + label_width, label_y + label_height),
                color,
                -1
            )

            # Draw class name with confidence
            cv2.putText(
                bgr_frame,
                label_text,
                (label_x + padding, label_y + text_height + padding),
                font,
                font_scale,
                (255, 255, 255),
                font_thickness,
            )

            # Draw depth if available
            if depth_frame is not None:
                try:
                    depth_mm = depth_frame[cy, cx]
                    depth_text = f"{depth_mm / 10:.1f} cm"
                    cv2.putText(
                        bgr_frame,
                        depth_text,
                        (label_x + padding, label_y + text_height + depth_height + padding * 2),
                        font,
                        0.7,
                        (255, 255, 255),
                        font_thickness,
                    )
                except:
                    pass

        return bgr_frame
