"""
Depth Validator Module

Provides lightweight depth discontinuity detection for RGB segmentation validation.
Uses fast Sobel-based gradient detection instead of computationally expensive
point cloud segmentation.

Based on research from docs/new-features.md Phase 3
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np


class DepthValidator:
    """
    Real-time depth validation for segmentation boundaries

    Performance: <2ms overhead
    Benefits:
    - Detects transparent objects invisible to RGB
    - Validates RGB boundaries with depth discontinuities
    - Resolves textureless objects (white on white)
    - Maintains real-time performance (30+ FPS)
    """

    def __init__(
        self,
        enabled: bool = True,
        discontinuity_threshold: float = 0.03,
        min_confidence: float = 0.5,
        edge_dilation: int = 1,
        use_bilateral_filter: bool = True,
        bilateral_d: int = 5,
        bilateral_sigma_color: float = 50.0,
        bilateral_sigma_space: float = 50.0
    ):
        """
        Initialize depth validator

        Args:
            enabled: Enable/disable depth validation (default True)
            discontinuity_threshold: Depth gradient threshold in meters (default 0.03 = 3cm)
                                    Smaller = more sensitive to edges
                                    Larger = only detect major discontinuities
            min_confidence: Minimum confidence for validation (default 0.5)
                           Boundaries with lower confidence are flagged
            edge_dilation: Dilation iterations for depth edges (default 1)
                          Larger = thicker edge regions for matching
            use_bilateral_filter: Apply bilateral filter to depth before edge detection
                                 Reduces noise while preserving edges (default True)
            bilateral_d: Bilateral filter diameter (default 5)
            bilateral_sigma_color: Bilateral filter color sigma (default 50.0)
            bilateral_sigma_space: Bilateral filter space sigma (default 50.0)
        """
        self.enabled = enabled
        self.discontinuity_threshold = discontinuity_threshold
        self.min_confidence = min_confidence
        self.edge_dilation = edge_dilation
        self.use_bilateral_filter = use_bilateral_filter
        self.bilateral_d = bilateral_d
        self.bilateral_sigma_color = bilateral_sigma_color
        self.bilateral_sigma_space = bilateral_sigma_space

        # Pre-create dilation kernel
        self.dilation_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (3, 3)
        )

    def validate_boundaries(
        self,
        depth_frame: np.ndarray,
        boxes: List[List[int]],
        contours: List[np.ndarray],
        min_depth: int = 100,
        max_depth: int = 5000
    ) -> Tuple[List[float], np.ndarray]:
        """
        Validate RGB segmentation boundaries using depth discontinuities

        Args:
            depth_frame: Depth map in millimeters (H x W)
            boxes: List of bounding boxes [x, y, w, h]
            contours: List of segmentation contours
            min_depth: Minimum valid depth in mm (default 100)
            max_depth: Maximum valid depth in mm (default 5000)

        Returns:
            Tuple of (confidences, depth_edges):
            - confidences: List of confidence scores (0.0-1.0) for each object
            - depth_edges: Binary edge map (H x W) for visualization
        """
        if not self.enabled or depth_frame is None or len(boxes) == 0:
            # Pass-through: return full confidence for all objects
            return [1.0] * len(boxes), None

        # Convert depth to meters for processing
        depth_m = depth_frame.astype(np.float32) / 1000.0

        # Mask invalid depths
        valid_mask = (depth_frame >= min_depth) & (depth_frame <= max_depth)
        depth_m[~valid_mask] = 0

        # Optional: Apply bilateral filter to reduce noise while preserving edges
        if self.use_bilateral_filter:
            # Only filter valid depth regions
            depth_filtered = cv2.bilateralFilter(
                depth_m.astype(np.float32),
                self.bilateral_d,
                self.bilateral_sigma_color / 1000.0,  # Convert to meters
                self.bilateral_sigma_space / 1000.0
            )
            # Restore masked regions
            depth_filtered[~valid_mask] = 0
        else:
            depth_filtered = depth_m

        # Compute depth gradients using Sobel
        grad_x = cv2.Sobel(depth_filtered, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(depth_filtered, cv2.CV_32F, 0, 1, ksize=3)

        # Gradient magnitude
        grad_magnitude = np.sqrt(grad_x**2 + grad_y**2)

        # Threshold to get depth edges
        depth_edges = (grad_magnitude > self.discontinuity_threshold).astype(np.uint8)

        # Dilate edges to create boundary regions
        if self.edge_dilation > 0:
            depth_edges = cv2.dilate(
                depth_edges,
                self.dilation_kernel,
                iterations=self.edge_dilation
            )

        # Validate each object's boundary
        confidences = []

        for i, (box, contour) in enumerate(zip(boxes, contours)):
            if len(contour) == 0:
                # No contour, default confidence
                confidences.append(self.min_confidence)
                continue

            # Create contour mask
            x, y, w, h = box
            contour_mask = np.zeros(depth_frame.shape, dtype=np.uint8)
            cv2.drawContours(contour_mask, [contour], -1, 1, 2)  # 2-pixel thickness

            # Count pixels where contour aligns with depth edges
            contour_pixels = np.sum(contour_mask > 0)
            aligned_pixels = np.sum((contour_mask > 0) & (depth_edges > 0))

            if contour_pixels == 0:
                confidence = self.min_confidence
            else:
                # Confidence = proportion of contour pixels that align with depth edges
                alignment_ratio = aligned_pixels / contour_pixels

                # Scale to confidence range [min_confidence, 1.0]
                confidence = self.min_confidence + alignment_ratio * (1.0 - self.min_confidence)
                confidence = np.clip(confidence, self.min_confidence, 1.0)

            confidences.append(float(confidence))

        return confidences, depth_edges

    def detect_transparent_objects(
        self,
        depth_frame: np.ndarray,
        rgb_detections: int,
        min_hole_area: int = 500
    ) -> List[np.ndarray]:
        """
        Detect potential transparent objects (depth holes with no RGB detection)

        Args:
            depth_frame: Depth map in millimeters
            rgb_detections: Number of RGB detections
            min_hole_area: Minimum area in pixels to consider (default 500)

        Returns:
            List of contours for potential transparent objects
        """
        if not self.enabled or depth_frame is None:
            return []

        # Find regions with invalid/zero depth (potential transparent objects)
        invalid_mask = (depth_frame == 0).astype(np.uint8) * 255

        # Morphological closing to fill small gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        invalid_mask = cv2.morphologyEx(invalid_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours of depth holes
        contours, _ = cv2.findContours(
            invalid_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter by area
        transparent_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_hole_area:
                transparent_contours.append(contour)

        return transparent_contours

    def visualize_validation(
        self,
        rgb_frame: np.ndarray,
        depth_edges: np.ndarray,
        confidences: List[float],
        boxes: List[List[int]]
    ) -> np.ndarray:
        """
        Visualize depth validation results

        Args:
            rgb_frame: RGB image
            depth_edges: Binary depth edge map
            confidences: List of confidence scores
            boxes: List of bounding boxes

        Returns:
            Visualization image
        """
        if depth_edges is None:
            return rgb_frame

        vis = rgb_frame.copy()

        # Overlay depth edges in cyan
        edge_overlay = np.zeros_like(rgb_frame)
        edge_overlay[depth_edges > 0] = [255, 255, 0]  # Cyan
        vis = cv2.addWeighted(vis, 0.7, edge_overlay, 0.3, 0)

        # Draw confidence scores on boxes
        for i, (box, conf) in enumerate(zip(boxes, confidences)):
            x, y, w, h = box

            # Color based on confidence: green (high) to red (low)
            if conf >= 0.8:
                color = (0, 255, 0)  # Green
            elif conf >= 0.6:
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 0, 255)  # Red

            # Draw confidence text
            cv2.putText(
                vis,
                f"Conf: {conf:.2f}",
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

        return vis

    def set_enabled(self, enabled: bool):
        """Enable or disable depth validation"""
        self.enabled = enabled

    def get_config(self) -> dict:
        """Get current configuration"""
        return {
            'enabled': self.enabled,
            'discontinuity_threshold': self.discontinuity_threshold,
            'min_confidence': self.min_confidence,
            'edge_dilation': self.edge_dilation,
            'use_bilateral_filter': self.use_bilateral_filter
        }
