"""
RF-DETR Seg Instance Segmentation Module

State-of-the-art real-time instance segmentation using RF-DETR
(released November 2025 by Roboflow).

Performance: 44.3 mAP@50:95 on COCO (better than YOLO11-X-Seg)
Speed: 170 FPS on T4 GPU, 30+ FPS on Apple Metal
"""

import os

import cv2
import numpy as np
from PIL import Image
from rfdetr import RFDETRSegPreview

from aaa_vision.spatial_smoother import SpatialSmoother


class RFDETRSeg:
    """
    RF-DETR Seg detector for instance segmentation

    Provides real-time instance segmentation with state-of-the-art accuracy
    (44.3 mAP on COCO, November 2025 release).
    """

    def __init__(self, confidence_threshold=0.25, use_tta=True, enable_smoothing=True):
        """
        Initialize RF-DETR Seg model

        Args:
            confidence_threshold: Minimum confidence for detections (default 0.25)
                                 Optimized for stationary home assistant objects
                                 Lower threshold catches marginal detections, reducing flicker
                                 Tracking layer filters false positives with multi-frame consensus
            use_tta: Enable test-time augmentation for improved consistency (default True)
                    Runs inference on original + flipped image, keeps consistent detections
                    Reduces false positives at cost of ~2x inference time
            enable_smoothing: Enable morphological smoothing of segmentation masks (default True)
                             Smooths jagged boundaries by 40-60% with 2-3ms overhead
        """
        self.confidence_threshold = confidence_threshold
        self.use_tta = use_tta

        print("[RF-DETR] Loading model...")

        # Initialize spatial smoother for mask boundary refinement
        # Load config from app_config if available
        try:
            from aaa_core.config.settings import app_config
            self.spatial_smoother = SpatialSmoother(
                enabled=enable_smoothing and app_config.spatial_smoothing_enabled,
                kernel_shape=app_config.spatial_smoothing_kernel_shape,
                small_object_kernel=app_config.spatial_smoothing_small_kernel,
                medium_object_kernel=app_config.spatial_smoothing_medium_kernel,
                large_object_kernel=app_config.spatial_smoothing_large_kernel,
                iterations=app_config.spatial_smoothing_iterations
            )
        except ImportError:
            # Fallback to defaults if config not available
            self.spatial_smoother = SpatialSmoother(enabled=enable_smoothing)

        try:
            # Find project root and models directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(__file__))
            )))
            models_dir = os.path.join(project_root, "data", "models")
            os.makedirs(models_dir, exist_ok=True)

            # RF-DETR downloads model to current directory with fixed name
            model_filename = "rf-detr-seg-preview.pt"
            target_path = os.path.join(models_dir, model_filename)

            # Change to models directory so RF-DETR downloads there
            original_cwd = os.getcwd()
            os.chdir(models_dir)

            try:
                # Load RF-DETR Seg model (Preview version)
                # Model auto-detects device (MPS/CUDA/CPU)
                self.model = RFDETRSegPreview()

                # NOTE: Do NOT call optimize_for_inference() - it breaks mask output!
                # The optimization removes segmentation masks from the Detections object.
                # Trade-off: Slightly slower inference but working segmentation masks.

            finally:
                # Restore original working directory
                os.chdir(original_cwd)

            print("[RF-DETR] Model loaded successfully ✅")
            print(f"[RF-DETR] Model location: {target_path}")

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
        if not self.use_tta:
            # Standard inference (fast)
            return self._detect_single(frame)

        # Test-time augmentation: detect on original + flipped, merge results
        img_height, img_width = frame.shape[:2]

        # Detect on original image
        boxes_orig, classes_orig, contours_orig, centers_orig = self._detect_single(frame)

        # Detect on horizontally flipped image
        frame_flipped = cv2.flip(frame, 1)  # 1 = horizontal flip
        boxes_flip, classes_flip, contours_flip, centers_flip = self._detect_single(frame_flipped)

        # Unflip the detections from flipped image
        boxes_flip_unflipped = []
        contours_flip_unflipped = []
        centers_flip_unflipped = []

        for box, contour, center in zip(boxes_flip, contours_flip, centers_flip):
            x, y, w, h = box
            # Flip bbox: new_x = img_width - (x + w)
            x_unflip = img_width - (x + w)
            boxes_flip_unflipped.append([x_unflip, y, w, h])

            # Flip contour points
            contour_unflip = contour.copy()
            contour_unflip[:, :, 0] = img_width - contour_unflip[:, :, 0]
            contours_flip_unflipped.append(contour_unflip)

            # Flip center
            cx, cy = center
            cx_unflip = img_width - cx
            centers_flip_unflipped.append((cx_unflip, cy))

        # Merge: keep only detections that appear in BOTH views
        merged_boxes = []
        merged_classes = []
        merged_contours = []
        merged_centers = []

        for i, (box_orig, class_orig, contour_orig, center_orig) in enumerate(
            zip(boxes_orig, classes_orig, contours_orig, centers_orig)
        ):
            # Find matching detection in flipped results
            best_iou = 0
            best_match_idx = None

            for j, (box_flip, class_flip) in enumerate(zip(boxes_flip_unflipped, classes_flip)):
                if class_flip != class_orig:
                    continue

                iou = self._calculate_iou_xywh(box_orig, box_flip)
                if iou > best_iou:
                    best_iou = iou
                    best_match_idx = j

            # If IoU > 0.5, object detected in both views (high confidence it's real)
            if best_iou > 0.5:
                merged_boxes.append(box_orig)
                merged_classes.append(class_orig)
                merged_contours.append(contour_orig)
                merged_centers.append(center_orig)

        return merged_boxes, merged_classes, merged_contours, merged_centers

    def _detect_single(self, frame):
        """Run detection on a single image (helper for TTA)"""
        # Convert BGR to RGB and to PIL Image
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        # Run inference
        detections = self.model.predict(
            pil_image,
            threshold=self.confidence_threshold
        )

        boxes = []
        classes = []
        contours = []
        centers = []

        # Process results
        if detections is not None:
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

                        # Convert boolean or float mask to uint8
                        if mask.dtype == bool:
                            mask_uint8 = (mask.astype(np.uint8) * 255)
                        else:
                            mask_uint8 = (mask * 255).astype(np.uint8)

                        # Apply spatial smoothing to refine boundaries
                        # Runs in 2-3ms on CPU, smooths boundaries by 40-60%
                        image_shape = frame.shape[:2]
                        mask_uint8 = self.spatial_smoother.smooth_mask(
                            mask_uint8,
                            image_shape=image_shape
                        )

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

    def _calculate_iou_xywh(self, box1, box2):
        """Calculate IoU for boxes in [x, y, w, h] format"""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        # Convert to xyxy
        x1_max, y1_max = x1 + w1, y1 + h1
        x2_max, y2_max = x2 + w2, y2 + h2

        # Intersection
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1_max, x2_max)
        yi2 = min(y1_max, y2_max)

        if xi2 < xi1 or yi2 < yi1:
            return 0.0

        intersection = (xi2 - xi1) * (yi2 - yi1)

        # Union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def draw_object_mask(self, frame, boxes=None, classes=None, contours=None, return_colors=False, selected_indices=None):
        """
        Draw segmentation masks on frame

        Args:
            frame: Input BGR image
            boxes: List of bounding boxes (optional, will auto-detect if None)
            classes: List of class names (optional)
            contours: List of segmentation contours (optional)
            return_colors: If True, return (frame, colors) tuple instead of just frame
            selected_indices: List of indices to draw (optional, None = draw all)

        Returns:
            frame: Frame with masks drawn (or tuple of (frame, colors) if return_colors=True)
        """
        # If no boxes provided, run detection
        if boxes is None:
            boxes, classes, contours, _ = self.detect_objects_mask(frame)

        # Create overlay for masks
        overlay = frame.copy()

        # Generate consistent colors based on class name hash
        # This ensures same object class gets same color across frames
        colors = []
        for class_name in classes:
            # Hash class name to get consistent color
            hash_val = hash(class_name)
            np.random.seed(hash_val % (2**32))
            color = (
                np.random.randint(50, 255),
                np.random.randint(50, 255),
                np.random.randint(50, 255)
            )
            colors.append(color)

        # Draw masks (only for selected indices if specified)
        for i, contour in enumerate(contours):
            if selected_indices is not None and i not in selected_indices:
                continue
            if i < len(colors):
                cv2.fillPoly(overlay, [contour], colors[i])

        # Blend overlay with original frame
        alpha = 0.4
        frame = cv2.addWeighted(frame, 1 - alpha, overlay, alpha, 0)

        # Draw contours (only for selected indices if specified)
        for i, contour in enumerate(contours):
            if selected_indices is not None and i not in selected_indices:
                continue
            if i < len(colors):
                cv2.drawContours(frame, [contour], -1, colors[i], 2)

        if return_colors:
            return frame, colors
        return frame

    def _repel_labels(self, labels_info, img_width, img_height, iterations=50):
        """
        Adjust label positions to avoid overlaps using force-directed algorithm
        Similar to R's ggrepel package

        Args:
            labels_info: List of dicts with keys: 'text', 'cx', 'cy', 'x', 'y', 'w', 'h'
            img_width: Image width for boundary constraints
            img_height: Image height for boundary constraints
            iterations: Number of repulsion iterations (default 50)

        Returns:
            List of adjusted label info dicts
        """
        print(f"[REPEL] Called with {len(labels_info)} labels")
        if len(labels_info) <= 1:
            print(f"[REPEL] Skipping - only {len(labels_info)} label(s)")
            return labels_info

        # Copy to avoid modifying original
        labels = [label.copy() for label in labels_info]

        # Force-directed layout algorithm
        for iteration in range(iterations):
            # Calculate forces for each label
            forces = [{'x': 0, 'y': 0} for _ in labels]

            # 1. Repulsion forces between overlapping labels
            for i, label1 in enumerate(labels):
                for j in range(i + 1, len(labels)):
                    label2 = labels[j]

                    # Calculate bounding boxes with padding
                    padding = 8
                    l1_x1 = label1['x'] - padding
                    l1_y1 = label1['y'] - label1['h'] - padding
                    l1_x2 = label1['x'] + label1['w'] + padding
                    l1_y2 = label1['y'] + padding

                    l2_x1 = label2['x'] - padding
                    l2_y1 = label2['y'] - label2['h'] - padding
                    l2_x2 = label2['x'] + label2['w'] + padding
                    l2_y2 = label2['y'] + padding

                    # Check rectangle overlap
                    overlap = not (l1_x2 < l2_x1 or l2_x2 < l1_x1 or
                                  l1_y2 < l2_y1 or l2_y2 < l1_y1)

                    if overlap:
                        # Calculate center of each label
                        l1_cx = label1['x'] + label1['w'] / 2
                        l1_cy = label1['y'] - label1['h'] / 2
                        l2_cx = label2['x'] + label2['w'] / 2
                        l2_cy = label2['y'] - label2['h'] / 2

                        # Repulsion vector
                        dx = l2_cx - l1_cx
                        dy = l2_cy - l1_cy
                        dist = np.sqrt(dx**2 + dy**2)

                        if dist < 1:
                            # Same position - push apart arbitrarily
                            dx, dy = 20, 10
                            dist = np.sqrt(dx**2 + dy**2)

                        # Stronger repulsion for overlapping labels
                        repulsion_strength = 15.0
                        force_x = (dx / dist) * repulsion_strength
                        force_y = (dy / dist) * repulsion_strength

                        # Apply equal and opposite forces
                        forces[i]['x'] -= force_x
                        forces[i]['y'] -= force_y
                        forces[j]['x'] += force_x
                        forces[j]['y'] += force_y

            # 2. Spring forces toward anchor points (object centers)
            spring_strength = 0.15  # Gentle pull toward original position
            for i, label in enumerate(labels):
                desired_x = label['cx'] - label['w'] // 2
                desired_y = label['cy'] - 15

                forces[i]['x'] += (desired_x - label['x']) * spring_strength
                forces[i]['y'] += (desired_y - label['y']) * spring_strength

            # 3. Apply forces with damping
            damping = 0.8  # Prevents oscillation
            for i, label in enumerate(labels):
                label['x'] += forces[i]['x'] * damping
                label['y'] += forces[i]['y'] * damping

                # Keep labels within image bounds
                label['x'] = max(10, min(label['x'], img_width - label['w'] - 10))
                label['y'] = max(label['h'] + 10, min(label['y'], img_height - 10))

        return labels

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
        Labels are automatically repositioned to avoid overlaps (similar to ggrepel)

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

        if not boxes:
            return frame

        img_height, img_width = frame.shape[:2]

        # First pass: calculate label sizes and initial positions
        labels_info = []
        for i, (box, class_name, center) in enumerate(
            zip(boxes, classes, centers)
        ):
            x, y, w, h = box
            cx, cy = center

            # Prepare label text
            label = class_name

            # Add depth if available
            if depth_frame is not None:
                h_depth, w_depth = depth_frame.shape[:2]
                if 0 <= cy < h_depth and 0 <= cx < w_depth:
                    depth = depth_frame[cy, cx]
                    if depth > 0:
                        label += f" {depth}mm"

            # Calculate label size
            (label_w, label_h), baseline = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                2
            )

            # Initial position (centered above center point)
            label_x = cx - label_w // 2
            label_y = cy - 15

            labels_info.append({
                'text': label,
                'cx': cx,
                'cy': cy,
                'x': label_x,
                'y': label_y,
                'w': label_w,
                'h': label_h
            })

        # Apply repulsion algorithm to avoid overlaps
        labels_info = self._repel_labels(labels_info, img_width, img_height)

        # Second pass: draw center points, crosshairs, and adjusted labels
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

            # Get adjusted label position
            label_info = labels_info[i]
            label_x = int(label_info['x'])
            label_y = int(label_info['y'])
            label_w = label_info['w']
            label_h = label_info['h']
            label = label_info['text']

            # Draw line from center to label (if label was moved significantly)
            label_center_x = label_x + label_w // 2
            label_center_y = label_y - label_h // 2
            distance_from_anchor = np.sqrt((label_center_x - cx)**2 + (label_center_y - cy)**2)

            if distance_from_anchor > 25:
                # Draw connector line
                cv2.line(
                    frame,
                    (cx, cy),
                    (label_center_x, label_center_y),
                    (255, 255, 0),  # Cyan line
                    1,
                    cv2.LINE_AA
                )

            # Draw label background (semi-transparent black)
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
