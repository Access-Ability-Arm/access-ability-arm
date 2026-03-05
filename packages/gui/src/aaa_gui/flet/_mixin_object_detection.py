"""Object detection, selection, and analysis mixin for MainWindow."""

import logging
import threading
import time

import cv2
import numpy as np
import flet as ft

logger = logging.getLogger(__name__)


class ObjectDetectionMixin:
    """Methods for object detection UI, selection, 3D analysis, and visualization."""

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
            from aaa_vision.point_cloud import CameraIntrinsics, PointCloudProcessor

            classes = self.frozen_detections["classes"]
            class_name = classes[object_index]
            contours = self.frozen_detections.get("contours", [])

            if object_index >= len(contours):
                raise ValueError("No contour data for selected object")

            display_depth = getattr(self, "frozen_display_depth", None)
            native_depth = self.frozen_depth_frame
            aligned_color = self.frozen_aligned_color

            contour = contours[object_index]
            mask_rgb = np.zeros((1080, 1920), dtype=np.uint8)
            cv2.drawContours(
                mask_rgb,
                [np.array(contour, dtype=np.int32)],
                -1,
                255,
                thickness=cv2.FILLED,
            )

            if display_depth is not None:
                # Use color-aligned depth (1920x1080) with mask at same resolution
                depth_for_pcd = display_depth
                raw_frame = getattr(self, "frozen_raw_frame", None)
                color_for_pcd = raw_frame[:, :, ::-1] if raw_frame is not None else None  # BGR->RGB
                mask_for_pcd = mask_rgb

                # Build processor with color camera intrinsics
                color_intrinsics = None
                try:
                    import pyrealsense2 as rs
                    if hasattr(self.image_processor, "rs_camera") and self.image_processor.rs_camera:
                        profile = self.image_processor.rs_camera.profile
                        cs = profile.get_stream(rs.stream.color).as_video_stream_profile()
                        rs_intr = cs.get_intrinsics()
                        color_intrinsics = CameraIntrinsics(
                            width=rs_intr.width, height=rs_intr.height,
                            fx=rs_intr.fx, fy=rs_intr.fy,
                            cx=rs_intr.ppx, cy=rs_intr.ppy,
                        )
                except Exception:
                    pass
                processor = PointCloudProcessor(intrinsics=color_intrinsics)
            elif native_depth is not None:
                # Fallback: native depth with resized mask (imprecise due to FOV mismatch)
                depth_for_pcd = native_depth
                color_for_pcd = aligned_color
                h_depth, w_depth = native_depth.shape[:2]
                mask_for_pcd = cv2.resize(
                    mask_rgb, (w_depth, h_depth), interpolation=cv2.INTER_NEAREST
                )
                processor = PointCloudProcessor()
            else:
                raise ValueError("No depth frame available")

            # Create object point cloud
            object_pcd = processor.extract_object(depth_for_pcd, mask_for_pcd, color_for_pcd)

            # Create scene point cloud
            scene_pcd = processor.create_from_depth(depth_for_pcd, color_for_pcd)
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
        # Use color intrinsics to project directly to 1920x1080 (no scaling needed)
        intr = None
        try:
            import pyrealsense2 as rs

            if (
                hasattr(self.image_processor, "rs_camera")
                and self.image_processor.rs_camera
            ):
                profile = self.image_processor.rs_camera.profile
                color_stream = profile.get_stream(
                    rs.stream.color
                ).as_video_stream_profile()
                intr = color_stream.get_intrinsics()
        except Exception:
            pass

        if intr is not None:
            import pyrealsense2 as rs

            pixel = rs.rs2_project_point_to_pixel(
                intr, [float(point_3d[0]), float(point_3d[1]), float(point_3d[2])]
            )
            px_rgb, py_rgb = int(pixel[0]), int(pixel[1])
        else:
            # Fallback: approximate D435 color intrinsics at 1920x1080
            fx, fy = 1386.0, 1386.0
            cx, cy = 960.0, 540.0
            if point_3d[2] != 0:
                px_rgb = int(point_3d[0] * fx / point_3d[2] + cx)
                py_rgb = int(point_3d[1] * fy / point_3d[2] + cy)
            else:
                px_rgb, py_rgb = int(cx), int(cy)

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
                    self.frozen_depth_frame,
                    aligned_color=self.frozen_aligned_color,
                    display_shape=self.frozen_raw_frame.shape,
                    display_depth=getattr(self, "frozen_display_depth", None),
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
                # Copy display depth frame (1920x1080, aligned to color FOV)
                self.frozen_display_depth = getattr(
                    self.image_processor, "_last_display_depth", None
                )
                if self.frozen_display_depth is not None:
                    self.frozen_display_depth = self.frozen_display_depth.copy()
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
                # Copy display depth frame (1920x1080, aligned to color FOV)
                self.frozen_display_depth = getattr(
                    self.image_processor, "_last_display_depth", None
                )
                if self.frozen_display_depth is not None:
                    self.frozen_display_depth = self.frozen_display_depth.copy()
                self.video_frozen = True
                print("Find Objects: Video frozen on new frame")

            threading.Thread(target=capture_and_freeze, daemon=True).start()

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
