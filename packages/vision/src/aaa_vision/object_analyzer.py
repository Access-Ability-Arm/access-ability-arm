"""
Object analysis for grasp planning using Open3D.

Analyzes a selected object's 3D geometry (shape, planes, centroid)
and computes grasp parameters for the Lite6 gripper.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

import numpy as np
import open3d as o3d
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

from aaa_vision.point_cloud import PointCloudProcessor, get_point_cloud_stats

logger = logging.getLogger(__name__)

# Lite6 gripper physical constraints
GRIPPER_MAX_OPENING_M = 0.066  # 66mm max opening
GRIPPER_MIN_WIDTH_M = 0.005  # 5mm min graspable width
GRIPPER_FINGER_LENGTH_M = 0.045  # 45mm finger length
TABLE_CLEARANCE_M = 0.015  # 15mm min above table

# Shape classification thresholds
CURVATURE_THRESHOLD = 0.01
FLAT_RATIO_THRESHOLD = 0.6
CURVED_RATIO_THRESHOLD = 0.6
MIN_INLIER_RATIO = 0.4

# Curvature computation parameters
CURVATURE_K = 30  # k-nearest neighbors for curvature


@dataclass
class PlaneInfo:
    """Information about a detected plane."""

    model: np.ndarray  # [a, b, c, d] plane equation
    normal: np.ndarray  # unit normal vector
    centroid: np.ndarray  # [x, y, z] center of plane points
    inlier_points: np.ndarray  # Nx3 array of points on the plane
    area_estimate: float  # estimated area in m^2


@dataclass
class ShapeEstimate:
    """Shape estimation result."""

    shape_type: str  # "cylinder", "box", "sphere", "irregular"
    confidence: float  # 0-1 (inlier ratio from best RANSAC fit)
    dimensions: dict  # shape-specific measurements
    oriented_bbox: Any  # Open3D OrientedBoundingBox
    curvature_profile: dict  # flat_ratio, curved_ratio, mean_curvature
    fit_residual: float  # RMSE of best primitive fit


@dataclass
class ObjectAnalysis:
    """Complete analysis result for a detected object."""

    centroid: np.ndarray  # [x, y, z] main body center
    shape: ShapeEstimate
    table_plane: Optional[PlaneInfo]
    top_plane: Optional[PlaneInfo]  # None if no flat top
    main_body_points: np.ndarray  # Nx3 core points (outliers removed)
    main_body_radius: float  # characteristic radius from centroid
    grasp_point: np.ndarray  # [x, y, z] recommended grasp location
    grasp_approach: np.ndarray  # [nx, ny, nz] approach direction
    grasp_width: float  # required gripper opening in meters
    graspable: bool  # False if object too large/small for Lite6 gripper
    grasp_confidence: float  # 0.0-1.0 probability
    num_points: int


class ObjectAnalyzer:
    """
    Analyzes 3D geometry of detected objects for grasp planning.

    Uses curvature analysis + RANSAC primitive fitting to classify
    shapes and compute grasp parameters.
    """

    def __init__(self, processor: Optional[PointCloudProcessor] = None):
        self.processor = processor or PointCloudProcessor()

    def analyze(
        self,
        object_pcd: o3d.geometry.PointCloud,
        scene_pcd: Optional[o3d.geometry.PointCloud] = None,
    ) -> ObjectAnalysis:
        """
        Full analysis pipeline for a detected object.

        Args:
            object_pcd: Point cloud of the segmented object
            scene_pcd: Optional full scene point cloud (for table plane detection)

        Returns:
            ObjectAnalysis with shape, grasp point, and metadata
        """
        # Extract table plane from scene if provided
        table_plane = None
        if scene_pcd is not None and len(scene_pcd.points) > 100:
            table_plane = self._extract_table_plane(scene_pcd)

        # Characterize main body (outlier removal + largest cluster)
        main_body_pcd, main_body_radius = self._characterize_main_body(object_pcd)
        main_body_points = np.asarray(main_body_pcd.points)

        if len(main_body_points) == 0:
            logger.warning("No points after main body characterization")
            main_body_points = np.asarray(object_pcd.points)
            main_body_pcd = object_pcd
            main_body_radius = 0.0

        centroid = main_body_points.mean(axis=0)
        num_points = len(main_body_points)

        # Ensure normals are estimated
        if not main_body_pcd.has_normals():
            main_body_pcd = self.processor.preprocess(
                main_body_pcd, voxel_size=0.003, estimate_normals=True
            )
            main_body_points = np.asarray(main_body_pcd.points)
            if len(main_body_points) == 0:
                return self._fallback_analysis(
                    object_pcd, table_plane, centroid, num_points
                )

        # Compute curvature profile
        curvature_profile = self._compute_curvature_profile(main_body_pcd)

        # Estimate shape
        shape = self._estimate_shape(main_body_pcd, curvature_profile)

        # Detect top plane
        top_plane = self._detect_top_plane(main_body_pcd, table_plane)

        # Compute grasp point
        grasp_point, grasp_approach, grasp_width = self._compute_grasp_point(
            main_body_pcd, shape, table_plane, centroid
        )

        # Check graspability
        object_height = main_body_points[:, 1].max() - main_body_points[:, 1].min()
        graspable = self._check_graspable(shape, grasp_width, object_height)

        # Assess confidence
        grasp_confidence = self._assess_confidence(shape, num_points, main_body_pcd)

        logger.debug(
            f"Analysis: shape={shape.shape_type}, confidence={shape.confidence:.2f}, "
            f"grasp_width={grasp_width * 1000:.1f}mm, graspable={graspable}, "
            f"grasp_confidence={grasp_confidence}, points={num_points}"
        )

        return ObjectAnalysis(
            centroid=centroid,
            shape=shape,
            table_plane=table_plane,
            top_plane=top_plane,
            main_body_points=main_body_points,
            main_body_radius=main_body_radius,
            grasp_point=grasp_point,
            grasp_approach=grasp_approach,
            grasp_width=grasp_width,
            graspable=graspable,
            grasp_confidence=grasp_confidence,
            num_points=num_points,
        )

    def analyze_from_file(self, path: str) -> ObjectAnalysis:
        """
        Load a point cloud from file and run analysis.

        Args:
            path: Path to .npz or .ply file

        Returns:
            ObjectAnalysis result
        """
        if path.endswith(".npz"):
            data = np.load(path)
            depth = data.get("depth")
            color = data.get("color", data.get("rgb", None))
            if depth is None:
                raise ValueError(f"NPZ file {path} has no 'depth' key")
            object_pcd = self.processor.create_from_depth(depth, color)
        elif path.endswith(".ply"):
            object_pcd = o3d.io.read_point_cloud(path)
        else:
            raise ValueError(f"Unsupported file format: {path}")

        object_pcd = self.processor.preprocess(object_pcd, voxel_size=0.003)
        return self.analyze(object_pcd)

    def _extract_table_plane(
        self, scene_pcd: o3d.geometry.PointCloud
    ) -> Optional[PlaneInfo]:
        """Extract the dominant table plane from a scene point cloud."""
        scene_preprocessed = self.processor.preprocess(scene_pcd, voxel_size=0.005)
        if len(scene_preprocessed.points) < 100:
            return None

        _, plane_model = self.processor.remove_plane(scene_preprocessed)
        if plane_model is None:
            return None

        normal = plane_model[:3]
        normal = normal / np.linalg.norm(normal)

        # Validate: table normal should be roughly vertical
        # In camera frame, Y is typically down, so table normal ~ [0, -1, 0] or [0, 1, 0]
        gravity_axes = [np.array([0, 1, 0]), np.array([0, -1, 0]), np.array([0, 0, 1])]
        is_vertical = any(abs(np.dot(normal, g)) > 0.8 for g in gravity_axes)

        if not is_vertical:
            logger.debug("Detected plane is not vertical enough to be a table")
            return None

        # Get inlier points
        points = np.asarray(scene_preprocessed.points)
        distances = np.abs(points @ plane_model[:3] + plane_model[3])
        inlier_mask = distances < 0.01
        inlier_points = points[inlier_mask]

        if len(inlier_points) < 10:
            return None

        plane_centroid = inlier_points.mean(axis=0)

        # Estimate area from convex hull of projected points
        area = self._estimate_plane_area(inlier_points, normal)

        return PlaneInfo(
            model=plane_model,
            normal=normal,
            centroid=plane_centroid,
            inlier_points=inlier_points,
            area_estimate=area,
        )

    def _detect_top_plane(
        self,
        object_pcd: o3d.geometry.PointCloud,
        table_plane: Optional[PlaneInfo],
    ) -> Optional[PlaneInfo]:
        """Detect a flat top surface on the object."""
        points = np.asarray(object_pcd.points)
        if len(points) < 30:
            return None

        # Sort by Y axis (camera Y is typically down, so min Y = top)
        y_values = points[:, 1]
        y_range = y_values.max() - y_values.min()
        if y_range < 0.005:  # Object too flat to have distinct top
            return None

        # Take upper 20% of points
        y_threshold = y_values.min() + 0.2 * y_range
        top_mask = y_values <= y_threshold
        top_points = points[top_mask]

        if len(top_points) < 10:
            return None

        # Create a temporary point cloud for RANSAC
        top_pcd = o3d.geometry.PointCloud()
        top_pcd.points = o3d.utility.Vector3dVector(top_points)

        # RANSAC plane fit
        try:
            plane_model, inliers = top_pcd.segment_plane(
                distance_threshold=0.005, ransac_n=3, num_iterations=500
            )
        except RuntimeError:
            return None

        inlier_ratio = len(inliers) / len(top_points)
        if inlier_ratio < 0.3:
            return None

        normal = np.array(plane_model[:3])
        normal = normal / np.linalg.norm(normal)

        # Validate: top plane should be roughly horizontal
        gravity_axes = [np.array([0, 1, 0]), np.array([0, -1, 0])]
        is_horizontal = any(abs(np.dot(normal, g)) > 0.7 for g in gravity_axes)

        if not is_horizontal:
            return None

        inlier_points = top_points[inliers]
        plane_centroid = inlier_points.mean(axis=0)
        area = self._estimate_plane_area(inlier_points, normal)

        return PlaneInfo(
            model=np.array(plane_model),
            normal=normal,
            centroid=plane_centroid,
            inlier_points=inlier_points,
            area_estimate=area,
        )

    def _characterize_main_body(
        self, object_pcd: o3d.geometry.PointCloud
    ) -> Tuple[o3d.geometry.PointCloud, float]:
        """
        Extract the main body by removing outliers and selecting the largest cluster.

        Returns:
            Tuple of (cleaned point cloud, characteristic radius from centroid)
        """
        if len(object_pcd.points) < 10:
            return object_pcd, 0.0

        # Outlier removal
        cleaned = self.processor.preprocess(
            object_pcd, voxel_size=0.003, estimate_normals=True
        )

        if len(cleaned.points) < 10:
            return object_pcd, 0.0

        # DBSCAN clustering to find largest connected component
        clusters = self.processor.cluster_objects(cleaned, eps=0.015, min_points=10)

        if not clusters:
            main_body = cleaned
        else:
            # Select largest cluster
            main_body = max(clusters, key=lambda c: len(c.points))

        points = np.asarray(main_body.points)
        if len(points) == 0:
            return object_pcd, 0.0

        centroid = points.mean(axis=0)
        distances = np.linalg.norm(points - centroid, axis=1)
        radius = np.median(distances)

        return main_body, radius

    def _compute_curvature_profile(self, pcd: o3d.geometry.PointCloud) -> dict:
        """
        Compute per-point curvature using normal covariance in a k-neighborhood.

        Uses k=30 with median filtering to suppress D435 depth noise.
        """
        points = np.asarray(pcd.points)
        normals = np.asarray(pcd.normals)
        n_points = len(points)

        if n_points < CURVATURE_K:
            return {"flat_ratio": 0.5, "curved_ratio": 0.5, "mean_curvature": 0.01}

        # Batch KNN via scipy cKDTree
        tree = cKDTree(points)
        k = min(CURVATURE_K, n_points)
        _, all_idx = tree.query(points, k=k)

        # Compute curvature: smallest eigenvalue of normal covariance per neighborhood
        curvature = np.zeros(n_points)
        for i in range(n_points):
            neighbor_normals = normals[all_idx[i]]
            cov = np.cov(neighbor_normals.T)
            curvature[i] = np.min(np.linalg.eigvalsh(cov))

        # Median filter: replace each point's curvature with median of its neighbors
        curvature_filtered = np.zeros_like(curvature)
        for i in range(n_points):
            curvature_filtered[i] = np.median(curvature[all_idx[i]])
        curvature = curvature_filtered

        # Classify points
        flat_mask = curvature < CURVATURE_THRESHOLD
        flat_ratio = flat_mask.sum() / n_points
        curved_ratio = 1.0 - flat_ratio
        mean_curvature = float(np.mean(curvature))

        return {
            "flat_ratio": float(flat_ratio),
            "curved_ratio": float(curved_ratio),
            "mean_curvature": mean_curvature,
        }

    def _estimate_shape(
        self,
        pcd: o3d.geometry.PointCloud,
        curvature_profile: dict,
    ) -> ShapeEstimate:
        """
        Estimate object shape using curvature pre-filter + RANSAC fitting.
        """
        points = np.asarray(pcd.points)
        obb = pcd.get_oriented_bounding_box()
        obb_extent = np.array(obb.extent)

        flat_ratio = curvature_profile["flat_ratio"]
        curved_ratio = curvature_profile["curved_ratio"]

        best_shape = "irregular"
        best_confidence = 0.0
        best_dimensions = {}
        best_residual = float("inf")

        # Candidate selection based on curvature
        if flat_ratio > FLAT_RATIO_THRESHOLD:
            # Try box first
            conf, dims, resid = self._fit_box(pcd, obb)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "box",
                    conf,
                    dims,
                    resid,
                )
            # Also try cylinder (boxes can have curved edges in noisy data)
            conf, dims, resid = self._fit_cylinder(pcd, obb)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "cylinder",
                    conf,
                    dims,
                    resid,
                )
        elif curved_ratio > CURVED_RATIO_THRESHOLD:
            # Try sphere first
            conf, dims, resid = self._fit_sphere(points)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "sphere",
                    conf,
                    dims,
                    resid,
                )
            # Also try cylinder
            conf, dims, resid = self._fit_cylinder(pcd, obb)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "cylinder",
                    conf,
                    dims,
                    resid,
                )
        else:
            # Mixed - try cylinder first (most common mixed shape)
            conf, dims, resid = self._fit_cylinder(pcd, obb)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "cylinder",
                    conf,
                    dims,
                    resid,
                )
            conf, dims, resid = self._fit_sphere(points)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "sphere",
                    conf,
                    dims,
                    resid,
                )
            conf, dims, resid = self._fit_box(pcd, obb)
            if conf > best_confidence:
                best_shape, best_confidence, best_dimensions, best_residual = (
                    "box",
                    conf,
                    dims,
                    resid,
                )

        # Fall back to irregular if confidence too low
        if best_confidence < MIN_INLIER_RATIO:
            best_shape = "irregular"
            sorted_extent = np.sort(obb_extent)
            best_dimensions = {
                "width": float(sorted_extent[0]),
                "depth": float(sorted_extent[1]),
                "height": float(sorted_extent[2]),
            }

        return ShapeEstimate(
            shape_type=best_shape,
            confidence=best_confidence,
            dimensions=best_dimensions,
            oriented_bbox=obb,
            curvature_profile=curvature_profile,
            fit_residual=best_residual,
        )

    def _fit_sphere(self, points: np.ndarray) -> Tuple[float, dict, float]:
        """Fit a sphere using pyransac3d."""
        if len(points) < 20:
            return 0.0, {}, float("inf")

        try:
            import pyransac3d as pyrsc

            sphere = pyrsc.Sphere()
            center, radius, inliers = sphere.fit(points, thresh=0.005)
        except Exception as e:
            logger.debug(f"Sphere fitting failed: {e}")
            return 0.0, {}, float("inf")

        if radius <= 0 or len(inliers) == 0:
            return 0.0, {}, float("inf")

        inlier_ratio = len(inliers) / len(points)
        inlier_points = points[inliers]
        distances = np.abs(np.linalg.norm(inlier_points - center, axis=1) - radius)
        residual = float(np.sqrt(np.mean(distances**2)))

        dims = {"radius": float(radius), "center": center.tolist()}
        return inlier_ratio, dims, residual

    def _fit_box(
        self,
        pcd: o3d.geometry.PointCloud,
        obb: o3d.geometry.OrientedBoundingBox,
    ) -> Tuple[float, dict, float]:
        """
        Detect box using OBB + RANSAC flat-face confirmation.

        For each OBB axis, take points near the face and RANSAC-fit a plane.
        """
        points = np.asarray(pcd.points)
        if len(points) < 20:
            return 0.0, {}, float("inf")

        obb_center = np.array(obb.center)
        obb_rotation = np.array(obb.R)
        obb_extent = np.array(obb.extent)

        confirmed_faces = 0
        total_inlier_ratio = 0.0
        total_residual = 0.0

        for axis_idx in range(3):
            axis = obb_rotation[:, axis_idx]
            half_extent = obb_extent[axis_idx] / 2.0

            # Project points onto this axis (relative to OBB center)
            projections = (points - obb_center) @ axis

            # Take points within 10% of extent from the nearest face
            threshold = 0.1 * obb_extent[axis_idx]

            # Near positive face
            near_pos = np.abs(projections - half_extent) < threshold
            # Near negative face
            near_neg = np.abs(projections + half_extent) < threshold

            for face_mask in [near_pos, near_neg]:
                face_points = points[face_mask]
                if len(face_points) < 10:
                    continue

                face_pcd = o3d.geometry.PointCloud()
                face_pcd.points = o3d.utility.Vector3dVector(face_points)

                try:
                    plane_model, inliers = face_pcd.segment_plane(
                        distance_threshold=0.005, ransac_n=3, num_iterations=200
                    )
                except RuntimeError:
                    continue

                face_inlier_ratio = len(inliers) / len(face_points)
                if face_inlier_ratio < 0.5:
                    continue

                # Check normal aligns with OBB axis
                face_normal = np.array(plane_model[:3])
                face_normal = face_normal / np.linalg.norm(face_normal)
                alignment = abs(np.dot(face_normal, axis))

                if alignment > 0.9:
                    confirmed_faces += 1
                    total_inlier_ratio += face_inlier_ratio

                    # Compute residual
                    inlier_pts = face_points[inliers]
                    dists = np.abs(inlier_pts @ face_normal + plane_model[3])
                    total_residual += float(np.sqrt(np.mean(dists**2)))
                    break  # One confirmed face per axis is enough

        if confirmed_faces == 0:
            return 0.0, {}, float("inf")

        confidence = (confirmed_faces / 3.0) * (total_inlier_ratio / confirmed_faces)
        avg_residual = total_residual / confirmed_faces

        sorted_extent = np.sort(obb_extent)
        dims = {
            "width": float(sorted_extent[0]),
            "depth": float(sorted_extent[1]),
            "height": float(sorted_extent[2]),
        }

        return confidence, dims, avg_residual

    def _fit_cylinder(
        self,
        pcd: o3d.geometry.PointCloud,
        obb: o3d.geometry.OrientedBoundingBox,
    ) -> Tuple[float, dict, float]:
        """
        Fit cylinder: OBB longest axis as cylinder axis, fit circle in perpendicular projection.
        """
        points = np.asarray(pcd.points)
        if len(points) < 20:
            return 0.0, {}, float("inf")

        obb_rotation = np.array(obb.R)
        obb_extent = np.array(obb.extent)

        # Longest axis = candidate cylinder axis
        longest_idx = np.argmax(obb_extent)
        cylinder_axis = obb_rotation[:, longest_idx]
        cylinder_height = float(obb_extent[longest_idx])

        # Project points onto plane perpendicular to cylinder axis
        center = points.mean(axis=0)
        relative = points - center
        along_axis = (relative @ cylinder_axis).reshape(-1, 1) * cylinder_axis
        projected = relative - along_axis  # points in perpendicular plane

        # Pick 2 orthogonal axes in the perpendicular plane
        perp1_idx = (longest_idx + 1) % 3
        perp2_idx = (longest_idx + 2) % 3
        perp1 = obb_rotation[:, perp1_idx]
        perp2 = obb_rotation[:, perp2_idx]

        # 2D coordinates in perpendicular plane
        x_2d = projected @ perp1
        y_2d = projected @ perp2

        # Fit circle using least-squares
        try:
            circle_center, circle_radius = self._fit_circle_2d(x_2d, y_2d)
        except Exception:
            return 0.0, {}, float("inf")

        if circle_radius <= 0:
            return 0.0, {}, float("inf")

        # Compute inliers: points within threshold of cylinder surface
        distances_2d = np.sqrt(
            (x_2d - circle_center[0]) ** 2 + (y_2d - circle_center[1]) ** 2
        )
        surface_distances = np.abs(distances_2d - circle_radius)
        threshold = 0.005  # 5mm
        inlier_mask = surface_distances < threshold
        inlier_ratio = inlier_mask.sum() / len(points)

        residual = (
            float(np.sqrt(np.mean(surface_distances[inlier_mask] ** 2)))
            if inlier_mask.any()
            else float("inf")
        )

        dims = {
            "radius": float(circle_radius),
            "height": cylinder_height,
            "axis": cylinder_axis.tolist(),
        }

        return inlier_ratio, dims, residual

    def _fit_circle_2d(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
        """Fit a circle to 2D points using least-squares."""
        # Initial guess: mean center, mean distance as radius
        cx0, cy0 = x.mean(), y.mean()
        r0 = np.sqrt((x - cx0) ** 2 + (y - cy0) ** 2).mean()

        def residuals(params):
            cx, cy, r = params
            return np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r

        result = least_squares(residuals, [cx0, cy0, r0])
        cx, cy, r = result.x
        return np.array([cx, cy]), abs(r)

    def _compute_grasp_point(
        self,
        pcd: o3d.geometry.PointCloud,
        shape: ShapeEstimate,
        table_plane: Optional[PlaneInfo],
        centroid: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Compute grasp point, approach direction, and required width.

        Returns:
            (grasp_point, approach_direction, grasp_width)
        """
        points = np.asarray(pcd.points)
        obb = shape.oriented_bbox

        if shape.shape_type == "cylinder":
            grasp_point = centroid.copy()
            # Approach perpendicular to cylinder axis, from camera-facing side
            axis = np.array(shape.dimensions.get("axis", [0, 1, 0]))
            # Camera is at origin, so approach from -Z direction (toward camera)
            camera_dir = -centroid / (np.linalg.norm(centroid) + 1e-8)
            # Remove component along cylinder axis
            approach = camera_dir - np.dot(camera_dir, axis) * axis
            norm = np.linalg.norm(approach)
            approach = approach / norm if norm > 1e-8 else np.array([0, 0, -1])
            grasp_width = 2.0 * shape.dimensions.get("radius", 0.03)

        elif shape.shape_type == "box":
            # Grasp center of largest visible face
            obb_rotation = np.array(obb.R)
            obb_extent = np.array(obb.extent)

            # Find which face is most camera-facing
            camera_dir = -centroid / (np.linalg.norm(centroid) + 1e-8)
            best_axis = 0
            best_dot = 0
            for i in range(3):
                d = abs(np.dot(obb_rotation[:, i], camera_dir))
                if d > best_dot:
                    best_dot = d
                    best_axis = i

            face_normal = obb_rotation[:, best_axis]
            if np.dot(face_normal, camera_dir) < 0:
                face_normal = -face_normal

            grasp_point = centroid.copy()
            approach = face_normal
            # Grasp width = shorter of the two non-approach extents
            other_extents = [obb_extent[i] for i in range(3) if i != best_axis]
            grasp_width = min(other_extents)

        elif shape.shape_type == "sphere":
            grasp_point = centroid.copy()
            # Top-down approach by default (-Y in camera frame)
            approach = np.array([0, -1, 0])
            grasp_width = 2.0 * shape.dimensions.get("radius", 0.03)

        else:  # irregular
            grasp_point = centroid.copy()
            approach = np.array([0, -1, 0])  # Top-down as safest default
            obb_extent = np.array(obb.extent)
            grasp_width = float(np.min(obb_extent))

        # Enforce table clearance
        if table_plane is not None:
            grasp_point = self._enforce_table_clearance(grasp_point, table_plane)

        return grasp_point, approach, grasp_width

    def _enforce_table_clearance(
        self, point: np.ndarray, table_plane: PlaneInfo
    ) -> np.ndarray:
        """Ensure grasp point is at least TABLE_CLEARANCE_M above the table."""
        normal = table_plane.normal
        # Distance from point to table plane
        dist = np.dot(point - table_plane.centroid, normal)
        # If normal points away from objects, distance is positive above table
        # If point is too close to table, shift it along the normal
        if abs(dist) < TABLE_CLEARANCE_M:
            shift = (
                (TABLE_CLEARANCE_M - abs(dist)) * np.sign(dist)
                if dist != 0
                else TABLE_CLEARANCE_M
            )
            point = point + shift * normal
        return point

    def _check_graspable(
        self, shape: ShapeEstimate, grasp_width: float, object_height: float
    ) -> bool:
        """Check if object fits Lite6 gripper constraints."""
        if grasp_width > GRIPPER_MAX_OPENING_M:
            return False
        if grasp_width < GRIPPER_MIN_WIDTH_M:
            return False
        if object_height < GRIPPER_MIN_WIDTH_M:
            return False
        return True

    def _assess_confidence(
        self,
        shape: ShapeEstimate,
        num_points: int,
        pcd: o3d.geometry.PointCloud,
    ) -> float:
        """Compute grasp confidence as a probability (0.0-1.0)."""
        # Shape confidence contributes 40%
        shape_score = shape.confidence if shape.shape_type != "irregular" else 0.1

        # Point count contributes 20% (saturates at 1000 points)
        point_score = min(1.0, num_points / 1000)

        # Visibility contributes 40%
        obb = shape.oriented_bbox
        obb_extent = np.array(obb.extent)
        sa = 2 * (
            obb_extent[0] * obb_extent[1]
            + obb_extent[1] * obb_extent[2]
            + obb_extent[0] * obb_extent[2]
        )
        if sa > 0:
            points = np.asarray(pcd.points)
            point_area = len(points) * (0.003**2)
            visibility = min(1.0, point_area / (sa * 0.5))
        else:
            visibility = 0.3

        return 0.4 * shape_score + 0.2 * point_score + 0.4 * visibility

    def _estimate_plane_area(self, points: np.ndarray, normal: np.ndarray) -> float:
        """Estimate area of a plane from its inlier points."""
        if len(points) < 3:
            return 0.0

        # Project to 2D (perpendicular to normal)
        # Find two axes perpendicular to the normal
        if abs(normal[0]) < 0.9:
            u = np.cross(normal, [1, 0, 0])
        else:
            u = np.cross(normal, [0, 1, 0])
        u = u / np.linalg.norm(u)
        v = np.cross(normal, u)

        projected = np.column_stack([points @ u, points @ v])

        try:
            from scipy.spatial import ConvexHull

            hull = ConvexHull(projected)
            return float(hull.volume)  # In 2D, volume = area
        except Exception:
            # Fallback: bounding rectangle area
            ranges = projected.max(axis=0) - projected.min(axis=0)
            return float(ranges[0] * ranges[1])

    def _fallback_analysis(
        self,
        pcd: o3d.geometry.PointCloud,
        table_plane: Optional[PlaneInfo],
        centroid: np.ndarray,
        num_points: int,
    ) -> ObjectAnalysis:
        """Produce a minimal analysis when not enough data for full pipeline."""
        points = np.asarray(pcd.points)
        if len(points) == 0:
            points = np.array([[0, 0, 0]])
            centroid = np.array([0, 0, 0])

        obb = pcd.get_oriented_bounding_box() if len(pcd.points) >= 4 else None
        obb_extent = (
            np.array(obb.extent) if obb is not None else np.array([0.01, 0.01, 0.01])
        )

        shape = ShapeEstimate(
            shape_type="irregular",
            confidence=0.0,
            dimensions={
                "width": float(np.min(obb_extent)),
                "depth": float(np.median(obb_extent)),
                "height": float(np.max(obb_extent)),
            },
            oriented_bbox=obb,
            curvature_profile={
                "flat_ratio": 0.5,
                "curved_ratio": 0.5,
                "mean_curvature": 0.0,
            },
            fit_residual=float("inf"),
        )

        grasp_point = centroid.copy()
        grasp_approach = np.array([0, -1, 0])
        grasp_width = float(np.min(obb_extent))

        if table_plane is not None:
            grasp_point = self._enforce_table_clearance(grasp_point, table_plane)

        return ObjectAnalysis(
            centroid=centroid,
            shape=shape,
            table_plane=table_plane,
            top_plane=None,
            main_body_points=points,
            main_body_radius=0.0,
            grasp_point=grasp_point,
            grasp_approach=grasp_approach,
            grasp_width=grasp_width,
            graspable=self._check_graspable(
                shape, grasp_width, float(np.max(obb_extent))
            ),
            grasp_confidence=0.1,
            num_points=num_points,
        )
