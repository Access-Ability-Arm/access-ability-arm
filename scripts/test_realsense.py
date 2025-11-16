#!/usr/bin/env python3
"""
Simple RealSense camera test script
Displays camera info and captures a single frame
"""
import pyrealsense2 as rs
import numpy as np

def test_realsense():
    # Try to stream directly (bypasses device enumeration issues on macOS)
    print("Attempting to start streaming...")
    pipeline = rs.pipeline()
    config = rs.config()

    # Configure streams
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

    try:
        # Start streaming
        profile = pipeline.start(config)
        print("✓ Streaming started successfully!")

        # Get device info after pipeline starts (works better on macOS)
        device = profile.get_device()
        print(f"\nConnected to: {device.get_info(rs.camera_info.name)}")
        print(f"Serial Number: {device.get_info(rs.camera_info.serial_number)}")
        print(f"Firmware: {device.get_info(rs.camera_info.firmware_version)}")

        # Capture a few frames
        print("\nCapturing frames...")
        for i in range(5):
            frames = pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()

            if depth_frame and color_frame:
                print(f"  Frame {i+1}: Color {color_frame.get_width()}x{color_frame.get_height()}, "
                      f"Depth {depth_frame.get_width()}x{depth_frame.get_height()}")

        print("\n✓ Camera is working correctly!")
        print("\nYou can now integrate RealSense into your Access Ability Arm project.")

    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure your RealSense camera is connected via USB")
        print("  2. Try unplugging and replugging the camera")
        print("  3. Check System Settings > Privacy & Security > Camera permissions")
        return False
    finally:
        try:
            pipeline.stop()
            print("\nStopped streaming.")
        except:
            pass

    return True

if __name__ == "__main__":
    print("RealSense Camera Test")
    print("=" * 50)
    test_realsense()
