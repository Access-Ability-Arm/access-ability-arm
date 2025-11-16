# AAA Lite6 Driver Package

UFactory Lite6 robotic arm driver for the Access Ability Arm project.

## Features

- UFactory Lite6 arm control via xArm Python SDK
- Position control (x, y, z)
- Gripper control
- Integration with Access Ability Arm vision system
- Safety features and error handling

## Installation

From the repository root:

```bash
pip install -e packages/lite6_driver
```

## Requirements

- UFactory Lite6 robotic arm
- xArm Python SDK (auto-installed)
- Network connection to the arm

## Usage

```python
from aaa_lite6_driver import Lite6Arm

# Connect to the arm
arm = Lite6Arm(ip="192.168.1.xxx")

# Move to position
arm.move_to_position(x=300, y=0, z=200)

# Control gripper
arm.open_gripper()
arm.close_gripper()

# Disconnect
arm.disconnect()
```

## Configuration

Configure the arm IP address and settings in your application or via environment variables.

## Documentation

See the UFactory documentation for detailed SDK information:
- [xArm Python SDK](https://github.com/xArm-Developer/xArm-Python-SDK)
- [UFactory Lite6 Manual](https://www.ufactory.cc/lite-6-collaborative-robot/)
