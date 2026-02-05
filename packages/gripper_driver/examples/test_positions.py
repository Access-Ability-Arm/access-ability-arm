#!/usr/bin/env python3
"""
Test Positions Script

Tests all preset positions of the SC Servo Gripper.
Cycles through: full open, wide, medium, narrow, close.

Usage:
    python test_positions.py [--port PORT] [--id SERVO_ID]

WARNING: Gripper will move! Ensure nothing is in the way.
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Test SC Servo Gripper positions")
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
        default=1.5,
        help="Delay between positions in seconds (default: 1.5)"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("SC Servo Gripper - Position Test")
    print("=" * 50)
    print()
    print("WARNING: Gripper will move through all positions!")
    print("         Ensure the gripper area is clear.")
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
        print()
        print("Starting position test...")
        print("-" * 30)

        # Test sequence
        tests = [
            ("Full Open (100%)", gripper.open_full),
            ("Wide (75%)", gripper.open_wide),
            ("Medium (50%)", gripper.open_medium),
            ("Narrow (25%)", gripper.open_narrow),
            ("Close (0%)", gripper.close),
        ]

        for name, method in tests:
            print(f"\nMoving to: {name}")
            if method(wait=True):
                pos = gripper.get_position()
                pct = gripper.get_position_percent()
                print(f"  Position: {pos} ({pct:.1f}%)")
                print(f"  Status: OK")
            else:
                print(f"  Status: FAILED")
            time.sleep(args.delay)

        # Return to open position
        print("\nReturning to full open...")
        gripper.open_full()

        print()
        print("-" * 30)
        print("Position test COMPLETE")

    finally:
        gripper.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
