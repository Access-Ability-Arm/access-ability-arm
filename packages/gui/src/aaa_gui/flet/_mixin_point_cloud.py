"""Point cloud extraction and export mixin for MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import FletMainWindow


class PointCloudMixin:
    """Methods for point cloud extraction, PLY export, and preview."""

    @staticmethod
    def _ensure_meters(arr):
        """Convert pixel+depth_mm points to meters if needed.

        Detects (px, py, depth_mm) format by checking coordinate ranges and
        deprojects using default D435 color intrinsics (1920x1080).
        """
        import numpy as np

        if len(arr) == 0 or arr.shape[1] != 3:
            return arr
        # Heuristic: pixel coords have X > 50 and Z (depth_mm) > 50
        if arr[:, 0].max() > 50 and arr[:, 2].min() > 50:
            # Use color intrinsics (1920x1080) since display_depth is aligned to color
            fx, fy = 1386.12, 1386.12
            cx, cy = 964.83, 545.55
            z_m = arr[:, 2] / 1000.0
            x_m = (arr[:, 0] - cx) * z_m / fx
            y_m = (arr[:, 1] - cy) * z_m / fy
            arr = np.column_stack([x_m, y_m, z_m])
            print(f"  Deprojected {len(arr)} points from pixel+mm to meters")
        return arr

    def get_object_depth_points(
        self: FletMainWindow, object_index: int, subsample: int = 4, to_meters: bool = False
    ):
        """Return list of (x, y, depth_mm) or (X, Y, Z) if to_meters and RealSense available for selected frozen object."""
        import cv2
        import numpy as np

        if not getattr(self, "frozen_detections", None):
            return []

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return []

        contour = contours[object_index]

        rgb = getattr(self, "frozen_raw_frame", None)
        if rgb is None:
            print("No frozen RGB frame available for point extraction")
            return []

        # Prefer display_depth (1920x1080, aligned to color FOV) so mask coords
        # can index depth directly without scaling. The native depth (848x480) has
        # a wider FOV than the color camera, so linear scaling is inaccurate.
        display_depth = getattr(self, "frozen_display_depth", None)
        native_depth = getattr(self, "frozen_depth_frame", None)

        if display_depth is not None:
            depth = display_depth
            use_color_intrinsics = True
        elif native_depth is not None:
            depth = native_depth
            use_color_intrinsics = False
        else:
            print("No frozen depth frame available for point extraction")
            return []

        h_rgb, w_rgb = rgb.shape[:2]
        h_depth, w_depth = depth.shape[:2]

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return []

        xs = xs[::subsample]
        ys = ys[::subsample]

        if use_color_intrinsics:
            # display_depth is same resolution as RGB: index directly
            xs_d, ys_d = xs, ys
        else:
            # Fallback: scale to native depth resolution (imprecise due to FOV mismatch)
            scale_x = w_depth / w_rgb
            scale_y = h_depth / h_rgb
            xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
            ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)

        depths = depth[ys_d, xs_d]

        points = []
        use_realsense = getattr(
            self.image_processor, "use_realsense", False
        ) and getattr(self.image_processor, "rs_camera", None)
        intr = None
        rs_mod = None
        if to_meters and use_realsense:
            try:
                import pyrealsense2 as rs_mod

                profile = self.image_processor.rs_camera.profile
                if use_color_intrinsics:
                    stream = profile.get_stream(
                        rs_mod.stream.color
                    ).as_video_stream_profile()
                else:
                    stream = profile.get_stream(
                        rs_mod.stream.depth
                    ).as_video_stream_profile()
                intr = stream.get_intrinsics()
            except Exception as e:
                intr = None
                print(f"Failed to get RealSense intrinsics: {e}")

        for u_d, v_d, z in zip(xs_d, ys_d, depths):
            if z == 0:
                continue
            if to_meters and use_realsense and intr is not None:
                try:
                    pt = rs_mod.rs2_deproject_pixel_to_point(
                        intr, [int(u_d), int(v_d)], float(z) / 1000.0
                    )
                    points.append((float(pt[0]), float(pt[1]), float(pt[2])))
                except Exception:
                    points.append((int(u_d), int(v_d), int(z)))
            else:
                points.append((int(u_d), int(v_d), int(z)))

        return points

    def _extract_object_colors(
        self: FletMainWindow, object_index: int, subsample: int = 4,
        aligned_color: "np.ndarray | None" = None,
        depth: "np.ndarray | None" = None,
        display_depth: "np.ndarray | None" = None,
    ) -> "np.ndarray | None":
        """Extract RGB colors from aligned color frame for object mask pixels.

        Returns Nx3 uint8 array matching the points from get_object_depth_points,
        or None if color data is unavailable.
        """
        import cv2
        import numpy as np

        if not getattr(self, "frozen_detections", None):
            return None

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return None

        contour = contours[object_index]
        rgb = getattr(self, "frozen_raw_frame", None)
        if rgb is None:
            return None

        h_rgb, w_rgb = rgb.shape[:2]

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return None

        xs = xs[::subsample]
        ys = ys[::subsample]

        if display_depth is not None:
            # Color-aligned path: depth and RGB both at 1920x1080, index directly
            depths = display_depth[ys, xs]
            valid = depths > 0
            # Sample from frozen_raw_frame (BGR) directly, convert to RGB
            colors_bgr = rgb[ys[valid], xs[valid]]
            colors_rgb = colors_bgr[:, ::-1].copy()
            return colors_rgb
        elif aligned_color is not None and depth is not None:
            # Fallback: scale to native depth space (imprecise due to FOV mismatch)
            h_depth, w_depth = depth.shape[:2]
            scale_x = w_depth / w_rgb
            scale_y = h_depth / h_rgb
            xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
            ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)
            depths = depth[ys_d, xs_d]
            valid = depths > 0
            # Aligned color is BGR (from RealSense), convert to RGB
            colors_bgr = aligned_color[ys_d[valid], xs_d[valid]]
            colors_rgb = colors_bgr[:, ::-1].copy()
            return colors_rgb
        else:
            return None

    def get_object_mask_pixels(self: FletMainWindow, object_index: int, subsample: int = 8):
        """Return list of (x, y, depth_mm or 0 if unavailable) in RGB image coordinates for the object mask."""
        import cv2
        import numpy as np

        if not getattr(self, "frozen_detections", None):
            return []

        contours = self.frozen_detections.get("contours")
        if not contours or object_index >= len(contours):
            return []

        contour = contours[object_index]
        rgb = getattr(self, "frozen_raw_frame", None)
        depth = getattr(self, "frozen_depth_frame", None)
        if rgb is None:
            return []

        h_rgb, w_rgb = rgb.shape[:2]
        h_depth = depth.shape[0] if depth is not None else None
        w_depth = depth.shape[1] if depth is not None else None

        mask_rgb = np.zeros((h_rgb, w_rgb), dtype=np.uint8)
        cv2.drawContours(
            mask_rgb, [np.array(contour, dtype=np.int32)], -1, 255, thickness=cv2.FILLED
        )

        ys, xs = np.where(mask_rgb == 255)
        if len(xs) == 0:
            return []

        xs = xs[::subsample]
        ys = ys[::subsample]

        points = []
        # Prefer display_depth (1920x1080, aligned to color FOV) for accurate lookup
        display_depth = getattr(self, "frozen_display_depth", None)
        if display_depth is not None:
            depths = display_depth[ys, xs]
            for x, y, z in zip(xs, ys, depths):
                points.append((int(x), int(y), int(z)))
        elif depth is not None:
            # Fallback: scale to native depth coords (imprecise due to FOV mismatch)
            scale_x = w_depth / w_rgb
            scale_y = h_depth / h_rgb
            xs_d = np.clip((xs * scale_x).astype(int), 0, w_depth - 1)
            ys_d = np.clip((ys * scale_y).astype(int), 0, h_depth - 1)
            depths = depth[ys_d, xs_d]
            for x, y, z in zip(xs, ys, depths):
                points.append((int(x), int(y), int(z)))
        else:
            for x, y in zip(xs, ys):
                points.append((int(x), int(y), 0))

        return points

    def _export_selected_object_ply(self: FletMainWindow, e=None, subsample: int = 4):
        """Export selected object's point cloud to PLY with RGB colors."""
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=True
        )
        if not pts:
            print("No points available to export")
            return

        # Show overlay of sampled points for user verification before saving
        try:
            self._show_point_overlay(
                self.selected_object, subsample=max(1, subsample), duration=1.5
            )
            import time

            time.sleep(1.0)
        except Exception as ex:
            print(f"Overlay failed: {ex}")

        arr = np.array(pts, dtype=float)

        # Extract RGB colors
        display_depth = getattr(self, "frozen_display_depth", None)
        aligned_color = getattr(self, "frozen_aligned_color", None)
        depth = getattr(self, "frozen_depth_frame", None)
        colors = self._extract_object_colors(
            self.selected_object, subsample=subsample,
            aligned_color=aligned_color, depth=depth,
            display_depth=display_depth,
        )
        has_colors = colors is not None and len(colors) == len(arr)

        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_obj{self.selected_object + 1}_{timestamp}.ply"

        try:
            with open(out_path, "w") as f:
                f.write("ply\nformat ascii 1.0\n")
                f.write(f"element vertex {arr.shape[0]}\n")
                f.write("property float x\nproperty float y\nproperty float z\n")
                if has_colors:
                    f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
                f.write("end_header\n")
                if has_colors:
                    for (x, y, z), (r, g, b) in zip(arr, colors):
                        f.write(f"{x:.6f} {y:.6f} {z:.6f} {int(r)} {int(g)} {int(b)}\n")
                else:
                    for x, y, z in arr:
                        f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

            print(f"✓ PLY saved: {out_path} ({arr.shape[0]} points, rgb={'yes' if has_colors else 'no'})")
            # Record last exported path for preview
            try:
                self.last_exported_ply = str(out_path)
            except Exception:
                self.last_exported_ply = None

            if hasattr(self, "status_text"):
                self.status_text.value = f"PLY saved: {out_path.name}"
                self.page.update()
            return str(out_path)
        except Exception as ex:
            print(f"Failed to save PLY: {ex}")
            return None

    def _export_selected_object_mesh(
        self: FletMainWindow, e=None, subsample: int = 2, method: str = "poisson"
    ):
        """Export selected object as a reconstructed 3D mesh PLY file."""
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return None

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=True
        )
        if not pts:
            print("No points available to export")
            return None

        arr = self._ensure_meters(np.array(pts, dtype=float))

        try:
            import open3d as o3d
            from aaa_vision.point_cloud import PointCloudProcessor
        except ImportError as ex:
            print(f"Open3D required for mesh reconstruction: {ex}")
            return None

        # Build Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(arr)

        # Attach RGB colors if available
        display_depth = getattr(self, "frozen_display_depth", None)
        aligned_color = getattr(self, "frozen_aligned_color", None)
        depth = getattr(self, "frozen_depth_frame", None)
        colors = self._extract_object_colors(
            self.selected_object, subsample=subsample,
            aligned_color=aligned_color, depth=depth,
            display_depth=display_depth,
        )
        if colors is not None and len(colors) == len(arr):
            pcd.colors = o3d.utility.Vector3dVector(colors.astype(float) / 255.0)

        # Preprocess: outlier removal + normal estimation
        processor = PointCloudProcessor()
        pcd = processor.preprocess(pcd, voxel_size=0.003, estimate_normals=True)

        if len(pcd.points) < 20:
            print(f"Too few points after preprocessing ({len(pcd.points)}) for mesh reconstruction")
            return None

        # Reconstruct mesh (suppress C++ stderr noise from Poisson solver)
        print(f"Reconstructing mesh ({method}) from {len(pcd.points)} points...")
        import os
        stderr_fd = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        try:
            mesh = processor.reconstruct_mesh(pcd, method=method)
        finally:
            os.dup2(stderr_fd, 2)
            os.close(devnull)
            os.close(stderr_fd)

        if len(mesh.vertices) == 0:
            print("Mesh reconstruction produced no vertices")
            return None

        out_dir = Path("logs/meshes")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"mesh_obj{self.selected_object + 1}_{timestamp}.ply"

        try:
            o3d.io.write_triangle_mesh(str(out_path), mesh)
            n_verts = len(mesh.vertices)
            n_tris = len(mesh.triangles)
            print(f"Mesh saved: {out_path} ({n_verts} vertices, {n_tris} triangles)")
            self.last_exported_ply = str(out_path)
            if hasattr(self, "status_text"):
                self.status_text.value = f"Mesh saved: {out_path.name} ({n_verts}v, {n_tris}t)"
                self.page.update()
            return str(out_path)
        except Exception as ex:
            print(f"Failed to save mesh: {ex}")
            return None

    def _export_completed_object_mesh(
        self: FletMainWindow, e=None, subsample: int = 2
    ):
        """Export selected object as a shape-completed 3D mesh.

        Uses ObjectAnalyzer to classify the shape, then generates a full
        primitive mesh (sphere/cylinder/box) or mirrors the observed surface
        for irregular objects.
        """
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return None

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=True
        )
        if not pts:
            print("No points available to export")
            return None

        arr = self._ensure_meters(np.array(pts, dtype=float))

        try:
            import open3d as o3d
            from aaa_vision.object_analyzer import ObjectAnalyzer
            from aaa_vision.point_cloud import PointCloudProcessor
        except ImportError as ex:
            print(f"Open3D/aaa_vision required for shape completion: {ex}")
            return None

        # Build Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(arr)

        # Attach RGB colors
        display_depth = getattr(self, "frozen_display_depth", None)
        aligned_color = getattr(self, "frozen_aligned_color", None)
        depth = getattr(self, "frozen_depth_frame", None)
        colors = self._extract_object_colors(
            self.selected_object, subsample=subsample,
            aligned_color=aligned_color, depth=depth,
            display_depth=display_depth,
        )
        if colors is not None and len(colors) == len(arr):
            pcd.colors = o3d.utility.Vector3dVector(colors.astype(float) / 255.0)

        # Preprocess
        processor = PointCloudProcessor()
        pcd = processor.preprocess(pcd, voxel_size=0.003, estimate_normals=True)

        if len(pcd.points) < 20:
            print(f"Too few points ({len(pcd.points)}) for shape completion")
            return None

        # Run shape analysis
        print("Analyzing object shape...")
        analyzer = ObjectAnalyzer(processor)
        analysis = analyzer.analyze(pcd)

        shape = analysis.shape
        print(
            f"Shape: {shape.shape_type} (confidence={shape.confidence:.2f}), "
            f"dims={shape.dimensions}"
        )

        # Generate completed mesh (suppress C++ stderr noise from Poisson solver)
        print(f"Generating complete {shape.shape_type} mesh...")
        import os
        stderr_fd = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        try:
            mesh = processor.complete_mesh(
                pcd,
                shape_type=shape.shape_type,
                dimensions=shape.dimensions,
                centroid=analysis.centroid,
                oriented_bbox=shape.oriented_bbox,
            )
        finally:
            os.dup2(stderr_fd, 2)
            os.close(devnull)
            os.close(stderr_fd)

        if len(mesh.vertices) == 0:
            print("Shape completion produced no vertices")
            return None

        out_dir = Path("logs/meshes")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = (
            out_dir
            / f"completed_{shape.shape_type}_obj{self.selected_object + 1}_{timestamp}.ply"
        )

        try:
            o3d.io.write_triangle_mesh(str(out_path), mesh)
            n_verts = len(mesh.vertices)
            n_tris = len(mesh.triangles)
            print(
                f"Completed mesh saved: {out_path} "
                f"({n_verts} vertices, {n_tris} triangles)"
            )
            self.last_exported_ply = str(out_path)
            if hasattr(self, "status_text"):
                self.status_text.value = (
                    f"Completed {shape.shape_type}: {out_path.name} "
                    f"({n_verts}v, {n_tris}t)"
                )
                self.page.update()
            return str(out_path)
        except Exception as ex:
            print(f"Failed to save completed mesh: {ex}")
            return None

    def _preview_selected_object_ply(self: FletMainWindow, e=None):
        """Preview the last exported PLY file using view_pointcloud.py as a subprocess."""
        import os
        import subprocess
        import sys
        from pathlib import Path

        # Ensure there is an exported file; try to export if not present
        if not getattr(self, "last_exported_ply", None):
            print("No previously exported PLY found - exporting now...")
            path = self._export_selected_object_ply(e)
        else:
            path = self.last_exported_ply

        if not path:
            print("No PLY available to preview")
            return

        # Resolve viewer script path
        cwd = Path.cwd()
        cloudview_candidate = cwd / "scripts" / "view_pointcloud.py"
        if not cloudview_candidate.exists():
            cloudview_candidate = cwd / "Cloudview.py"
        if not cloudview_candidate.exists():
            # Try to locate viewer anywhere in repo
            import glob

            matches = glob.glob("**/view_pointcloud.py", recursive=True)
            if not matches:
                matches = glob.glob("**/Cloudview.py", recursive=True)
            if matches:
                cloudview_candidate = Path(matches[0])
            else:
                print("view_pointcloud.py not found in repo - cannot preview")
                return

        try:
            # Launch Cloudview in background
            subprocess.Popen(
                [sys.executable, str(cloudview_candidate), str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Launching Cloudview for: {path}")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Previewing: {Path(path).name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to launch Cloudview: {ex}")
