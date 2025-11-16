#!/usr/bin/env python3
"""
Interactive configuration setup script for Access Ability Arm

This script helps you set up your configuration file with guided prompts.
"""

import os
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


def prompt(question: str, default: str = None) -> str:
    """Prompt user for input with optional default"""
    if default:
        response = input(f"{question} [{default}]: ").strip()
        return response if response else default
    else:
        response = ""
        while not response:
            response = input(f"{question}: ").strip()
        return response


def prompt_bool(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no input"""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{question} [{default_str}]: ").strip().lower()

    if not response:
        return default
    return response in ['y', 'yes', 'true', '1']


def prompt_float(question: str, default: float) -> float:
    """Prompt user for float input"""
    while True:
        response = input(f"{question} [{default}]: ").strip()
        if not response:
            return default
        try:
            return float(response)
        except ValueError:
            print("Please enter a valid number.")


def prompt_int(question: str, default: int) -> int:
    """Prompt user for integer input"""
    while True:
        response = input(f"{question} [{default}]: ").strip()
        if not response:
            return default
        try:
            return int(response)
        except ValueError:
            print("Please enter a valid integer.")


def prompt_choice(question: str, choices: list, default: str) -> str:
    """Prompt user to choose from a list"""
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        marker = "*" if choice == default else " "
        print(f"  {marker} {i}. {choice}")

    while True:
        response = input(f"Enter choice [1-{len(choices)}] or press Enter for default: ").strip()
        if not response:
            return default
        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
            else:
                print(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            print("Please enter a valid number.")


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


def main():
    """Main configuration setup"""
    print("=" * 60)
    print("Access Ability Arm - Configuration Setup")
    print("=" * 60)
    print("\nThis script will help you create a custom configuration file.")
    print("Press Enter to accept default values (shown in brackets).\n")

    project_root = get_project_root()
    config_path = project_root / "config" / "config.yaml"
    template_path = project_root / "config" / "config.yaml.template"

    # Load template as defaults
    if template_path.exists():
        with open(template_path) as f:
            config = yaml.safe_load(f)
    else:
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)

    # Check if config already exists
    if config_path.exists():
        overwrite = prompt_bool("\nConfiguration file already exists. Overwrite?", default=False)
        if not overwrite:
            print("Configuration setup cancelled.")
            return

    print("\n" + "-" * 60)
    print("ROBOTIC ARM SETTINGS")
    print("-" * 60)

    config['arm']['ip'] = prompt(
        "Enter your Lite6 arm IP address",
        default=config['arm']['ip']
    )

    config['arm']['port'] = prompt_int(
        "Enter the port number",
        default=config['arm']['port']
    )

    # Test connection
    test_connection = prompt_bool("\nWould you like to test the arm connection now?", default=True)
    if test_connection:
        connected = test_arm_connection(config['arm']['ip'], config['arm']['port'])
        if not connected:
            retry = prompt_bool("Would you like to re-enter the IP address?", default=True)
            if retry:
                config['arm']['ip'] = prompt("Enter your Lite6 arm IP address")
                test_arm_connection(config['arm']['ip'], config['arm']['port'])

    config['arm']['auto_connect'] = prompt_bool(
        "Auto-connect to arm on startup?",
        default=config['arm']['auto_connect']
    )

    print("\n" + "-" * 60)
    print("CAMERA SETTINGS")
    print("-" * 60)

    config['camera']['max_cameras_to_check'] = prompt_int(
        "Maximum number of cameras to check",
        default=config['camera']['max_cameras_to_check']
    )

    config['camera']['default_camera'] = prompt_int(
        "Default camera index (0 = first camera)",
        default=config['camera']['default_camera']
    )

    print("\n" + "-" * 60)
    print("OBJECT DETECTION SETTINGS")
    print("-" * 60)

    config['detection']['threshold'] = prompt_float(
        "Detection confidence threshold (0.0 - 1.0)",
        default=config['detection']['threshold']
    )

    config['detection']['yolo_model_size'] = prompt_choice(
        "YOLOv11 model size",
        choices=['n', 's', 'm', 'l', 'x'],
        default=config['detection']['yolo_model_size']
    )

    print("\n" + "-" * 60)
    print("CONTROL SETTINGS")
    print("-" * 60)

    config['controls']['tap_step_size'] = prompt_int(
        "Step size for tap (short press) in mm",
        default=config['controls']['tap_step_size']
    )

    config['controls']['hold_step_size'] = prompt_int(
        "Step size for hold (long press) in mm",
        default=config['controls']['hold_step_size']
    )

    config['controls']['movement_speed'] = prompt_int(
        "Movement speed in mm/s",
        default=config['controls']['movement_speed']
    )

    # Save configuration
    print("\n" + "=" * 60)
    print("Saving configuration...")

    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Configuration saved to: {config_path}")
    print("\nYou can manually edit this file at any time.")
    print("To run this setup again, use: python scripts/setup_config.py")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nConfiguration setup cancelled.")
        sys.exit(0)
