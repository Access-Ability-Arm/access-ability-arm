#!/usr/bin/env python3
"""
Test script for ObjectAnalyzer.

Loads point clouds from files and validates shape estimation against ground truth.
Optionally visualizes results in Open3D.

Usage:
    # Test a single file
    python scripts/test_object_analysis.py --file test_data/ycb/003_cracker_box.ply

    # Test all files in manifest
    python scripts/test_object_analysis.py --all

    # Test with visualization
    python scripts/test_object_analysis.py --file test_data/ycb/025_mug.ply --visualize
"""

import argparse
import json
import os
import sys

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "test_data")


def ensure_test_data():
    """Download test point clouds if manifest is missing."""
    manifest_path = os.path.join(TEST_DATA_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        return
    print("Test data not found. Downloading...\n")
    from download_test_pointclouds import main as download_main

    download_main()
    print()


def analyze_file(file_path: str, visualize: bool = False) -> dict:
    """Run analysis on a point cloud file and return results."""
    if not os.path.exists(file_path):
        ensure_test_data()
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            sys.exit(1)

    from aaa_vision.object_analyzer import ObjectAnalyzer

    analyzer = ObjectAnalyzer()
    analysis = analyzer.analyze_from_file(file_path)

    result = {
        "file": os.path.basename(file_path),
        "shape": analysis.shape.shape_type,
        "confidence": analysis.shape.confidence,
        "dimensions": analysis.shape.dimensions,
        "centroid": analysis.centroid.tolist(),
        "grasp_point": analysis.grasp_point.tolist(),
        "grasp_width_mm": analysis.grasp_width * 1000,
        "graspable": analysis.graspable,
        "grasp_confidence": analysis.grasp_confidence,
        "num_points": analysis.num_points,
        "curvature": analysis.shape.curvature_profile,
        "table_plane": analysis.table_plane is not None,
        "top_plane": analysis.top_plane is not None,
    }

    # Print structured results
    print(f"\n{'=' * 50}")
    print(f"File: {result['file']}")
    print(f"Shape: {result['shape']} (confidence: {result['confidence']:.3f})")
    print(f"Dimensions: {result['dimensions']}")
    print(
        f"Centroid: [{result['centroid'][0]:.4f}, {result['centroid'][1]:.4f}, {result['centroid'][2]:.4f}]"
    )
    print(
        f"Grasp point: [{result['grasp_point'][0]:.4f}, {result['grasp_point'][1]:.4f}, {result['grasp_point'][2]:.4f}]"
    )
    print(f"Grasp width: {result['grasp_width_mm']:.1f}mm")
    print(f"Graspable: {result['graspable']}")
    print(f"Grasp confidence: {result['grasp_confidence']:.1%}")
    print(f"Points: {result['num_points']}")
    print(
        f"Curvature: flat={result['curvature']['flat_ratio']:.2f}, curved={result['curvature']['curved_ratio']:.2f}"
    )
    print(f"Table plane: {result['table_plane']}, Top plane: {result['top_plane']}")

    if visualize:
        _visualize_analysis(file_path, analysis)

    return result


def _visualize_analysis(file_path: str, analysis):
    """Visualize analysis results in Open3D."""
    import open3d as o3d

    geometries = []

    # Main body (green)
    if len(analysis.main_body_points) > 0:
        body_pcd = o3d.geometry.PointCloud()
        body_pcd.points = o3d.utility.Vector3dVector(analysis.main_body_points)
        body_pcd.paint_uniform_color([0, 0.8, 0])
        geometries.append(body_pcd)

    # Table plane (gray)
    if analysis.table_plane is not None and len(analysis.table_plane.inlier_points) > 0:
        table_pcd = o3d.geometry.PointCloud()
        table_pcd.points = o3d.utility.Vector3dVector(
            analysis.table_plane.inlier_points
        )
        table_pcd.paint_uniform_color([0.5, 0.5, 0.5])
        geometries.append(table_pcd)

    # Top plane (blue)
    if analysis.top_plane is not None and len(analysis.top_plane.inlier_points) > 0:
        top_pcd = o3d.geometry.PointCloud()
        top_pcd.points = o3d.utility.Vector3dVector(analysis.top_plane.inlier_points)
        top_pcd.paint_uniform_color([0, 0, 1])
        geometries.append(top_pcd)

    # Grasp point (red sphere)
    grasp_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.005)
    grasp_sphere.translate(analysis.grasp_point)
    grasp_sphere.paint_uniform_color([1, 0, 0])
    geometries.append(grasp_sphere)

    # Coordinate frame
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.05)
    geometries.append(coord_frame)

    # OBB
    if analysis.shape.oriented_bbox is not None:
        obb = analysis.shape.oriented_bbox
        obb.color = (0, 0.5, 1)
        geometries.append(obb)

    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"Analysis: {os.path.basename(file_path)} ({analysis.shape.shape_type})",
        width=1280,
        height=720,
    )


def test_all(manifest_path: str | None = None, visualize: bool = False):
    """Test all files in the manifest against ground truth."""
    ensure_test_data()
    if manifest_path is None:
        manifest_path = os.path.join(TEST_DATA_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"No manifest found at {manifest_path}")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    correct = 0
    total = 0

    manifest_dir = os.path.dirname(os.path.abspath(manifest_path))

    for rel_path, info in manifest.items():
        full_path = os.path.join(manifest_dir, rel_path)
        if not os.path.exists(full_path):
            print(f"  SKIP {rel_path} (file not found)")
            continue

        expected = info["expected_shape"]
        result = analyze_file(full_path, visualize=visualize)
        actual = result["shape"]
        total += 1

        match = actual == expected
        if match:
            correct += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"  {status}: {info['name']} expected={expected} actual={actual}")

    print(f"\n{'=' * 50}")
    print(
        f"Results: {correct}/{total} correct ({correct / total * 100:.0f}%)"
        if total > 0
        else "No files tested"
    )


def interactive_pick(visualize: bool = False):
    """Show available test files and let the user pick one."""
    ensure_test_data()

    # Collect all .ply and .npz files under test_data
    files = []
    for root, _, filenames in os.walk(TEST_DATA_DIR):
        for fn in sorted(filenames):
            if fn.endswith((".ply", ".npz")):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, TEST_DATA_DIR)
                files.append((rel, full))

    if not files:
        print("No test files found. Run: python scripts/download_test_pointclouds.py")
        return

    # Load manifest for expected shape info
    manifest = {}
    manifest_path = os.path.join(TEST_DATA_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    print(f"\nAvailable test files ({len(files)}):\n")
    for i, (rel, _) in enumerate(files, 1):
        info = manifest.get(rel, {})
        expected = info.get("expected_shape", "")
        suffix = f"  (expected: {expected})" if expected else ""
        print(f"  {i}. {rel}{suffix}")

    print(f"\n  a. Run all ({len(files)} files)")
    print(f"  q. Quit")

    while True:
        choice = input("\nSelect file number (or a/q): ").strip().lower()
        if choice == "q":
            return
        if choice == "a":
            test_all(visualize=visualize)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                analyze_file(files[idx][1], visualize=visualize)
                return
        except ValueError:
            pass
        print(f"Invalid choice. Enter 1-{len(files)}, 'a', or 'q'.")


def main():
    parser = argparse.ArgumentParser(
        description="Test ObjectAnalyzer on point cloud files"
    )
    parser.add_argument(
        "file", nargs="?", help="Path to a .ply or .npz file to analyze"
    )
    parser.add_argument(
        "--manifest", "-m", help="Path to manifest.json for batch testing"
    )
    parser.add_argument(
        "--all", "-a", action="store_true", help="Test all files in default manifest"
    )
    parser.add_argument(
        "--visualize", "-v", action="store_true", help="Show Open3D visualization"
    )
    args = parser.parse_args()

    if args.file:
        analyze_file(args.file, visualize=args.visualize)
    elif args.manifest:
        test_all(manifest_path=args.manifest, visualize=args.visualize)
    elif args.all:
        test_all(visualize=args.visualize)
    else:
        interactive_pick(visualize=args.visualize)


if __name__ == "__main__":
    main()
