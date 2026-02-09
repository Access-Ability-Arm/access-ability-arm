"""
Simple point cloud viewer for exported .npz files created by the GUI.

Behavior:
- If a filename is provided on the command line, it loads that file.
- Otherwise it picks the most recent file under `logs/pointclouds`.
- It attempts to use Open3D for interactive 3D viewing; if Open3D is not
  available it falls back to a Matplotlib 3D scatter (slower, less interactive).

Usage:
    python Cloudview.py [path/to/pointcloud.npz]

"""

import argparse
import glob
import os
from pathlib import Path

import numpy as np


def find_latest_pointcloud(search_dir: str = "logs/pointclouds") -> str:
    p = Path(search_dir)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {search_dir}")
    files = sorted(p.glob("*.npz"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No .npz pointcloud files found in: {search_dir}")
    return str(files[0])


def load_points(path: str) -> np.ndarray:
    data = np.load(path)
    # Try to retrieve 'points' otherwise use first array
    if "points" in data:
        pts = data["points"]
    else:
        # Pick the first item in the archive
        keys = list(data.keys())
        if not keys:
            raise ValueError("No arrays found in the .npz file")
        pts = data[keys[0]]
    pts = np.asarray(pts, dtype=float)
    if pts.ndim != 2 or pts.shape[1] not in (2, 3):
        raise ValueError(f"Unsupported point array shape: {pts.shape}")

    if pts.shape[1] == 3:
        # Filter out invalid depth (0 or sensor max 65535)
        valid = (pts[:, 2] > 0) & (pts[:, 2] < 65535)
        removed = len(pts) - valid.sum()
        pts = pts[valid]
        if removed > 0:
            print(f"  Filtered {removed} invalid depth points")

        # Detect pixel+mm format: X/Y in pixel range, Z in mm range
        # Heuristic: if X max < 2000 and Z min > 100, it's (px, py, depth_mm)
        if pts[:, 0].max() < 2000 and pts[:, 2].min() > 50:
            print("  Detected pixel+depth_mm format, converting to pseudo-3D...")
            # Convert to a viewable 3D representation:
            # Use default D435 intrinsics at 848x480 to deproject
            fx, fy = 425.19, 425.19
            cx, cy = 423.86, 239.87
            z_m = pts[:, 2] / 1000.0  # mm -> meters
            x_m = (pts[:, 0] - cx) * z_m / fx
            y_m = (pts[:, 1] - cy) * z_m / fy
            pts = np.column_stack([x_m, y_m, z_m])
            print(f"  Deprojected to meters: {len(pts)} points")

    return pts


def view_with_open3d(points: np.ndarray, path: str = None):
    from pathlib import Path

    import open3d as o3d

    # If points are (x,y,depth_mm) with integer depth, just use them as (x,y,z)
    pts = points.astype(float)
    if pts.shape[1] == 2:
        z = np.zeros((pts.shape[0], 1), dtype=float)
        pts = np.hstack([pts, z])

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)

    # Simple color by Z value for visualization
    zvals = np.asarray(pcd.points)[:, 2]
    znorm = (zvals - zvals.min()) / (np.ptp(zvals) + 1e-9)
    colors = plt_cm_viridis(znorm)
    pcd.colors = o3d.utility.Vector3dVector(colors[:, :3])

    # Window title with filename when provided
    window_name = f"Point Cloud - {Path(path).name}" if path else "Point Cloud"

    # Use explicit VisualizerWithKeyCallback to enable keyboard shortcuts
    vis = o3d.visualization.VisualizerWithKeyCallback()
    vis.create_window(window_name=window_name)
    vis.add_geometry(pcd)
    vis.poll_events()
    vis.update_renderer()

    # Helper operations for camera control
    def _get_vc():
        return vis.get_view_control()

    def _reset_view(vis_obj=None):
        ctr = _get_vc()
        bbox = pcd.get_axis_aligned_bounding_box()
        center = bbox.get_center()
        ctr.set_lookat(center)
        # sensible default: look from +Z towards origin
        ctr.set_front(np.array([0.0, 0.0, -1.0]))
        ctr.set_up(np.array([0.0, -1.0, 0.0]))
        try:
            ctr.set_zoom(0.7)
        except Exception:
            pass
        print("[Cloudview] Reset view")
        return False

    def _align_axis(axis):
        def _fn(vis_obj=None):
            ctr = _get_vc()
            bbox = pcd.get_axis_aligned_bounding_box()
            center = bbox.get_center()
            ctr.set_lookat(center)
            if axis == "X":
                ctr.set_front(np.array([1.0, 0.0, 0.0]))
                ctr.set_up(np.array([0.0, 0.0, 1.0]))
            elif axis == "Y":
                ctr.set_front(np.array([0.0, 1.0, 0.0]))
                ctr.set_up(np.array([0.0, 0.0, 1.0]))
            elif axis == "Z":
                ctr.set_front(np.array([0.0, 0.0, 1.0]))
                ctr.set_up(np.array([0.0, -1.0, 0.0]))
            try:
                ctr.set_zoom(0.7)
            except Exception:
                pass
            print(f"[Cloudview] Aligned to {axis}-axis")
            return False

        return _fn

    def _rotate(vis_obj=None, yaw_deg=0.0, pitch_deg=0.0):
        ctr = _get_vc()
        front = np.array(ctr.get_front())
        up = np.array(ctr.get_up())
        lookat = np.array(ctr.get_lookat())

        # Compute right vector
        right = np.cross(front, up)
        right = right / (np.linalg.norm(right) + 1e-9)

        # Rotate front around given axes by small angles
        def _rot(v, axis, ang_rad):
            axis = axis / (np.linalg.norm(axis) + 1e-9)
            c = np.cos(ang_rad)
            s = np.sin(ang_rad)
            return v * c + np.cross(axis, v) * s + axis * (np.dot(axis, v) * (1 - c))

        new_front = front.copy()
        if yaw_deg:
            new_front = _rot(new_front, up, np.radians(yaw_deg))
        if pitch_deg:
            new_front = _rot(new_front, right, np.radians(pitch_deg))

        new_front = new_front / (np.linalg.norm(new_front) + 1e-9)
        # Keep same up vector (re-orthonormalize)
        new_up = np.cross(right, new_front)
        new_up = new_up / (np.linalg.norm(new_up) + 1e-9)

        ctr.set_front(new_front)
        ctr.set_up(new_up)
        print(f"[Cloudview] Rotated yaw={yaw_deg} pitch={pitch_deg}")
        return False

    def _zoom(vis_obj=None, factor=1.1):
        ctr = _get_vc()
        try:
            z = ctr.get_zoom()
            ctr.set_zoom(z * factor)
            print(f"[Cloudview] Zoom set: {z * factor:.3f}")
        except Exception:
            pass
        return False

    def _fit(vis_obj=None):
        ctr = _get_vc()
        bbox = pcd.get_axis_aligned_bounding_box()
        center = bbox.get_center()
        ctr.set_lookat(center)
        try:
            ctr.set_zoom(0.8)
        except Exception:
            pass
        print("[Cloudview] Fit to center")
        return False

    # Register key callbacks (letters)
    vis.register_key_callback(ord("R"), _reset_view)
    vis.register_key_callback(ord("X"), _align_axis("X"))
    vis.register_key_callback(ord("Y"), _align_axis("Y"))
    vis.register_key_callback(ord("Z"), _align_axis("Z"))
    vis.register_key_callback(
        ord("A"), lambda vis_obj=None: _rotate(vis_obj, yaw_deg=-10.0)
    )
    vis.register_key_callback(
        ord("D"), lambda vis_obj=None: _rotate(vis_obj, yaw_deg=10.0)
    )
    # Map U/J for up/down rotation to avoid common conflicts (e.g., S/X used elsewhere)
    vis.register_key_callback(
        ord("U"), lambda vis_obj=None: _rotate(vis_obj, pitch_deg=10.0)
    )
    vis.register_key_callback(
        ord("u"), lambda vis_obj=None: _rotate(vis_obj, pitch_deg=10.0)
    )
    vis.register_key_callback(
        ord("J"), lambda vis_obj=None: _rotate(vis_obj, pitch_deg=-10.0)
    )
    vis.register_key_callback(
        ord("j"), lambda vis_obj=None: _rotate(vis_obj, pitch_deg=-10.0)
    )
    vis.register_key_callback(ord("+"), lambda vis_obj=None: _zoom(vis_obj, 0.8))
    vis.register_key_callback(ord("="), lambda vis_obj=None: _zoom(vis_obj, 0.8))
    vis.register_key_callback(ord("-"), lambda vis_obj=None: _zoom(vis_obj, 1.25))
    vis.register_key_callback(ord("F"), _fit)

    # Attempt to register arrow key codes (GLFW codes) for convenience
    try:
        # Right = 262, Left = 263, Down = 264, Up = 265
        vis.register_key_callback(
            262, lambda vis_obj=None: _rotate(vis_obj, yaw_deg=10.0)
        )
        vis.register_key_callback(
            263, lambda vis_obj=None: _rotate(vis_obj, yaw_deg=-10.0)
        )
        vis.register_key_callback(
            265, lambda vis_obj=None: _rotate(vis_obj, pitch_deg=10.0)
        )
        vis.register_key_callback(
            264, lambda vis_obj=None: _rotate(vis_obj, pitch_deg=-10.0)
        )
    except Exception:
        pass

    # Help overlay lines
    help_lines = [
        "R: Reset view",
        "X / Y / Z: Align axes",
        "A / D: Rotate left / right",
        "U / J: Rotate up / down",
        "+ / -: Zoom in / out",
        "F: Fit to center",
        "H: Toggle help overlay",
    ]

    show_help = False
    help_label_positions = []

    def _toggle_help(vis_obj=None):
        nonlocal show_help, help_label_positions
        show_help = not show_help
        bbox = pcd.get_axis_aligned_bounding_box()
        extent = bbox.get_extent()
        base = bbox.get_max_bound() + np.array([0.0, 0.0, extent[2] * 0.03])
        try:
            if show_help:
                # Attempt to add small 3D labels for each help line
                help_label_positions = []
                for i, line in enumerate(help_lines):
                    pos = base + np.array([0.0, 0.0, i * extent[2] * 0.03])
                    try:
                        vis.add_3d_label(pos, line)
                        help_label_positions.append(pos)
                    except Exception:
                        # add_3d_label may not exist on some Open3D builds
                        pass
                print("[Cloudview] Help overlay ON")
                print("\n".join(help_lines))
            else:
                # Try to clear 3d labels if supported
                try:
                    vis.clear_3d_labels()
                except Exception:
                    # Fallback: cannot clear; just notify
                    pass
                print("[Cloudview] Help overlay OFF")
        except Exception as ex:
            print(f"[Cloudview] Help toggle failed: {ex}")
        return False

    # Register H to toggle help overlay
    vis.register_key_callback(ord("H"), _toggle_help)

    print(
        "Keyboard shortcuts: R=reset, X/Y/Z=align axis, A/D=rotate left/right, U/J=rotate up/down, +/-=zoom, F=fit, H=help"
    )

    vis.run()
    vis.destroy_window()


def view_with_matplotlib(
    points: np.ndarray, max_points: int = 200000, path: str = None
):
    from pathlib import Path

    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    pts = points.astype(float)
    if pts.shape[1] == 2:
        # Treat as (x, y) + zero z
        z = np.zeros((pts.shape[0], 1), dtype=float)
        pts = np.hstack([pts, z])

    # Subsample if huge
    if pts.shape[0] > max_points:
        idx = np.random.choice(pts.shape[0], max_points, replace=False)
        pts = pts[idx]

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    sc = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], c=pts[:, 2], cmap="viridis", s=1)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    plt.colorbar(sc, ax=ax, label="Z")
    title = f"Point Cloud - {Path(path).name}" if path else "Point Cloud"
    plt.title(title)

    # Create help overlay text box (toggleable with 'h')
    help_text = "\n".join(
        [
            "R: Reset view",
            "X/Y/Z: Align axes",
            "A/D: Rotate left/right",
            "U/J: Rotate up/down",
            "+/-: Zoom in/out",
            "F: Fit to center",
            "H: Toggle help overlay",
        ]
    )

    help_box = fig.text(
        0.02,
        0.98,
        help_text,
        fontsize=9,
        va="top",
        ha="left",
        bbox=dict(facecolor="white", alpha=0.75),
    )

    # Key handler for matplotlib viewer
    def on_key(event):
        azim = ax.azim
        elev = ax.elev

        def set_view(e, a):
            ax.view_init(elev=e, azim=a)
            fig.canvas.draw_idle()

        key = event.key
        if not key:
            return

        if key.lower() == "r":
            # Reset view
            set_view(20, 45)
            print("[Cloudview] Reset view (matplotlib)")
        elif key.lower() == "x":
            set_view(0, 0)
            print("[Cloudview] Aligned to X (matplotlib)")
        elif key.lower() == "y":
            set_view(0, 90)
            print("[Cloudview] Aligned to Y (matplotlib)")
        elif key.lower() == "z":
            set_view(90, -90)
            print("[Cloudview] Aligned to Z (matplotlib)")
        elif key.lower() in ("a", "left"):
            set_view(elev, azim - 10)
        elif key.lower() in ("d", "right"):
            set_view(elev, azim + 10)
        elif key.lower() in ("u", "up"):
            set_view(elev + 10, azim)
        elif key.lower() in ("j", "down"):
            set_view(elev - 10, azim)
        elif key in ("+", "="):
            # Zoom in by shrinking axis ranges around center
            def zoom(factor):
                for axis_get, axis_set in (
                    (ax.get_xlim3d, ax.set_xlim3d),
                    (ax.get_ylim3d, ax.set_ylim3d),
                    (ax.get_zlim3d, ax.set_zlim3d),
                ):
                    mn, mx = axis_get()
                    c = 0.5 * (mn + mx)
                    half = 0.5 * (mx - mn) * factor
                    axis_set((c - half, c + half))
                fig.canvas.draw_idle()

            zoom(0.8)
        elif key == "-":

            def zoom_out(factor=1.25):
                for axis_get, axis_set in (
                    (ax.get_xlim3d, ax.set_xlim3d),
                    (ax.get_ylim3d, ax.set_ylim3d),
                    (ax.get_zlim3d, ax.set_zlim3d),
                ):
                    mn, mx = axis_get()
                    c = 0.5 * (mn + mx)
                    half = 0.5 * (mx - mn) * factor
                    axis_set((c - half, c + half))
                fig.canvas.draw_idle()

            zoom_out()
        elif key.lower() == "f":
            # Fit to center by computing data bounds
            xmin, xmax = pts[:, 0].min(), pts[:, 0].max()
            ymin, ymax = pts[:, 1].min(), pts[:, 1].max()
            zmin, zmax = pts[:, 2].min(), pts[:, 2].max()
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
            ax.set_zlim(zmin, zmax)
            set_view(20, 45)
            print("[Cloudview] Fit to center (matplotlib)")
        elif key.lower() == "h":
            # Toggle help box visibility
            help_box.set_visible(not help_box.get_visible())
            fig.canvas.draw_idle()
            print(
                f"[Cloudview] Help overlay {'ON' if help_box.get_visible() else 'OFF'} (matplotlib)"
            )

    fig.canvas.mpl_connect("key_press_event", on_key)

    print(
        "Keyboard shortcuts (matplotlib): R=reset, X/Y/Z=align, A/D/U/J or arrow keys=rotate, +/-=zoom, F=fit, H=help"
    )
    plt.show()


# Small helper for Open3D coloring using matplotlib colormap (without importing full pyplot)
def plt_cm_viridis(arr):
    import matplotlib
    import numpy as np

    cmap = matplotlib.colormaps["viridis"]
    return cmap(np.clip(arr, 0.0, 1.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", help="Path to .npz pointcloud file")
    parser.add_argument(
        "--no-open3d", action="store_true", help="Force matplotlib viewer"
    )
    parser.add_argument(
        "--subsample",
        type=int,
        default=4,
        help="Subsample factor for dense clouds (matplotlib viewer)",
    )
    args = parser.parse_args()

    try:
        if args.path:
            path = args.path
        else:
            path = find_latest_pointcloud()
        print(f"Loading: {path}")
        points = load_points(path)
        print(f"Loaded {points.shape[0]} points (shape={points.shape})")
        print(
            f"  X range: [{points[:, 0].min():.4f}, {points[:, 0].max():.4f}]"
            f"  Y range: [{points[:, 1].min():.4f}, {points[:, 1].max():.4f}]"
            f"  Z range: [{points[:, 2].min():.4f}, {points[:, 2].max():.4f}]"
        )

        # Try Open3D unless disabled
        if not args.no_open3d:
            try:
                import open3d

                # Use Open3D viewer
                view_with_open3d(points, path=path)
                return
            except Exception as e:
                print(
                    f"Open3D viewer unavailable or failed: {e}\nFalling back to matplotlib"
                )

        view_with_matplotlib(
            points, max_points=200000 // max(1, args.subsample), path=path
        )

    except Exception as ex:
        print(f"Error: {ex}")


if __name__ == "__main__":
    main()
