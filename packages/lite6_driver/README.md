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

### Basic Usage

```python
from aaa_lite6_driver import Lite6Arm

# Connect to the arm
arm = Lite6Arm(ip="192.168.1.203")
if arm.connect():
    # Move to position (x, y, z in mm)
    arm.move_to_position(x=300, y=0, z=200)
    
    # Move with orientation (x, y, z, roll, pitch, yaw)
    arm.move_to_position(x=300, y=0, z=200, roll=0, pitch=0, yaw=0)
    
    # Control gripper
    arm.open_gripper()
    arm.close_gripper()
    arm.set_gripper_position(400)  # 0=closed, 800=open
    
    # Get current position
    pos = arm.get_position()  # Returns (x, y, z, roll, pitch, yaw)
    
    # Home position
    arm.home()
    
    # Disconnect
    arm.disconnect()
```

### Context Manager (Recommended)

```python
from aaa_lite6_driver import Lite6Arm

with Lite6Arm("192.168.1.203") as arm:
    arm.move_to_position(x=300, y=0, z=200)
    arm.close_gripper()
    # Automatically disconnects when done
```

### Example Script

See [examples/basic_control.py](examples/basic_control.py) for a complete working example.

## Configuration

Configure the arm IP address and settings in your application or via environment variables.

## Documentation

See the UFactory documentation for detailed SDK information:
- [xArm Python SDK](https://github.com/xArm-Developer/xArm-Python-SDK)
- [UFactory Lite6 Manual](https://www.ufactory.cc/lite-6-collaborative-robot/)
