#!/usr/bin/env python3
"""
Test Connection Script

Basic connectivity test for the SC Servo Gripper.
Verifies serial port and servo communication.

Usage:
    python test_connection.py [--port PORT] [--id SERVO_ID]

Examples:
    python test_connection.py
    python test_connection.py --port /dev/ttyUSB0 --id 1
    python test_connection.py --port /dev/cu.usbserial-1420 --id 1
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Test SC Servo Gripper connection")
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
    args = parser.parse_args()

    print("=" * 50)
    print("SC Servo Gripper - Connection Test")
    print("=" * 50)
    print(f"Port: {args.port}")
    print(f"Baudrate: {args.baudrate}")
    print(f"Servo ID: {args.servo_id}")
    print()

    # Check SDK availability
    try:
        from aaa_gripper_driver import SDK_AVAILABLE
        if not SDK_AVAILABLE:
            print("ERROR: scservo_sdk not installed!")
            print()
            print("Please download the SDK from:")
            print("  https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)")
            print()
            print("Extract STServo_Python.zip and copy scservo_sdk to:")
            print("  packages/gripper_driver/src/aaa_gripper_driver/vendor/")
            return 1
    except ImportError as e:
        print(f"ERROR: Failed to import gripper driver: {e}")
        print("Make sure the package is installed: pip install -e packages/gripper_driver")
        return 1

    # Try to connect
    from aaa_gripper_driver import SCServoGripper

    print("Attempting connection...")
    gripper = SCServoGripper(
        port=args.port,
        baudrate=args.baudrate,
        servo_id=args.servo_id
    )

    if gripper.connect():
        print()
        print("SUCCESS: Servo is responding!")
        print()

        # Get current position
        position = gripper.get_position()
        if position is not None:
            percent = gripper.get_position_percent()
            print(f"Current position: {position} ({percent:.1f}%)")

        # Get current load
        load = gripper.get_load()
        if load is not None:
            print(f"Current load: {load}")

        gripper.disconnect()
        print()
        print("Connection test PASSED")
        return 0
    else:
        print()
        print("FAILED: Could not connect to servo")
        print()
        print("Troubleshooting:")
        print("  1. Check that the servo adapter is connected via USB")
        print("  2. Check that the servo is powered (external 6-8V power)")
        print("  3. Verify the servo ID matches (use --id flag)")
        print("  4. Try different serial port (use --port flag)")
        print("  5. Check wiring: servo -> adapter signal cable")
        return 1


if __name__ == "__main__":
    sys.exit(main())
