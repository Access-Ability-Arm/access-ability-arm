#!/usr/bin/env python3
"""
Quick configuration update script for Access Ability Arm

This script allows you to quickly update common settings without
manually editing the config file or running the full setup.
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).parent.parent


def load_config() -> dict:
    """Load existing config or create from template"""
    project_root = get_project_root()
    config_path = project_root / "config" / "config.yaml"
    template_path = project_root / "config" / "config.yaml.template"

    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    elif template_path.exists():
        print("No config.yaml found. Creating from template...")
        with open(template_path) as f:
            config = yaml.safe_load(f)
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print(f"Created config.yaml from template")
        return config
    else:
        print("Error: Neither config.yaml nor template found")
        sys.exit(1)


def save_config(config: dict):
    """Save configuration to file"""
    project_root = get_project_root()
    config_path = project_root / "config" / "config.yaml"

    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\n✓ Configuration saved to: {config_path}")


def test_arm_connection(ip: str, port: int) -> bool:
    """Test connection to the arm"""
    print(f"\nTesting connection to {ip}:{port}...")
    try:
        from aaa_lite6_driver import Lite6Arm

        arm = Lite6Arm(ip, port)
        if arm.connect():
            print("✓ Connection successful!")
            arm.disconnect()
            return True
        else:
            print("✗ Connection failed. The arm may not be powered on or the IP may be incorrect.")
            return False
    except ImportError:
        print("Note: lite6_driver not installed. Skipping connection test.")
        return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False


def update_arm_ip():
    """Update arm IP address"""
    config = load_config()

    current_ip = config.get('arm', {}).get('ip', 'not set')
    print(f"\nCurrent arm IP: {current_ip}")

    new_ip = input("Enter new IP address (or press Enter to cancel): ").strip()
    if not new_ip:
        print("Cancelled.")
        return

    # Update config
    if 'arm' not in config:
        config['arm'] = {}
    config['arm']['ip'] = new_ip

    # Test connection
    port = config.get('arm', {}).get('port', 502)
    test = input("\nTest connection now? [Y/n]: ").strip().lower()
    if test != 'n':
        connected = test_arm_connection(new_ip, port)
        if not connected:
            confirm = input("\nConnection failed. Save anyway? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("Cancelled. Configuration not saved.")
                return

    save_config(config)


def update_camera_default():
    """Update default camera index"""
    config = load_config()

    current = config.get('camera', {}).get('default_camera', 0)
    print(f"\nCurrent default camera: {current}")

    try:
        new_camera = input("Enter new default camera index (0-2, or press Enter to cancel): ").strip()
        if not new_camera:
            print("Cancelled.")
            return

        new_camera = int(new_camera)
        if new_camera < 0:
            print("Camera index must be >= 0")
            return

        if 'camera' not in config:
            config['camera'] = {}
        config['camera']['default_camera'] = new_camera

        save_config(config)
    except ValueError:
        print("Invalid number. Cancelled.")


def update_movement_speeds():
    """Update movement speeds"""
    config = load_config()

    if 'controls' not in config:
        config['controls'] = {}

    controls = config['controls']

    print("\n=== Movement Speeds ===")
    print(f"Current tap step: {controls.get('tap_step_size', 10)} mm")
    print(f"Current hold step: {controls.get('hold_step_size', 50)} mm")
    print(f"Current movement speed: {controls.get('movement_speed', 100)} mm/s")
    print(f"Current gripper speed: {controls.get('gripper_speed', 5000)} pulse/s")

    print("\nEnter new values (or press Enter to keep current):")

    tap = input(f"Tap step size [{controls.get('tap_step_size', 10)}] mm: ").strip()
    if tap:
        try:
            controls['tap_step_size'] = int(tap)
        except ValueError:
            print("Invalid number, keeping current value")

    hold = input(f"Hold step size [{controls.get('hold_step_size', 50)}] mm: ").strip()
    if hold:
        try:
            controls['hold_step_size'] = int(hold)
        except ValueError:
            print("Invalid number, keeping current value")

    speed = input(f"Movement speed [{controls.get('movement_speed', 100)}] mm/s: ").strip()
    if speed:
        try:
            controls['movement_speed'] = int(speed)
        except ValueError:
            print("Invalid number, keeping current value")

    gripper = input(f"Gripper speed [{controls.get('gripper_speed', 5000)}] pulse/s: ").strip()
    if gripper:
        try:
            controls['gripper_speed'] = int(gripper)
        except ValueError:
            print("Invalid number, keeping current value")

    config['controls'] = controls
    save_config(config)


def update_detection_threshold():
    """Update detection confidence threshold"""
    config = load_config()

    if 'detection' not in config:
        config['detection'] = {}

    current = config['detection'].get('threshold', 0.5)
    print(f"\nCurrent detection threshold: {current}")
    print("Lower = more detections but more false positives")
    print("Higher = fewer detections but more accurate")

    try:
        new_threshold = input(f"Enter new threshold [0.0-1.0, current: {current}]: ").strip()
        if not new_threshold:
            print("Cancelled.")
            return

        new_threshold = float(new_threshold)
        if not (0.0 <= new_threshold <= 1.0):
            print("Threshold must be between 0.0 and 1.0")
            return

        config['detection']['threshold'] = new_threshold
        save_config(config)
    except ValueError:
        print("Invalid number. Cancelled.")


def view_config():
    """View current configuration"""
    config = load_config()

    print("\n" + "=" * 60)
    print("CURRENT CONFIGURATION")
    print("=" * 60)

    print("\n--- Arm Settings ---")
    arm = config.get('arm', {})
    print(f"  IP: {arm.get('ip', 'not set')}")
    print(f"  Port: {arm.get('port', 'not set')}")
    print(f"  Auto-connect: {arm.get('auto_connect', 'not set')}")

    print("\n--- Camera Settings ---")
    camera = config.get('camera', {})
    print(f"  Max cameras to check: {camera.get('max_cameras_to_check', 'not set')}")
    print(f"  Default camera: {camera.get('default_camera', 'not set')}")

    print("\n--- Detection Settings ---")
    detection = config.get('detection', {})
    print(f"  Threshold: {detection.get('threshold', 'not set')}")
    print(f"  YOLO model size: {detection.get('yolo_model_size', 'not set')}")

    print("\n--- Control Settings ---")
    controls = config.get('controls', {})
    print(f"  Button hold threshold: {controls.get('button_hold_threshold', 'not set')} s")
    print(f"  Tap step size: {controls.get('tap_step_size', 'not set')} mm")
    print(f"  Hold step size: {controls.get('hold_step_size', 'not set')} mm")
    print(f"  Movement speed: {controls.get('movement_speed', 'not set')} mm/s")
    print(f"  Gripper speed: {controls.get('gripper_speed', 'not set')} pulse/s")

    print("\n--- Display Settings ---")
    display = config.get('display', {})
    print(f"  Video width: {display.get('width', 'not set')} px")
    print(f"  Video height: {display.get('height', 'not set')} px")
    print(f"  Window width: {display.get('window_width', 'not set')} px")
    print(f"  Window height: {display.get('window_height', 'not set')} px")

    print("\n" + "=" * 60)


def main():
    """Main menu"""
    while True:
        print("\n" + "=" * 60)
        print("Access Ability Arm - Quick Configuration Update")
        print("=" * 60)
        print("\nWhat would you like to update?")
        print("  1. Arm IP address")
        print("  2. Default camera")
        print("  3. Movement speeds and step sizes")
        print("  4. Detection threshold")
        print("  5. View current configuration")
        print("  6. Run full setup (interactive)")
        print("  0. Exit")

        choice = input("\nEnter choice [0-6]: ").strip()

        if choice == '1':
            update_arm_ip()
        elif choice == '2':
            update_camera_default()
        elif choice == '3':
            update_movement_speeds()
        elif choice == '4':
            update_detection_threshold()
        elif choice == '5':
            view_config()
        elif choice == '6':
            print("\nLaunching full setup script...")
            import subprocess
            script_path = Path(__file__).parent / "setup_config.py"
            subprocess.run([sys.executable, str(script_path)])
            return
        elif choice == '0':
            print("\nGoodbye!")
            return
        else:
            print("Invalid choice. Please enter 0-6.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)
