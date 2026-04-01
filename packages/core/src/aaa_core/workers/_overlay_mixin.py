"""Shared overlay drawing logic for image processors.

Provides depth visualization and reference point drawing used by
both ImageProcessor and DaemonImageProcessor.
"""

import cv2
import numpy as np


class OverlayMixin:
    """Mixin providing shared overlay methods for image processors."""

    def _init_overlay_state(self):
        """Initialize overlay-related attributes. Call from __init__."""
        self.reference_point = (250, 100)  # (x, y) for fixed depth reading
        self.show_reference_point = True
        self.show_depth_visualization = False

    def _draw_reference_point(
        self, image: np.ndarray, depth_frame: np.ndarray
    ) -> np.ndarray:
        """Draw a fixed reference point with depth measurement.

        Args:
            image: RGB image array
            depth_frame: Depth frame (uint16, values in mm)

        Returns:
            Image with reference point drawn
        """
        point_x, point_y = self.reference_point

        if 0 <= point_y < depth_frame.shape[0] and 0 <= point_x < depth_frame.shape[1]:
            try:
                distance_mm = depth_frame[point_y, point_x]
                cv2.circle(image, (point_x, point_y), 8, (255, 0, 0), -1)
                cv2.putText(
                    image,
                    f"{distance_mm} mm",
                    (point_x, point_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2,
                )
            except Exception:
                pass

        return image

    def _colorize_depth(
        self,
        depth_frame: np.ndarray,
        aligned_color: np.ndarray = None,
        display_shape: tuple = None,
        display_depth: np.ndarray = None,
    ) -> np.ndarray:
        """Convert depth frame to colorized visualization.

        If display_depth (1920x1080, aligned to color FOV) is provided, it is
        used directly — no upscaling needed and the FOV matches the RGB view.

        Args:
            depth_frame: Raw depth frame (uint16, values in mm) at native 848x480
            aligned_color: SDK-aligned color frame (BGR, same resolution as depth).
                Used only as fallback when display_depth is not available.
            display_shape: Target display shape — fallback upscale target when
                display_depth is not available.
            display_depth: Depth aligned to color camera FOV (uint16, mm) at 1920x1080.

        Returns:
            Colorized depth image as RGB numpy array at display resolution
        """
        if display_depth is not None:
            depth_clipped = np.clip(display_depth, 0, 5000)
            depth_normalized = (depth_clipped / 5000 * 255).astype(np.uint8)
            depth_colorized = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_TURBO)
            return cv2.cvtColor(depth_colorized, cv2.COLOR_BGR2RGB)

        depth_clipped = np.clip(depth_frame, 0, 5000)
        depth_normalized = (depth_clipped / 5000 * 255).astype(np.uint8)
        depth_colorized = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_TURBO)

        if aligned_color is not None and aligned_color.shape[:2] == depth_frame.shape[:2]:
            blended = cv2.addWeighted(aligned_color, 0.4, depth_colorized, 0.6, 0)
        else:
            blended = depth_colorized

        result = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)

        if display_shape is not None:
            h, w = display_shape[:2]
            result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR)

        return result
