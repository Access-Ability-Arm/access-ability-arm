"""Point cloud extraction and export mixin for MainWindow."""


class PointCloudMixin:
    """Methods for point cloud extraction, export (NPZ/PLY), and preview."""

    def get_object_depth_points(
        self, object_index: int, subsample: int = 4, to_meters: bool = False
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
        self, object_index: int, subsample: int = 4,
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

    def get_object_mask_pixels(self, object_index: int, subsample: int = 8):
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

    def _export_selected_object_pointcloud(
        self, e=None, subsample: int = 4, to_meters: bool = True
    ):
        """Export selected object's point cloud to logs/pointclouds as compressed .npz"""
        import time
        from pathlib import Path

        import numpy as np

        if self.selected_object is None:
            print("No object selected to export")
            return

        pts = self.get_object_depth_points(
            self.selected_object, subsample=subsample, to_meters=to_meters
        )
        if not pts:
            print("No points available to export")
            return

        # Show overlay of sampled points for user verification before saving
        try:
            self._show_point_overlay(
                self.selected_object, subsample=max(1, subsample), duration=1.5
            )
            # Give user a brief moment to see overlay
            import time

            time.sleep(1.0)
        except Exception as ex:
            print(f"Overlay failed: {ex}")

        arr = np.array(pts)
        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_obj{self.selected_object + 1}_{timestamp}.npz"
        try:
            # Extract RGB colors using color-aligned depth when available
            save_kwargs = {"points": arr}
            display_depth = getattr(self, "frozen_display_depth", None)
            aligned_color = getattr(self, "frozen_aligned_color", None)
            depth = getattr(self, "frozen_depth_frame", None)
            colors = self._extract_object_colors(
                self.selected_object, subsample=subsample,
                aligned_color=aligned_color, depth=depth,
                display_depth=display_depth,
            )
            if colors is not None and len(colors) == len(arr):
                save_kwargs["colors"] = colors

            np.savez_compressed(out_path, **save_kwargs)
            has_colors = "colors" in save_kwargs
            print(f"✓ Point cloud saved: {out_path} ({arr.shape[0]} points, rgb={'yes' if has_colors else 'no'})")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Point cloud saved: {out_path.name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to save point cloud: {ex}")

    def _export_full_pointcloud(
        self, e=None, subsample: int = 1, to_meters: bool = True
    ):
        """Export the full depth frame as a compressed .npz containing points (X,Y,Z) in meters when available.

        This exports all non-zero depth pixels (optionally subsampled) from the current frozen depth frame (if frozen)
        or the latest depth frame from the image processor.
        """
        import time
        from pathlib import Path

        import numpy as np

        # Choose depth frame: prefer frozen depth frame if video is frozen
        depth = None
        if (
            getattr(self, "video_frozen", False)
            and getattr(self, "frozen_depth_frame", None) is not None
        ):
            depth = self.frozen_depth_frame.copy()
        else:
            depth = (
                getattr(self.image_processor, "depth_frame", None)
                if getattr(self, "image_processor", None)
                else None
            )

        if depth is None:
            print("No depth frame available to export")
            if hasattr(self, "status_text"):
                self.status_text.value = "No depth frame available to export"
                self.page.update()
            return

        h, w = depth.shape[:2]

        # Get all non-zero depth pixels
        ys, xs = np.nonzero(depth)
        if subsample > 1:
            ys = ys[::subsample]
            xs = xs[::subsample]

        depths = depth[ys, xs]

        points_list = []
        use_realsense = getattr(
            self.image_processor, "use_realsense", False
        ) and getattr(self.image_processor, "rs_camera", None)
        intr = None
        rs_mod = None
        if to_meters and use_realsense:
            try:
                import pyrealsense2 as rs_mod

                profile = self.image_processor.rs_camera.profile
                depth_stream = profile.get_stream(
                    rs_mod.stream.depth
                ).as_video_stream_profile()
                intr = depth_stream.get_intrinsics()
            except Exception as e:
                intr = None
                print(f"Failed to get RealSense intrinsics: {e}")

        # Build points list (deproject if intrinsics available)
        for u, v, z in zip(xs, ys, depths):
            if z == 0:
                continue
            if to_meters and use_realsense and intr is not None:
                try:
                    pt = rs_mod.rs2_deproject_pixel_to_point(
                        intr, [int(u), int(v)], float(z) / 1000.0
                    )
                    points_list.append((float(pt[0]), float(pt[1]), float(pt[2])))
                except Exception:
                    points_list.append((int(u), int(v), int(z)))
            else:
                points_list.append((int(u), int(v), int(z)))

        arr = np.array(points_list)
        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_full_{timestamp}.npz"
        try:
            # Extract RGB colors from aligned color frame (same 848x480 grid as depth)
            save_kwargs = {"points": arr}
            aligned_color = None
            if getattr(self, "video_frozen", False):
                aligned_color = getattr(self, "frozen_aligned_color", None)
            else:
                aligned_color = getattr(self.image_processor, "_last_aligned_color", None) if getattr(self, "image_processor", None) else None

            if aligned_color is not None:
                # xs, ys are in depth coordinates; filter to valid (z > 0) same as points_list
                valid = depths > 0
                xs_valid = xs[valid]
                ys_valid = ys[valid]
                colors_bgr = aligned_color[ys_valid, xs_valid]
                colors_rgb = colors_bgr[:, ::-1].copy()
                if len(colors_rgb) == len(arr):
                    save_kwargs["colors"] = colors_rgb

            np.savez_compressed(out_path, **save_kwargs)
            has_colors = "colors" in save_kwargs
            print(f"✓ Full point cloud saved: {out_path} ({arr.shape[0]} points, rgb={'yes' if has_colors else 'no'})")
            if hasattr(self, "status_text"):
                self.status_text.value = f"Full point cloud saved: {out_path.name}"
                self.page.update()
        except Exception as ex:
            print(f"Failed to save full point cloud: {ex}")

    def _export_selected_object_ply(self, e=None, subsample: int = 4):
        """Export selected object's point cloud to PLY (XYZ in meters when available)."""
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

        out_dir = Path("logs/pointclouds")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"pointcloud_obj{self.selected_object + 1}_{timestamp}.ply"

        try:
            with open(out_path, "w") as f:
                f.write("ply\nformat ascii 1.0\n")
                f.write(f"element vertex {arr.shape[0]}\n")
                f.write("property float x\nproperty float y\nproperty float z\n")
                f.write("end_header\n")
                for x, y, z in arr:
                    f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")

            print(f"✓ PLY saved: {out_path} ({arr.shape[0]} points)")
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

    def _preview_selected_object_ply(self, e=None):
        """Preview the last exported PLY file using Cloudview.py as a subprocess."""
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

        # Resolve Cloudview script path
        cwd = Path.cwd()
        cloudview_candidate = cwd / "Cloudview.py"
        if not cloudview_candidate.exists():
            # Try to locate Cloudview anywhere in repo
            import glob

            matches = glob.glob("**/Cloudview.py", recursive=True)
            if matches:
                cloudview_candidate = Path(matches[0])
            else:
                print("Cloudview.py not found in repo - cannot preview")
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
