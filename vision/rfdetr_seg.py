"""
RF-DETR Seg Instance Segmentation Module

State-of-the-art real-time instance segmentation using RF-DETR
(released November 2025 by Roboflow).

Performance: 44.3 mAP@50:95 on COCO (better than YOLO11-X-Seg)
Speed: 170 FPS on T4 GPU, 30+ FPS on Apple Metal
"""

import cv2
import numpy as np
from PIL import Image
from rfdetr import RFDETRSegPreview


class RFDETRSeg:
    """
    RF-DETR Seg detector for instance segmentation

    Provides real-time instance segmentation with state-of-the-art accuracy
    (44.3 mAP on COCO, November 2025 release).
    """

    def __init__(self, confidence_threshold=0.5):
        """
        Initialize RF-DETR Seg model

        Args:
            confidence_threshold: Minimum confidence for detections (default 0.5)
        """
        self.confidence_threshold = confidence_threshold

        print("[RF-DETR] Loading model...")

        try:
            # Load RF-DETR Seg model (Preview version)
            # Model auto-detects device (MPS/CUDA/CPU)
            self.model = RFDETRSegPreview()

            # Optimize model for inference (reduces latency)
            print("[RF-DETR] Optimizing model for inference...")
            self.model.optimize_for_inference()
            print("[RF-DETR] Model loaded and optimized ✅")

        except Exception as e:
            print(f"[RF-DETR] Error loading model: {e}")
            raise

        # COCO class names (RF-DETR uses 1-indexed class IDs)
        # Model has built-in class_names dict: {1: 'person', 2: 'bicycle', ...}
        # We'll use the model's class_names directly
        self.class_names = self.model.class_names

    def detect_objects_mask(self, frame, depth_frame=None):
        """
        Detect objects with instance segmentation

        Args:
            frame: Input BGR image (numpy array)
            depth_frame: Optional depth frame (not used, for compatibility)

        Returns:
            tuple: (boxes, classes, contours, centers)
                - boxes: List of [x, y, w, h] bounding boxes
                - classes: List of class names
                - contours: List of segmentation contours
                - centers: List of (cx, cy) center points
        """
        # Convert BGR to RGB and to PIL Image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        # Run inference (returns list of Detections for each image)
        detections_list = self.model.predict(
            [pil_image],
            threshold=self.confidence_threshold
        )

        boxes = []
        classes = []
        contours = []
        centers = []

        # Process results (first image in batch)
        if detections_list and len(detections_list) > 0:
            detections = detections_list[0]

            # Supervision Detections object has: xyxy, class_id, confidence, mask
            if hasattr(detections, 'xyxy') and detections.xyxy is not None:
                num_detections = len(detections.xyxy)

                for i in range(num_detections):
                    # Get bbox (xyxy format)
                    x1, y1, x2, y2 = detections.xyxy[i]
                    x, y, w, h = int(x1), int(y1), int(x2-x1), int(y2-y1)
                    boxes.append([x, y, w, h])

                    # Get class (RF-DETR uses 1-indexed class IDs)
                    class_id = int(detections.class_id[i])
                    class_name = self.class_names.get(
                        class_id, f"class_{class_id}"
                    )
                    classes.append(class_name)

                    # Get segmentation mask and convert to contour
                    if hasattr(detections, 'mask') and detections.mask is not None:
                        mask = detections.mask[i]
                        # Find contours from mask
                        mask_uint8 = (mask * 255).astype(np.uint8)
                        contour_list, _ = cv2.findContours(
                            mask_uint8,
                            cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE
                        )
                        if contour_list:
                            # Use largest contour
                            largest_contour = max(
                                contour_list,
                                key=cv2.contourArea
                            )
                            contours.append(largest_contour)
                        else:
                            # Fallback: bbox as contour
                            contours.append(np.array([
                                [[x, y]], [[x+w, y]], [[x+w, y+h]], [[x, y+h]]
                            ]))
                    else:
                        # No mask available, use bbox as contour
                        contours.append(np.array([
                            [[x, y]], [[x+w, y]], [[x+w, y+h]], [[x, y+h]]
                        ]))

                    # Calculate center
                    cx = x + w // 2
                    cy = y + h // 2
                    centers.append((cx, cy))

        return boxes, classes, contours, centers

    def draw_object_mask(self, frame, boxes=None, classes=None, contours=None):
        """
        Draw segmentation masks on frame

        Args:
            frame: Input BGR image
            boxes: List of bounding boxes (optional, will auto-detect if None)
            classes: List of class names (optional)
            contours: List of segmentation contours (optional)

        Returns:
            frame: Frame with masks drawn
        """
        # If no boxes provided, run detection
        if boxes is None:
            boxes, classes, contours, _ = self.detect_objects_mask(frame)

        # Create overlay for masks
        overlay = frame.copy()

        # Generate colors for each object
        num_objects = len(boxes)
        colors = [
            (
                np.random.randint(50, 255),
                np.random.randint(50, 255),
                np.random.randint(50, 255)
            )
            for _ in range(num_objects)
        ]

        # Draw masks
        for i, contour in enumerate(contours):
            if i < len(colors):
                cv2.fillPoly(overlay, [contour], colors[i])

        # Blend overlay with original frame
        alpha = 0.4
        frame = cv2.addWeighted(frame, 1 - alpha, overlay, alpha, 0)

        # Draw contours
        for i, contour in enumerate(contours):
            if i < len(colors):
                cv2.drawContours(frame, [contour], -1, colors[i], 2)

        return frame

    def draw_object_info(
        self,
        frame,
        boxes=None,
        classes=None,
        centers=None,
        depth_frame=None
    ):
        """
        Draw labels and depth information (no bounding boxes)

        Args:
            frame: Input BGR image
            boxes: List of bounding boxes (optional, will auto-detect if None)
            classes: List of class names (optional)
            centers: List of center points (optional)
            depth_frame: Optional depth frame for distance measurement

        Returns:
            frame: Frame with labels drawn
        """
        # If no boxes provided, run detection
        if boxes is None:
            boxes, classes, _, centers = self.detect_objects_mask(frame)

        for i, (box, class_name, center) in enumerate(
            zip(boxes, classes, centers)
        ):
            x, y, w, h = box
            cx, cy = center

            # Draw center point and crosshair
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.drawMarker(
                frame,
                (cx, cy),
                (0, 255, 255),
                cv2.MARKER_CROSS,
                20,
                2
            )

            # Prepare label
            label = class_name

            # Add depth if available
            if depth_frame is not None:
                h_depth, w_depth = depth_frame.shape[:2]
                if 0 <= cy < h_depth and 0 <= cx < w_depth:
                    depth = depth_frame[cy, cx]
                    if depth > 0:
                        label += f" {depth}mm"

            # Draw label background (semi-transparent black)
            (label_w, label_h), baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                2
            )
            # Position label near center point
            label_x = cx - label_w // 2
            label_y = cy - 15
            cv2.rectangle(
                frame,
                (label_x - 5, label_y - label_h - 5),
                (label_x + label_w + 5, label_y + 5),
                (0, 0, 0),
                -1
            )

            # Draw label text in white
            cv2.putText(
                frame,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        return frame
