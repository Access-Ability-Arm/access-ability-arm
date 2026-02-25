"""Generate and display a checkerboard pattern for calibration.

This script creates a high-contrast checkerboard that you can:
  - View on screen
  - Print and stick on a rigid surface
  - Use for camera calibration

Usage:
  python scripts/generate_checkerboard.py [--cols 9] [--rows 6] [--square-size 30]

Examples:
  python scripts/generate_checkerboard.py                    # 9x6 at 30mm/square (A4 size)
  python scripts/generate_checkerboard.py --cols 8 --rows 5 --square-size 40  # Larger squares
  python scripts/generate_checkerboard.py --output checkerboard_print.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def generate_checkerboard(
    cols: int = 9,
    rows: int = 6,
    square_size: int = 30,
    margin: int = 50,
) -> np.ndarray:
    """Generate a checkerboard pattern image.
    
    Args:
      cols: Number of squares horizontally (inner grid; final width is cols+1)
      rows: Number of squares vertically (inner grid; final height is rows+1)
      square_size: Size of each square in pixels
      margin: White margin around the board in pixels
    
    Returns:
      (height, width, 3) BGR image with checkerboard pattern
    """
    # Pattern is (rows+1) x (cols+1) squares for OpenCV compatibility
    pattern_rows = rows + 1
    pattern_cols = cols + 1

    board_height = pattern_rows * square_size
    board_width = pattern_cols * square_size

    height = board_height + 2 * margin
    width = board_width + 2 * margin

    # Create white background
    image = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Fill in black squares in checkerboard pattern
    for r in range(pattern_rows):
        for c in range(pattern_cols):
            if (r + c) % 2 == 1:  # Black square
                y_start = margin + r * square_size
                y_end = y_start + square_size
                x_start = margin + c * square_size
                x_end = x_start + square_size
                image[y_start:y_end, x_start:x_end] = 0

    return image


def print_checkerboard_info(cols: int, rows: int, square_size_mm: float):
    """Print calibration info."""
    actual_cols = cols + 1
    actual_rows = rows + 1
    width_mm = actual_cols * square_size_mm
    height_mm = actual_rows * square_size_mm
    width_in = width_mm / 25.4
    height_in = height_mm / 25.4

    print(f"\n=== Checkerboard Specifications ===")
    print(f"OpenCV detects: {cols}×{rows} inner corners")
    print(f"Pattern size: {actual_cols}×{actual_rows} squares")
    print(f"Square size: {square_size_mm}mm = {square_size_mm/10:.1f}cm")
    print(f"Total size: {width_mm}mm × {height_mm}mm ({width_in:.1f}\" × {height_in:.1f}\")")
    print(f"\nUse this for calibration:")
    print(f"  python scripts/calibrate_camera_extrinsic.py --checkerboard {cols} {rows} --square-size {square_size_mm/1000:.3f}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a printable checkerboard pattern")
    parser.add_argument("--cols", type=int, default=9, help="Number of inner corners horizontally (OpenCV pattern width)")
    parser.add_argument("--rows", type=int, default=6, help="Number of inner corners vertically (OpenCV pattern height)")
    parser.add_argument("--square-size", type=int, default=30, help="Square size in pixels (for screen display)")
    parser.add_argument(
        "--square-size-mm",
        type=float,
        help="Square size in mm (for printing). If set, overrides --square-size for info only",
    )
    parser.add_argument("--output", "-o", help="Save to file (e.g., checkerboard.png)")
    parser.add_argument("--no-display", action="store_true", help="Don't show on screen (just save)")
    args = parser.parse_args(argv)

    # Generate checkerboard
    image = generate_checkerboard(
        cols=args.cols,
        rows=args.rows,
        square_size=args.square_size,
        margin=50,
    )

    # Print info
    square_size_mm = args.square_size_mm if args.square_size_mm else args.square_size / 10 * 2.54
    print_checkerboard_info(args.cols, args.rows, square_size_mm)

    # Save if requested
    if args.output:
        cv2.imwrite(args.output, image)
        dpi = 100
        width_mm = (args.cols + 1) * square_size_mm
        height_mm = (args.rows + 1) * square_size_mm
        print(f"\nSaved to: {args.output}")
        print(f"For printing: print at 100% scale (no scaling)")
        print(f"  Standard print DPI: 300 (sharper)")
        print(f"  At 300 DPI, printed size: {width_mm/25.4:.1f}\" × {height_mm/25.4:.1f}\"")

    # Display
    if not args.no_display:
        print("\nDisplaying checkerboard (press any key to close)...")
        cv2.imshow(f"Checkerboard {args.cols}x{args.rows} - Print or use for camera calibration", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
