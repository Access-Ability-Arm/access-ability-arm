"""
YOLOv12 Instance Segmentation Wrapper
Provides interface compatible with mask_rcnn.py for easy drop-in replacement
"""

import cv2
import numpy as np
from ultralytics import YOLO


class YOLOv12Seg:
    def __init__(self, model_size="n"):
        """
        Initialize YOLOv12 segmentation model

        Args:
            model_size: Model size - 'n' (nano), 's' (small), 'm' (medium), 'l' (large), 'x' (xlarge)
                       Nano is fastest, XLarge is most accurate
        """
        print(f"Loading YOLOv12-{model_size}-seg model...")

        # Detect available device (MPS for Apple Silicon, CUDA for NVIDIA, CPU fallback)
        import torch

        if torch.backends.mps.is_available():
            self.device = "mps"
            print("YOLOv12: Using Apple Metal (MPS) for GPU acceleration")
        elif torch.cuda.is_available():
            self.device = "cuda"
            print("YOLOv12: Using NVIDIA CUDA for GPU acceleration")
        else:
            self.device = "cpu"
            print("YOLOv12: Using CPU (no GPU acceleration available)")

        # Load YOLOv12 segmentation model (will auto-download on first use)
        model_name = f"yolo12{model_size}-seg.pt"
        try:
            self.model = YOLO(model_name)
            print(f"YOLOv12-{model_size}-seg loaded successfully")
        except Exception as e:
            print(f"Error loading {model_name}: {e}")
            print("Falling back to YOLOv11n-seg...")
            self.model = YOLO("yolo11n-seg.pt")

        # Detection confidence threshold
        self.detection_threshold = 0.5  # Higher than Mask R-CNN's 0.7 for better recall

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
        self.obj_centers = []
        self.obj_contours = []
        self.obj_masks = []

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
        # Run inference
        results = self.model.predict(
            bgr_frame,
            conf=self.detection_threshold,
            verbose=False,
            device=self.device,  # Auto-detected: 'mps' for Apple Silicon, 'cuda' for NVIDIA, 'cpu' fallback
        )

        # Clear previous results
        self.obj_boxes = []
        self.obj_classes = []
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

            # Process each detection
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i].astype(int)
                class_id = int(classes[i])

                # Store box
                self.obj_boxes.append([x1, y1, x2, y2])

                # Store class
                self.obj_classes.append(class_id)

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

                # Find contours
                contours, _ = cv2.findContours(
                    mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                self.obj_contours.append(contours)
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
        for box, class_id, center in zip(
            self.obj_boxes, self.obj_classes, self.obj_centers
        ):
            x1, y1, x2, y2 = box
            cx, cy = center

            # Get color
            color = self.colors[class_id % len(self.colors)]
            color = (int(color[0]), int(color[1]), int(color[2]))

            # Draw crosshairs at center
            cv2.line(bgr_frame, (cx, y1), (cx, y2), color, 1)
            cv2.line(bgr_frame, (x1, cy), (x2, cy), color, 1)

            # Draw bounding box
            cv2.rectangle(bgr_frame, (x1, y1), (x2, y2), color, 2)

            # Get class name
            class_name = (
                self.classes[class_id]
                if class_id < len(self.classes)
                else f"Class {class_id}"
            )

            # Draw label background
            label_height = 60 if depth_frame is not None else 30
            cv2.rectangle(bgr_frame, (x1, y1), (x1 + 200, y1 + label_height), color, -1)

            # Draw class name
            cv2.putText(
                bgr_frame,
                class_name.capitalize(),
                (x1 + 5, y1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            # Draw depth if available
            if depth_frame is not None:
                try:
                    depth_mm = depth_frame[cy, cx]
                    cv2.putText(
                        bgr_frame,
                        f"{depth_mm / 10:.1f} cm",
                        (x1 + 5, y1 + 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2,
                    )
                except:
                    pass

        return bgr_frame
