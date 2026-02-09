#!/usr/bin/env python3
"""
Download and prepare test point clouds for object analysis validation.

Sources:
- YCB Objects: Downloaded as .tgz archives from the YCB benchmark site
- Open3D builtins: Stanford Bunny for "irregular" ground truth
- Procedural primitives: Generated cylinder, box, sphere for reliable ground truth

Usage:
    python scripts/download_test_pointclouds.py
"""

import json
import os
import sys
import tarfile
import tempfile
import urllib.request

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "test_data")
YCB_DIR = os.path.join(TEST_DATA_DIR, "ycb")
PRIMITIVES_DIR = os.path.join(TEST_DATA_DIR, "primitives")

# YCB objects to download with expected shape classifications
YCB_OBJECTS = {
    "025_mug": "cylinder",
    "006_mustard_bottle": "cylinder",
    "003_cracker_box": "box",
    "004_sugar_box": "box",
    "055_baseball": "sphere",
    "036_wood_block": "box",
}

# YCB files are .tgz archives, not raw .ply
YCB_BASE_URL = "http://ycb-benchmarks.s3-website-us-east-1.amazonaws.com/data/google"


def download_file(url: str, dest: str) -> bool:
    """Download a file with progress reporting."""
    try:
        print(f"  Downloading {os.path.basename(dest)}...")
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"  Failed to download {url}: {e}")
        return False


def extract_mesh_from_tgz(tgz_path: str) -> str | None:
    """Extract the nontextured.ply mesh from a YCB .tgz archive. Returns path to extracted file."""
    try:
        with tarfile.open(tgz_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith("nontextured.ply"):
                    # Extract to a temp location
                    extracted = tar.extractfile(member)
                    if extracted:
                        tmp_path = tgz_path.replace(".tgz", "_mesh.ply")
                        with open(tmp_path, "wb") as f:
                            f.write(extracted.read())
                        return tmp_path
    except Exception as e:
        print(f"  Failed to extract mesh from {tgz_path}: {e}")
    return None


def download_ycb_objects():
    """Download YCB object meshes and convert to point clouds."""
    os.makedirs(YCB_DIR, exist_ok=True)

    try:
        import open3d as o3d
    except ImportError:
        print("ERROR: open3d is required. Install with: pip install open3d")
        return 0

    success_count = 0
    for obj_name, expected_shape in YCB_OBJECTS.items():
        ply_path = os.path.join(YCB_DIR, f"{obj_name}.ply")
        if os.path.exists(ply_path):
            print(f"  {obj_name}: already exists, skipping")
            success_count += 1
            continue

        # YCB files are .tgz archives, try google_16k first (smaller), then google_512k
        downloaded = False
        for resolution in ["google_16k", "google_512k"]:
            tgz_url = f"{YCB_BASE_URL}/{obj_name}_{resolution}.tgz"
            tgz_path = os.path.join(YCB_DIR, f"{obj_name}_{resolution}.tgz")

            if download_file(tgz_url, tgz_path):
                mesh_path = extract_mesh_from_tgz(tgz_path)
                if mesh_path:
                    try:
                        mesh = o3d.io.read_triangle_mesh(mesh_path)
                        if len(mesh.vertices) > 0:
                            pcd = mesh.sample_points_uniformly(number_of_points=5000)
                            o3d.io.write_point_cloud(ply_path, pcd)
                            print(
                                f"  {obj_name}: converted to point cloud "
                                f"({len(pcd.points)} points, {resolution})"
                            )
                            success_count += 1
                            downloaded = True
                        else:
                            print(f"  {obj_name}: empty mesh from {resolution}")
                    except Exception as e:
                        print(f"  {obj_name}: mesh conversion failed: {e}")
                    finally:
                        # Clean up temp files
                        if os.path.exists(mesh_path):
                            os.remove(mesh_path)

                # Clean up .tgz
                if os.path.exists(tgz_path):
                    os.remove(tgz_path)

                if downloaded:
                    break
            else:
                # Clean up partial download
                if os.path.exists(tgz_path):
                    os.remove(tgz_path)

        if not downloaded:
            print(f"  {obj_name}: all download attempts failed")

    return success_count


def generate_primitives():
    """Generate procedural primitive shapes as reliable ground truth."""
    try:
        import open3d as o3d
    except ImportError:
        print("ERROR: open3d is required")
        return 0

    os.makedirs(PRIMITIVES_DIR, exist_ok=True)
    count = 0

    # Cylinder: radius=0.03m, height=0.10m (like a small can)
    cyl_path = os.path.join(PRIMITIVES_DIR, "cylinder.ply")
    if not os.path.exists(cyl_path):
        mesh = o3d.geometry.TriangleMesh.create_cylinder(radius=0.03, height=0.10)
        mesh.compute_vertex_normals()
        pcd = mesh.sample_points_uniformly(number_of_points=5000)
        o3d.io.write_point_cloud(cyl_path, pcd)
        print(f"  cylinder: generated ({len(pcd.points)} points)")
    else:
        print("  cylinder: already exists, skipping")
    count += 1

    # Box: 0.06 x 0.04 x 0.08m (like a small box)
    box_path = os.path.join(PRIMITIVES_DIR, "box.ply")
    if not os.path.exists(box_path):
        mesh = o3d.geometry.TriangleMesh.create_box(width=0.06, height=0.04, depth=0.08)
        mesh.compute_vertex_normals()
        # Center the box at origin
        mesh.translate(-mesh.get_center())
        pcd = mesh.sample_points_uniformly(number_of_points=5000)
        o3d.io.write_point_cloud(box_path, pcd)
        print(f"  box: generated ({len(pcd.points)} points)")
    else:
        print("  box: already exists, skipping")
    count += 1

    # Sphere: radius=0.035m (like a tennis ball)
    sphere_path = os.path.join(PRIMITIVES_DIR, "sphere.ply")
    if not os.path.exists(sphere_path):
        mesh = o3d.geometry.TriangleMesh.create_sphere(radius=0.035)
        mesh.compute_vertex_normals()
        pcd = mesh.sample_points_uniformly(number_of_points=5000)
        o3d.io.write_point_cloud(sphere_path, pcd)
        print(f"  sphere: generated ({len(pcd.points)} points)")
    else:
        print("  sphere: already exists, skipping")
    count += 1

    return count


def generate_bunny():
    """Generate Stanford Bunny point cloud from Open3D builtins."""
    try:
        import open3d as o3d
    except ImportError:
        print("ERROR: open3d is required")
        return False

    bunny_dir = os.path.join(TEST_DATA_DIR, "builtins")
    os.makedirs(bunny_dir, exist_ok=True)

    bunny_path = os.path.join(bunny_dir, "bunny.ply")
    if os.path.exists(bunny_path):
        print("  bunny: already exists, skipping")
        return True

    try:
        bunny_data = o3d.data.BunnyMesh()
        mesh = o3d.io.read_triangle_mesh(bunny_data.path)
        pcd = mesh.sample_points_uniformly(number_of_points=5000)
        o3d.io.write_point_cloud(bunny_path, pcd)
        print(f"  bunny: generated ({len(pcd.points)} points)")
        return True
    except Exception as e:
        print(f"  bunny: failed to generate: {e}")
        return False


def create_manifest():
    """Create manifest.json mapping each file to its expected shape."""
    manifest = {}

    # YCB objects
    for obj_name, expected_shape in YCB_OBJECTS.items():
        ply_path = os.path.join("ycb", f"{obj_name}.ply")
        full_path = os.path.join(TEST_DATA_DIR, ply_path)
        if os.path.exists(full_path):
            manifest[ply_path] = {
                "expected_shape": expected_shape,
                "source": "ycb",
                "name": obj_name,
            }

    # Primitives
    for name, expected_shape in [
        ("cylinder", "cylinder"),
        ("box", "box"),
        ("sphere", "sphere"),
    ]:
        ply_path = os.path.join("primitives", f"{name}.ply")
        full_path = os.path.join(TEST_DATA_DIR, ply_path)
        if os.path.exists(full_path):
            manifest[ply_path] = {
                "expected_shape": expected_shape,
                "source": "procedural",
                "name": name,
            }

    # Bunny
    bunny_path = os.path.join("builtins", "bunny.ply")
    full_bunny = os.path.join(TEST_DATA_DIR, bunny_path)
    if os.path.exists(full_bunny):
        manifest[bunny_path] = {
            "expected_shape": "irregular",
            "source": "open3d_builtin",
            "name": "stanford_bunny",
        }

    manifest_path = os.path.join(TEST_DATA_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest created with {len(manifest)} entries: {manifest_path}")
    return manifest


def main():
    print("=" * 60)
    print("Download Test Point Clouds for Object Analysis")
    print("=" * 60)

    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    print("\n1. Procedural Primitives (reliable shape ground truth)")
    prim_count = generate_primitives()

    print("\n2. Open3D Builtins (irregular shape ground truth)")
    generate_bunny()

    print("\n3. YCB Objects (real-world shape ground truth)")
    ycb_count = download_ycb_objects()

    print("\n4. Creating manifest")
    manifest = create_manifest()

    print("\nDone! Test data is in:", os.path.abspath(TEST_DATA_DIR))
    print(f"Available test files: {len(manifest)}")
    for path, info in manifest.items():
        print(f"  {path}: expected={info['expected_shape']}")

    if ycb_count == 0 and prim_count > 0:
        print(
            "\nNote: YCB downloads failed but procedural primitives are available."
            "\nYou can still test shape estimation with the primitives and bunny."
        )


if __name__ == "__main__":
    main()
