#!/usr/bin/env python3
"""
Test Force/Torque Control Script

Tests the force-controlled gripping of the SC Servo Gripper.
Demonstrates soft, medium, and firm grip levels.

Usage:
    python test_force.py [--port PORT] [--id SERVO_ID]

TIP: Place a soft object (like a foam ball) in the gripper
     to see the force control in action.
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Test SC Servo Gripper force control")
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
        help="Delay between tests in seconds (default: 2.0)"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("SC Servo Gripper - Force Control Test")
    print("=" * 50)
    print()
    print("This test demonstrates force-controlled gripping.")
    print("The servo will close until it meets resistance,")
    print("then stop to avoid crushing the object.")
    print()
    print("TIP: Place a soft object in the gripper to observe")
    print("     different grip strengths.")
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
        print("Starting force control test...")
        print("-" * 30)

        force_levels = ["soft", "medium", "firm"]

        for force in force_levels:
            print(f"\n--- Testing {force.upper()} grip ---")

            # Open first
            print("Opening gripper...")
            gripper.open_full()
            time.sleep(0.5)

            # Now grip with specified force
            print(f"Gripping with {force} force...")
            gripper.grip(force=force)

            # Check load
            load = gripper.get_load()
            pos = gripper.get_position()
            pct = gripper.get_position_percent()

            print(f"  Final position: {pos} ({pct:.1f}%)")
            print(f"  Load reading: {load}")
            print(f"  Status: OK")

            time.sleep(args.delay)

        # Release and return to open
        print("\nReleasing grip...")
        gripper.release()

        print()
        print("-" * 30)
        print("Force control test COMPLETE")
        print()
        print("Notes:")
        print("  - Soft grip: Low torque, stops easily on light contact")
        print("  - Medium grip: Moderate torque, good for most objects")
        print("  - Firm grip: High torque, for heavy/slippery objects")

    finally:
        gripper.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
