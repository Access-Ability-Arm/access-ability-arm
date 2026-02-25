"""Debug checkerboard detection for RealSense camera.

This script helps diagnose why checkerboard detection fails by:
  - Showing live color and grayscale images
  - Attempting detection with different pattern sizes
  - Displaying image contrast and quality metrics
  - Showing OpenCV's corner detection visualization

Usage:
  python scripts/debug_checkerboard.py [--checkerboard 9 6]

Controls:
  's' - Save frame (for analysis)
  'c' - Try to detect with specified pattern
  't' - Auto-trial different pattern sizes
  'h' - Show histogram (contrast)
  'q' - Quit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except Exception:  # pragma: no cover
    rs = None


def detect_checkerboard_verbose(image: np.ndarray, pattern_size: tuple[int, int]) -> bool:
    """Try to detect checkerboard and print debug info."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)

    if ret:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        print(f"  ✓ DETECTED {pattern_size}: {len(corners)} corners")
        return True
    else:
        print(f"  ✗ Not detected {pattern_size}")
        return False


def compute_image_quality(image: np.ndarray) -> dict:
    """Compute sharpness, contrast, brightness metrics."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Sharpness (Laplacian variance) - higher is sharper
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Contrast (standard deviation) - higher is more contrast
    contrast = gray.std()

    # Brightness (mean)
    brightness = gray.mean()

    # Histogram spread
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist_spread = np.std(hist)

    return {
        "sharpness": laplacian_var,
        "contrast": contrast,
        "brightness": brightness,
        "hist_spread": hist_spread,
    }


def debug_interactive(pattern_size: tuple[int, int] = (9, 6)):
    """Interactive debug mode."""
    if rs is None:
        print("pyrealsense2 not available.")
        return 1

    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
    cfg.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30)

    profile = pipeline.start(cfg)

    try:
        print("\n=== Checkerboard Detection Debug ===")
        print(f"Default pattern size: {pattern_size}")
        print("\nControls:")
        print("  's' - Save current frame")
        print("  'c' - Try to detect with default pattern")
        print("  't' - Auto-trial pattern sizes")
        print("  'h' - Show histogram")
        print("  'q' - Quit\n")

        frame_count = 0

        while True:
            frames = pipeline.wait_for_frames(timeout_ms=1000)
            color_frame = frames.get_color_frame()

            if not color_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            gray_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

            frame_count += 1

            # Create side-by-side display
            h, w = color_image.shape[:2]
            gray_bgr = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
            display = np.hstack([color_image, gray_bgr])

            # Add status text
            quality = compute_image_quality(color_image)
            status_text = (
                f"Frame {frame_count} | Sharpness: {quality['sharpness']:.1f} | "
                f"Contrast: {quality['contrast']:.1f} | Brightness: {quality['brightness']:.1f}"
            )
            cv2.putText(
                display,
                status_text,
                (30, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                display,
                "s=save, c=detect, t=trial, h=hist, q=quit",
                (30, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            cv2.imshow("Debug: Color (left) | Grayscale (right)", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("s"):
                filename = f"debug_frame_{frame_count}.png"
                cv2.imwrite(filename, color_image)
                print(f"Saved frame to {filename}")

            elif key == ord("c"):
                print(f"\nAttempting detection with pattern {pattern_size}...")
                detect_checkerboard_verbose(color_image, pattern_size)

            elif key == ord("t"):
                print(f"\nAuto-trying different pattern sizes:")
                for rows in [5, 6, 7, 8, 9]:
                    for cols in [6, 7, 8, 9, 10]:
                        detect_checkerboard_verbose(color_image, (cols, rows))

            elif key == ord("h"):
                print(f"\nImage quality metrics:")
                quality = compute_image_quality(color_image)
                for metric, value in quality.items():
                    print(f"  {metric}: {value:.2f}")

                # Show histogram
                hist = cv2.calcHist([gray_image], [0], None, [256], [0, 256])
                hist_display = np.zeros((200, 256, 3), dtype=np.uint8)
                cv2.normalize(hist, hist, 0, 200, cv2.NORM_MINMAX)
                for i in range(256):
                    cv2.line(
                        hist_display,
                        (i, 200),
                        (i, 200 - int(hist[i][0])),
                        (0, 255, 0),
                        1,
                    )
                cv2.imshow("Histogram (intensity distribution)", hist_display)
                print("  Histogram displayed in separate window.")

        cv2.destroyAllWindows()
        return 0

    finally:
        pipeline.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Debug checkerboard detection")
    parser.add_argument(
        "--checkerboard",
        nargs=2,
        type=int,
        default=[9, 6],
        help="Checkerboard pattern size (cols rows)",
    )
    args = parser.parse_args(argv)

    return debug_interactive(pattern_size=tuple(args.checkerboard))


if __name__ == "__main__":
    sys.exit(main())
