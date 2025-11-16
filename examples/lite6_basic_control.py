#!/usr/bin/env python3
"""
UFactory Lite6 Basic Control Example

Demonstrates basic usage of the Lite6 arm driver.
"""

import time

from aaa_lite6_driver import Lite6Arm


def main():
    """Basic control example"""
    # Configure your arm's IP address
    ARM_IP = "192.168.1.xxx"  # Replace with your arm's IP

    print("=" * 60)
    print("UFactory Lite6 Basic Control Example")
    print("=" * 60)
    print()

    # Create arm instance
    arm = Lite6Arm(ip=ARM_IP)

    # Connect to the arm
    if not arm.connect():
        print("Failed to connect to arm. Check IP address and connection.")
        return

    try:
        # Move to home position
        print("\n1. Moving to home position...")
        arm.home()
        time.sleep(2)

        # Open gripper
        print("\n2. Opening gripper...")
        arm.open_gripper()
        time.sleep(1)

        # Move to a position
        print("\n3. Moving to position (300, 0, 200)...")
        arm.move_to_position(x=300, y=0, z=200, speed=100)
        time.sleep(2)

        # Get current position
        print("\n4. Getting current position...")
        pos = arm.get_position()
        if pos:
            print(f"   Current position: x={pos[0]:.1f}, y={pos[1]:.1f}, z={pos[2]:.1f} mm")

        # Close gripper
        print("\n5. Closing gripper...")
        arm.close_gripper()
        time.sleep(1)

        # Set gripper to half-open
        print("\n6. Setting gripper to 50% open...")
        arm.set_gripper_position(400)  # 400 = 50% (0-800 range)
        time.sleep(1)

        # Move back to home
        print("\n7. Returning to home position...")
        arm.home()

        print("\n✓ Example completed successfully!")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        arm.emergency_stop()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        arm.emergency_stop()

    finally:
        # Disconnect
        print("\nDisconnecting...")
        arm.disconnect()


def context_manager_example():
    """Example using context manager (with statement)"""
    ARM_IP = "192.168.1.xxx"  # Replace with your arm's IP

    print("\nContext Manager Example:")
    print("-" * 40)

    # Using context manager (automatically connects and disconnects)
    with Lite6Arm(ip=ARM_IP) as arm:
        print("Moving to position...")
        arm.move_to_position(x=300, y=0, z=200)

        print("Opening gripper...")
        arm.open_gripper()

    print("✓ Disconnected automatically")


if __name__ == "__main__":
    main()

    # Uncomment to try context manager example:
    # context_manager_example()
