"""
Point cloud processing for grasp planning using Open3D.

This module provides utilities for:
- Creating point clouds from RealSense depth data
- Preprocessing (outlier removal, downsampling, normal estimation)
- Workspace cropping
- Table plane segmentation
- Extracting object-specific point clouds using segmentation masks
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import open3d as o3d


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters."""

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    def to_open3d(self) -> o3d.camera.PinholeCameraIntrinsic:
        """Convert to Open3D camera intrinsic object."""
        return o3d.camera.PinholeCameraIntrinsic(
            self.width, self.height, self.fx, self.fy, self.cx, self.cy
        )


# Default intrinsics for RealSense D435 at 848x480
DEFAULT_D435_INTRINSICS = CameraIntrinsics(
    width=848, height=480, fx=425.19, fy=425.19, cx=423.86, cy=239.87
)


class PointCloudProcessor:
    """
    Process point clouds from depth images for grasp planning.

    Typical workflow:
        1. create_from_depth() - Create point cloud from depth image
        2. preprocess() - Clean and prepare point cloud
        3. crop_to_workspace() - Remove points outside robot workspace
        4. remove_plane() - Remove table surface
        5. extract_object() - Extract specific object using mask
    """

    def __init__(
        self,
        intrinsics: Optional[CameraIntrinsics] = None,
        depth_scale: float = 1000.0,
        depth_trunc: float = 3.0,
    ):
        """
        Initialize point cloud processor.

        Args:
            intrinsics: Camera intrinsic parameters. Uses D435 defaults if None.
            depth_scale: Depth units per meter (1000 for mm, 1 for meters)
            depth_trunc: Maximum depth in meters (points beyond are ignored)
        """
        self.intrinsics = intrinsics or DEFAULT_D435_INTRINSICS
        self.o3d_intrinsics = self.intrinsics.to_open3d()
        self.depth_scale = depth_scale
        self.depth_trunc = depth_trunc

    def create_from_depth(
        self,
        depth_image: np.ndarray,
        color_image: Optional[np.ndarray] = None,
    ) -> o3d.geometry.PointCloud:
        """
        Create point cloud from depth image.

        Args:
            depth_image: Depth image (H, W) uint16 in depth units
            color_image: Optional RGB image (H, W, 3) uint8

        Returns:
            Open3D point cloud
        """
        # Ensure depth is uint16
        if depth_image.dtype != np.uint16:
            depth_image = depth_image.astype(np.uint16)

        # Create Open3D depth image
        o3d_depth = o3d.geometry.Image(depth_image)

        if color_image is not None:
            # Ensure color is uint8 RGB
            if color_image.dtype != np.uint8:
                color_image = color_image.astype(np.uint8)

            # Handle BGR to RGB conversion if needed
            if len(color_image.shape) == 3 and color_image.shape[2] == 3:
                # Assume BGR from OpenCV, convert to RGB
                color_image_rgb = color_image[:, :, ::-1].copy()
            else:
                color_image_rgb = color_image

            # Resize color to match depth if needed
            if color_image_rgb.shape[:2] != depth_image.shape:
                import cv2

                color_image_rgb = cv2.resize(
                    color_image_rgb, (depth_image.shape[1], depth_image.shape[0])
                )

            o3d_color = o3d.geometry.Image(color_image_rgb)

            # Create RGBD image
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                o3d_color,
                o3d_depth,
                depth_scale=self.depth_scale,
                depth_trunc=self.depth_trunc,
                convert_rgb_to_intensity=False,
            )
        else:
            # Depth only - create grayscale color
            gray = np.zeros((*depth_image.shape, 3), dtype=np.uint8)
            gray[:, :] = [128, 128, 128]
            o3d_color = o3d.geometry.Image(gray)

            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                o3d_color,
                o3d_depth,
                depth_scale=self.depth_scale,
                depth_trunc=self.depth_trunc,
                convert_rgb_to_intensity=False,
            )

        # Create point cloud from RGBD
        pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, self.o3d_intrinsics)

        return pcd

    def preprocess(
        self,
        pcd: o3d.geometry.PointCloud,
        voxel_size: float = 0.005,
        nb_neighbors: int = 20,
        std_ratio: float = 2.0,
        estimate_normals: bool = True,
        normal_radius: float = 0.02,
    ) -> o3d.geometry.PointCloud:
        """
        Preprocess point cloud: remove outliers, downsample, estimate normals.

        Args:
            pcd: Input point cloud
            voxel_size: Voxel size for downsampling in meters (0.005 = 5mm)
            nb_neighbors: Number of neighbors for outlier removal
            std_ratio: Standard deviation ratio for outlier removal
            estimate_normals: Whether to estimate surface normals
            normal_radius: Search radius for normal estimation

        Returns:
            Preprocessed point cloud
        """
        if len(pcd.points) == 0:
            return pcd

        # Remove statistical outliers
        pcd_clean, _ = pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )

        if len(pcd_clean.points) == 0:
            return pcd_clean

        # Voxel downsampling
        pcd_down = pcd_clean.voxel_down_sample(voxel_size=voxel_size)

        # Estimate normals if requested
        if estimate_normals and len(pcd_down.points) > 0:
            pcd_down.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(
                    radius=normal_radius, max_nn=30
                )
            )
            # Orient normals toward camera (at origin)
            pcd_down.orient_normals_towards_camera_location(camera_location=[0, 0, 0])

        return pcd_down

    def crop_to_workspace(
        self,
        pcd: o3d.geometry.PointCloud,
        bounds: Dict[str, Tuple[float, float]],
    ) -> o3d.geometry.PointCloud:
        """
        Crop point cloud to workspace bounds.

        Args:
            pcd: Input point cloud
            bounds: Dictionary with min/max for x, y, z in meters
                    Example: {'x': (-0.5, 0.5), 'y': (-0.5, 0.5), 'z': (0.2, 1.0)}

        Returns:
            Cropped point cloud
        """
        if len(pcd.points) == 0:
            return pcd

        # Create axis-aligned bounding box
        min_bound = np.array(
            [
                bounds.get("x", (-np.inf, np.inf))[0],
                bounds.get("y", (-np.inf, np.inf))[0],
                bounds.get("z", (-np.inf, np.inf))[0],
            ]
        )
        max_bound = np.array(
            [
                bounds.get("x", (-np.inf, np.inf))[1],
                bounds.get("y", (-np.inf, np.inf))[1],
                bounds.get("z", (-np.inf, np.inf))[1],
            ]
        )

        bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound, max_bound)
        pcd_cropped = pcd.crop(bbox)

        return pcd_cropped

    def remove_plane(
        self,
        pcd: o3d.geometry.PointCloud,
        distance_threshold: float = 0.01,
        ransac_n: int = 3,
        num_iterations: int = 1000,
    ) -> Tuple[o3d.geometry.PointCloud, Optional[np.ndarray]]:
        """
        Remove the dominant plane (usually table) from point cloud using RANSAC.

        Args:
            pcd: Input point cloud
            distance_threshold: Max distance from plane to be inlier (meters)
            ransac_n: Number of points to sample for plane estimation
            num_iterations: RANSAC iterations

        Returns:
            Tuple of (point cloud with plane removed, plane model [a,b,c,d])
        """
        if len(pcd.points) < ransac_n:
            return pcd, None

        # Segment plane
        plane_model, inliers = pcd.segment_plane(
            distance_threshold=distance_threshold,
            ransac_n=ransac_n,
            num_iterations=num_iterations,
        )

        # Extract non-plane points (objects)
        pcd_objects = pcd.select_by_index(inliers, invert=True)

        return pcd_objects, np.array(plane_model)

    def extract_object(
        self,
        depth_image: np.ndarray,
        mask: np.ndarray,
        color_image: Optional[np.ndarray] = None,
        preprocess: bool = True,
    ) -> o3d.geometry.PointCloud:
        """
        Extract point cloud for a single object using segmentation mask.

        Args:
            depth_image: Full depth image (H, W) uint16
            mask: Binary mask for the object (H, W) bool or uint8
            color_image: Optional RGB image (H, W, 3)
            preprocess: Whether to preprocess the extracted cloud

        Returns:
            Point cloud for the masked object
        """
        # Ensure mask is boolean
        if mask.dtype != bool:
            mask = mask.astype(bool)

        # Resize mask to match depth if needed
        if mask.shape != depth_image.shape:
            import cv2

            mask_resized = cv2.resize(
                mask.astype(np.uint8),
                (depth_image.shape[1], depth_image.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
        else:
            mask_resized = mask

        # Apply mask to depth (zero out non-object pixels)
        depth_masked = depth_image.copy()
        depth_masked[~mask_resized] = 0

        # Mask color if provided
        if color_image is not None:
            # Resize color mask if needed
            if color_image.shape[:2] != depth_image.shape:
                import cv2

                color_mask = cv2.resize(
                    mask.astype(np.uint8),
                    (color_image.shape[1], color_image.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                ).astype(bool)
            else:
                color_mask = mask_resized

            color_masked = color_image.copy()
            color_masked[~color_mask] = 0
        else:
            color_masked = None

        # Create point cloud
        pcd = self.create_from_depth(depth_masked, color_masked)

        # Preprocess if requested
        if preprocess and len(pcd.points) > 0:
            pcd = self.preprocess(pcd, voxel_size=0.003)  # Finer for objects

        return pcd

    def cluster_objects(
        self,
        pcd: o3d.geometry.PointCloud,
        eps: float = 0.02,
        min_points: int = 10,
    ) -> List[o3d.geometry.PointCloud]:
        """
        Cluster point cloud into separate objects using DBSCAN.

        Args:
            pcd: Input point cloud (typically after plane removal)
            eps: DBSCAN clustering distance (meters)
            min_points: Minimum points per cluster

        Returns:
            List of point clouds, one per detected cluster
        """
        if len(pcd.points) < min_points:
            return []

        # Cluster using DBSCAN
        labels = np.array(
            pcd.cluster_dbscan(eps=eps, min_points=min_points, print_progress=False)
        )

        # Extract clusters
        clusters = []
        max_label = labels.max()

        for i in range(max_label + 1):
            indices = np.where(labels == i)[0]
            if len(indices) >= min_points:
                cluster = pcd.select_by_index(indices)
                clusters.append(cluster)

        return clusters


def visualize_point_clouds(
    point_clouds: List[o3d.geometry.PointCloud],
    colors: Optional[List[List[float]]] = None,
    window_name: str = "Point Clouds",
    coordinate_frame: bool = True,
):
    """
    Visualize multiple point clouds with different colors.

    Args:
        point_clouds: List of point clouds to visualize
        colors: Optional list of RGB colors (0-1 range) for each cloud
        window_name: Window title
        coordinate_frame: Whether to show coordinate axes
    """
    if not point_clouds:
        print("No point clouds to visualize")
        return

    # Default colors
    default_colors = [
        [1, 0, 0],  # Red
        [0, 1, 0],  # Green
        [0, 0, 1],  # Blue
        [1, 1, 0],  # Yellow
        [1, 0, 1],  # Magenta
        [0, 1, 1],  # Cyan
        [1, 0.5, 0],  # Orange
        [0.5, 0, 1],  # Purple
    ]

    geometries = []

    for i, pcd in enumerate(point_clouds):
        if colors and i < len(colors):
            color = colors[i]
        else:
            color = default_colors[i % len(default_colors)]

        pcd_colored = o3d.geometry.PointCloud(pcd)
        pcd_colored.paint_uniform_color(color)
        geometries.append(pcd_colored)

    # Add coordinate frame
    if coordinate_frame:
        coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=0.1, origin=[0, 0, 0]
        )
        geometries.append(coord_frame)

    o3d.visualization.draw_geometries(
        geometries,
        window_name=window_name,
        width=1280,
        height=720,
    )


def get_point_cloud_stats(pcd: o3d.geometry.PointCloud) -> Dict:
    """
    Get statistics about a point cloud.

    Args:
        pcd: Input point cloud

    Returns:
        Dictionary with point count, bounds, centroid, etc.
    """
    if len(pcd.points) == 0:
        return {
            "num_points": 0,
            "has_colors": False,
            "has_normals": False,
        }

    points = np.asarray(pcd.points)

    stats = {
        "num_points": len(points),
        "has_colors": pcd.has_colors(),
        "has_normals": pcd.has_normals(),
        "min_bound": points.min(axis=0).tolist(),
        "max_bound": points.max(axis=0).tolist(),
        "centroid": points.mean(axis=0).tolist(),
        "std": points.std(axis=0).tolist(),
    }

    return stats
