"""Video Display & Labels mixin for MainWindow."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from .main_window import FletMainWindow


class VideoDisplayMixin:
    """Mixin providing video feed display and label rendering methods."""

    def _update_video_feed(self: FletMainWindow, img_array):
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
                    self._populate_object_cards()
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
        self: FletMainWindow,
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
        self: FletMainWindow, centers, classes, img_shape, font_size=42, padding=12
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

    def _enhance_frozen_labels(self: FletMainWindow, img_array):
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

        # Use CARD_COLORS_BGR so camera masks match the card badge colors
        from . import _design_tokens as T

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
            colors=T.CARD_COLORS_BGR,
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
