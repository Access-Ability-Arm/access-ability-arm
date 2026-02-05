#!/usr/bin/env python3
"""
Test Special Modes Script

Tests point mode and push mode of the SC Servo Gripper.
- Point mode: Single finger extended for pressing buttons
- Push mode: Closed gripper for pushing/sliding objects

Usage:
    python test_modes.py [--port PORT] [--id SERVO_ID]
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Test SC Servo Gripper special modes")
    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        help="Serial port (default: /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=1000000,
        help="Baudrate (default: 1000000)"
    )
    parser.add_argument(
        "--id",
        type=int,
        default=1,
        dest="servo_id",
        help="Servo ID (default: 1)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between modes in seconds (default: 2.0)"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("SC Servo Gripper - Special Modes Test")
    print("=" * 50)
    print()
    print("Testing special gripper modes:")
    print("  - Point mode: For pressing buttons/touchscreens")
    print("  - Push mode: For pushing/sliding objects")
    print()

    try:
        from aaa_gripper_driver import SCServoGripper, SDK_AVAILABLE
        if not SDK_AVAILABLE:
            print("ERROR: scservo_sdk not installed!")
            return 1
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1

    gripper = SCServoGripper(
        port=args.port,
        baudrate=args.baudrate,
        servo_id=args.servo_id
    )

    if not gripper.connect():
        print("FAILED: Could not connect to servo")
        return 1

    try:
        print("Starting modes test...")
        print("-" * 30)

        # Start from open position
        print("\n1. Starting from full open position...")
        gripper.open_full()
        pos = gripper.get_position_percent()
        print(f"   Position: {pos:.1f}%")
        time.sleep(args.delay)

        # Test point mode
        print("\n2. Entering POINT MODE...")
        print("   (Single finger extended for button pressing)")
        gripper.point_mode()
        pos = gripper.get_position_percent()
        print(f"   Position: {pos:.1f}%")
        time.sleep(args.delay)

        # Test push mode
        print("\n3. Entering PUSH MODE...")
        print("   (Gripper closed for pushing objects)")
        gripper.push_mode()
        pos = gripper.get_position_percent()
        print(f"   Position: {pos:.1f}%")
        time.sleep(args.delay)

        # Return to open
        print("\n4. Returning to full open...")
        gripper.open_full()
        pos = gripper.get_position_percent()
        print(f"   Position: {pos:.1f}%")

        print()
        print("-" * 30)
        print("Special modes test COMPLETE")
        print()
        print("Mode descriptions:")
        print("  POINT MODE - Partially closed position ideal for:")
        print("    - Pressing elevator buttons")
        print("    - Tapping touchscreens")
        print("    - Flipping switches")
        print()
        print("  PUSH MODE - Fully closed position ideal for:")
        print("    - Pushing objects across a surface")
        print("    - Sliding doors open")
        print("    - Moving items without gripping")

    finally:
        gripper.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
