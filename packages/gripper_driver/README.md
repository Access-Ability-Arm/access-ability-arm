# AAA Gripper Driver

Waveshare SC Servo gripper driver for the Access Ability Arm project.

## Overview

This package provides a Python driver for controlling Waveshare SC series servos (SC09/SC15) connected via the Bus Servo Adapter (A). It's designed to work with a gripper mechanism for the Lite6 robotic arm.

## Installation

```bash
pip install -e packages/gripper_driver
```

## Vendored SDK

This package vendors the `scservo_sdk` from Waveshare's STServo Python SDK. To set up:

1. Download `STServo_Python.zip` from [Waveshare Wiki](https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A))
2. Extract the `scservo_sdk` folder
3. Copy it to `src/aaa_gripper_driver/vendor/scservo_sdk/`

## Quick Start

```python
from aaa_gripper_driver import SCServoGripper

# Connect to gripper
gripper = SCServoGripper(port="/dev/ttyUSB0", servo_id=1)
if gripper.connect():
    # Open and close
    gripper.open_full()
    gripper.close()

    # Grip with force control
    gripper.grip(force="medium")

    # Special modes
    gripper.point_mode()  # Single finger for pressing
    gripper.push_mode()   # Closed for pushing

    gripper.disconnect()
```

## Configuration

Default settings can be overridden:

```python
from aaa_gripper_driver import SCServoGripper, GripperConfig

config = GripperConfig(
    min_position=100,      # Calibrated closed position
    max_position=900,      # Calibrated open position
    preset_wide=80,        # 80% open
    preset_medium=50,      # 50% open
    preset_narrow=30,      # 30% open
    torque_soft=25,        # 25% torque for soft grip
    torque_medium=50,      # 50% torque for medium grip
    torque_firm=85,        # 85% torque for firm grip
)

gripper = SCServoGripper(port="/dev/ttyUSB0", config=config)
```

## Test Scripts

Run the example scripts to validate your hardware:

```bash
# Test connection
python packages/gripper_driver/examples/test_connection.py

# Test position presets
python packages/gripper_driver/examples/test_positions.py

# Test force/torque control
python packages/gripper_driver/examples/test_force.py

# Test point and push modes
python packages/gripper_driver/examples/test_modes.py

# Interactive CLI
python packages/gripper_driver/examples/interactive.py
```

## Hardware Notes

- **Serial port**: Linux `/dev/ttyUSB0`, macOS `/dev/cu.usbserial-xxx`, Windows `COM3`
- **Default baudrate**: 1000000 (1 Mbps)
- **Position resolution**: 12-bit (0-4095)
- **Protocol**: SCSCL (for SC series servos)
