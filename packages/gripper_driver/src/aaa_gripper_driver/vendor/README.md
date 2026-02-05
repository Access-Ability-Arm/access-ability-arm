# Vendored Libraries

## scservo_sdk

The `scservo_sdk` module is vendored from Waveshare's STServo Python SDK.

### Source

- **Project**: Waveshare Bus Servo Adapter (A)
- **Download**: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- **File**: STServo_Python.zip
- **License**: Waveshare proprietary (for use with their hardware)

### Installation

1. Download `STServo_Python.zip` from the Waveshare wiki page
2. Extract the archive
3. Copy the `scservo_sdk` folder to this directory:
   ```
   packages/gripper_driver/src/aaa_gripper_driver/vendor/scservo_sdk/
   ```

### Expected Files

After installation, you should have:

```
vendor/
├── __init__.py
├── README.md
└── scservo_sdk/
    ├── __init__.py
    ├── scscl.py         # SC series protocol (SC09, SC15, etc.)
    ├── port_handler.py  # Serial port handling
    ├── packet_handler.py
    ├── group_sync_read.py
    ├── group_sync_write.py
    └── protocol_packet_handler.py
```

### Usage

```python
from aaa_gripper_driver.vendor.scservo_sdk import PortHandler, SCSCL

# The SCSCL class is used for SC series servos
port_handler = PortHandler("/dev/ttyUSB0")
servo = SCSCL(port_handler)
```

### Notes

- This SDK is for SC series servos (SCSCL protocol)
- For ST series servos, use SMS_STS protocol instead
- Default baudrate: 1000000 (1 Mbps)
- Position resolution: 12-bit (0-4095)
