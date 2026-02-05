#!/usr/bin/env python3
"""
Interactive Gripper Control Script

Provides a simple REPL for manually testing gripper commands.
Useful for hardware calibration and exploration.

Usage:
    python interactive.py [--port PORT] [--id SERVO_ID]

Commands:
    open          - Full open
    wide          - Wide open (75%)
    medium        - Medium open (50%)
    narrow        - Narrow open (25%)
    close         - Full close
    grip [force]  - Grip with force (soft/medium/firm)
    release       - Release and open
    point         - Point mode
    push          - Push mode
    pos <0-100>   - Move to percentage
    raw <0-4095>  - Move to raw position
    status        - Show current position and load
    calibrate     - Enter calibration mode
    help          - Show this help
    quit          - Exit
"""

import argparse
import sys


def print_help():
    print("""
Commands:
  open          - Full open (100%)
  wide          - Wide open (75%)
  medium        - Medium open (50%)
  narrow        - Narrow open (25%)
  close         - Full close (0%)
  grip [force]  - Grip with force control (soft/medium/firm, default: medium)
  release       - Release grip and return to open
  point         - Enter point mode (for pressing buttons)
  push          - Enter push mode (for pushing objects)
  pos <0-100>   - Move to specific percentage
  raw <0-4095>  - Move to raw servo position
  speed <value> - Set movement speed
  torque <0-100>- Set torque limit percentage
  status        - Show current position and load
  calibrate     - Enter calibration helper mode
  help          - Show this help
  quit          - Exit program
""")


def calibrate_mode(gripper):
    """Interactive calibration helper"""
    print("\n--- CALIBRATION MODE ---")
    print("Use 'raw' commands to find min/max positions for your gripper.")
    print("Commands: raw <pos>, status, done")
    print()

    min_pos = None
    max_pos = None

    while True:
        try:
            cmd = input("cal> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue

        parts = cmd.split()

        if parts[0] == "done":
            break
        elif parts[0] == "raw" and len(parts) > 1:
            try:
                pos = int(parts[1])
                gripper.set_position(pos)
            except ValueError:
                print("Invalid position")
        elif parts[0] == "status":
            pos = gripper.get_position()
            pct = gripper.get_position_percent()
            load = gripper.get_load()
            print(f"Position: {pos} ({pct:.1f}%), Load: {load}")
        elif parts[0] == "setmin":
            min_pos = gripper.get_position()
            print(f"Min position set to: {min_pos}")
        elif parts[0] == "setmax":
            max_pos = gripper.get_position()
            print(f"Max position set to: {max_pos}")
        else:
            print("Commands: raw <pos>, status, setmin, setmax, done")

    print("\n--- CALIBRATION RESULTS ---")
    if min_pos is not None:
        print(f"Minimum (closed): {min_pos}")
    if max_pos is not None:
        print(f"Maximum (open): {max_pos}")
    if min_pos is not None and max_pos is not None:
        print(f"\nAdd to GripperConfig:")
        print(f"  min_position={min_pos},")
        print(f"  max_position={max_pos},")
    print()


def main():
    parser = argparse.ArgumentParser(description="Interactive SC Servo Gripper control")
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
    print("SC Servo Gripper - Interactive Control")
    print("=" * 50)
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

    print()
    print("Type 'help' for commands, 'quit' to exit.")
    print()

    try:
        while True:
            try:
                cmd = input("gripper> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not cmd:
                continue

            parts = cmd.split()
            command = parts[0]

            try:
                if command in ("quit", "exit", "q"):
                    break

                elif command == "help":
                    print_help()

                elif command == "open":
                    gripper.open_full()

                elif command == "wide":
                    gripper.open_wide()

                elif command == "medium":
                    gripper.open_medium()

                elif command == "narrow":
                    gripper.open_narrow()

                elif command == "close":
                    gripper.close()

                elif command == "grip":
                    force = parts[1] if len(parts) > 1 else "medium"
                    if force not in ("soft", "medium", "firm"):
                        print("Force must be: soft, medium, or firm")
                    else:
                        gripper.grip(force=force)

                elif command == "release":
                    gripper.release()

                elif command == "point":
                    gripper.point_mode()

                elif command == "push":
                    gripper.push_mode()

                elif command == "pos":
                    if len(parts) < 2:
                        print("Usage: pos <0-100>")
                    else:
                        pct = float(parts[1])
                        gripper.set_position_percent(pct)

                elif command == "raw":
                    if len(parts) < 2:
                        print("Usage: raw <0-4095>")
                    else:
                        pos = int(parts[1])
                        gripper.set_position(pos)

                elif command == "speed":
                    if len(parts) < 2:
                        print(f"Current speed: {gripper.config.default_speed}")
                        print("Usage: speed <value>")
                    else:
                        gripper.config.default_speed = int(parts[1])
                        print(f"Speed set to: {gripper.config.default_speed}")

                elif command == "torque":
                    if len(parts) < 2:
                        print("Usage: torque <0-100>")
                    else:
                        pct = float(parts[1])
                        gripper.set_torque_limit(pct)

                elif command == "status":
                    pos = gripper.get_position()
                    pct = gripper.get_position_percent()
                    load = gripper.get_load()
                    print(f"Position: {pos} ({pct:.1f}%)")
                    print(f"Load: {load}")

                elif command == "calibrate":
                    calibrate_mode(gripper)

                elif command == "stop":
                    gripper.emergency_stop()
                    print("Emergency stop!")

                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for available commands")

            except Exception as e:
                print(f"Error: {e}")

    finally:
        print("Disconnecting...")
        gripper.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
