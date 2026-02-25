"""
Camera calibration utilities for depth-to-color frame alignment.

This module handles loading and applying camera extrinsic calibration
that maps depth camera coordinates to color camera coordinates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class CameraCalibration:
    """Depth-to-color camera extrinsic calibration."""

    # Intrinsics
    depth_intrinsics: dict
    color_intrinsics: dict
    
    # Extrinsic: rotation (3x3) and translation (3,)
    rotation_matrix: np.ndarray
    translation_vector: np.ndarray
    
    # Metadata
    reprojection_error_pixels: float
    num_captures: int = 1
    calibration_file: Optional[str] = None

    @classmethod
    def load_from_json(cls, json_file: str) -> CameraCalibration:
        """Load calibration from JSON file.
        
        Args:
            json_file: Path to calibration JSON (from calibrate_camera_extrinsic.py)
        
        Returns:
            CameraCalibration object
        
        Raises:
            FileNotFoundError: If JSON file not found
            KeyError: If required keys missing from JSON
        """
        path = Path(json_file)
        if not path.exists():
            raise FileNotFoundError(f"Calibration file not found: {json_file}")

        with open(path, "r") as f:
            data = json.load(f)

        ext = data.get("extrinsic_depth_to_color", {})
        R = np.array(ext.get("rotation_matrix", np.eye(3).tolist()))
        t = np.array(ext.get("translation_vector", [0, 0, 0]))

        return cls(
            depth_intrinsics=data.get("depth_intrinsics", {}),
            color_intrinsics=data.get("color_intrinsics", {}),
            rotation_matrix=R,
            translation_vector=t,
            reprojection_error_pixels=data.get("reprojection_error_pixels", 0.0),
            num_captures=data.get("num_captures", 1),
            calibration_file=str(path),
        )

    def transform_points(self, points: np.ndarray) -> np.ndarray:
        """Apply extrinsic transform to 3D points.
        
        Transforms points from depth camera frame to color camera frame.
        
        Args:
            points: (N, 3) array of 3D points in depth frame
        
        Returns:
            (N, 3) array of points in color frame
        """
        # p_color = R @ p_depth + t
        return (self.rotation_matrix @ points.T + self.translation_vector.reshape(3, 1)).T


def get_default_calibration_path() -> str:
    """Get default calibration file path (project root)."""
    import os
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return str(Path(workspace_root) / "calibration_extrinsic.json")


def try_load_calibration() -> Optional[CameraCalibration]:
    """Attempt to load calibration from default location.
    
    Returns:
        CameraCalibration if found and valid, None otherwise
    """
    try:
        path = get_default_calibration_path()
        return CameraCalibration.load_from_json(path)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        # Silently fail - calibration is optional
        return None
