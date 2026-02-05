# Waveshare STServo Gripper Integration Plan

## Summary

Integrate the Waveshare Bus Servo Adapter (A) with SC series servos (SC09/SC15) as the primary gripper, replacing the Lite6 built-in gripper functionality. Create a new package following the established `lite6_driver` pattern.

## Phased Approach

### Phase 1: Hardware Validation (Current)
- Create driver package with vendored SDK
- Implement core driver class
- Standalone testing scripts to verify hardware/software connection
- No GUI changes

### Phase 2: GUI Integration (Future)
- Create Flet worker class
- Add gripper controls to main window
- Replace Lite6 gripper functionality

---

## Feature Requirements

1. **Position Presets** (4 configurable positions with sensible defaults)
   - Full Open (100%) - maximum opening
   - Wide (75%) - large objects
   - Medium (50%) - standard grip
   - Narrow (25%) - small objects

2. **Grip Command with Force Control**
   - Torque limit presets: Soft, Medium, Firm
   - Servo stops when resistance exceeds torque limit
   - Configurable torque values per force level

3. **Point Mode** - Single finger extended for pressing buttons/touchscreens

4. **Push Mode** - Closed gripper for pushing/sliding objects

---

# Phase 1: Hardware Validation

## Package Structure

```
packages/gripper_driver/
├── pyproject.toml
├── README.md
├── examples/
│   └── basic_control.py
└── src/
    └── aaa_gripper_driver/
        ├── __init__.py
        ├── scservo_gripper.py       # Main driver class
        └── vendor/
            ├── __init__.py
            ├── README.md            # Attribution/license
            └── scservo_sdk/         # Vendored from STServo_Python.zip
```

## Implementation Steps

### 1. Create Package Structure
- Create `packages/gripper_driver/` directory
- Download STServo_Python.zip from Waveshare
- Vendor the `scservo_sdk` module into `vendor/`
- Create `pyproject.toml`:
```toml
[project]
name = "aaa-gripper-driver"
version = "0.1.0"
dependencies = ["aaa-core", "pyserial>=3.5"]
```

### 2. Implement SCServoGripper Driver
Create `scservo_gripper.py` following `lite6_arm.py` patterns:

**Core Methods:**
- `__init__(port, baudrate, servo_id, config)` - config includes presets and torque settings
- `connect() -> bool` - open serial port, ping servo
- `disconnect()` - close port
- `emergency_stop()` - disable torque immediately
- Context manager support (`__enter__`, `__exit__`)

**Position Control:**
- `set_position(position, speed, wait) -> bool` - raw servo position
- `set_position_percent(percent, speed, wait) -> bool` - 0-100%
- `get_position() -> Optional[int]` - current raw position
- `get_position_percent() -> Optional[float]` - current as percentage

**Preset Position Methods:**
- `open_full(speed, wait) -> bool` - 100% open
- `open_wide(speed, wait) -> bool` - 75% open (configurable)
- `open_medium(speed, wait) -> bool` - 50% open (configurable)
- `open_narrow(speed, wait) -> bool` - 25% open (configurable)
- `close(speed, wait) -> bool` - fully closed

**Grip with Force Control:**
- `grip(force: str = "medium", speed, wait) -> bool` - close with torque limit
  - `force`: "soft" | "medium" | "firm"
  - Sets torque limit before closing, servo stops when resistance exceeds limit
- `set_torque_limit(percent: float) -> bool` - 0-100% of max torque
- `get_load() -> Optional[int]` - current load/resistance reading

**Special Modes:**
- `point_mode(speed, wait) -> bool` - extend single finger for pointing/pressing
- `push_mode(speed, wait) -> bool` - closed position for pushing objects

Key details for SC series:
- Use `SCSCL` protocol class (not `SMS_STS`)
- Default baudrate: 1000000 (may vary for SC series)
- 12-bit position resolution (0-4095)
- Torque control via servo's torque limit register

### 3. Create Standalone Test Scripts
Create test scripts in `examples/` for hardware validation:

**examples/test_connection.py** - Basic connectivity test
```python
# Test serial connection and servo ping
from aaa_gripper_driver import SCServoGripper

gripper = SCServoGripper(port="/dev/ttyUSB0", servo_id=1)
if gripper.connect():
    print("SUCCESS: Servo responding")
    gripper.disconnect()
else:
    print("FAILED: Check port and wiring")
```

**examples/test_positions.py** - Test position control
```python
# Test all preset positions
gripper.open_full()
gripper.open_wide()
gripper.open_medium()
gripper.open_narrow()
gripper.close()
```

**examples/test_force.py** - Test torque/force control
```python
# Test grip with different force levels
gripper.grip(force="soft")
gripper.grip(force="medium")
gripper.grip(force="firm")
```

**examples/test_modes.py** - Test point and push modes
```python
# Test special modes
gripper.point_mode()
gripper.push_mode()
```

**examples/interactive.py** - Interactive CLI for manual testing
```python
# Simple REPL for testing commands manually
# Commands: open, close, grip [soft|medium|firm], point, push, pos <0-100>, quit
```

### 4. Install and Test
```bash
# Install the package
pip install -e packages/gripper_driver

# Run tests
python packages/gripper_driver/examples/test_connection.py
python packages/gripper_driver/examples/test_positions.py
python packages/gripper_driver/examples/interactive.py
```

---

# Phase 2: GUI Integration (Future)

### 1. Configuration Integration
Modify [settings.py](packages/core/src/aaa_core/config/settings.py):

Add to `AppConfig` dataclass:
```python
# SC Servo Gripper settings
scservo_port: str = "/dev/ttyUSB0"
scservo_baudrate: int = 1000000
scservo_id: int = 1
scservo_min_position: int = 0      # Calibrated in Phase 1
scservo_max_position: int = 4095   # Calibrated in Phase 1
scservo_speed: int = 2000
scservo_auto_connect: bool = False
scservo_available: bool = False

# Position presets (percentage of range)
scservo_preset_full: int = 100
scservo_preset_wide: int = 75
scservo_preset_medium: int = 50
scservo_preset_narrow: int = 25
scservo_preset_point: int = 15

# Torque/force presets (percentage of max torque)
scservo_torque_soft: int = 30
scservo_torque_medium: int = 60
scservo_torque_firm: int = 90
```

Add capability detection and `gripper:` section in config.yaml.

### 2. Create Worker Class
Create `gripper_controller_flet.py` in [workers/](packages/core/src/aaa_core/workers/):
- Follow `arm_controller_flet.py` pattern
- Callbacks: `on_connection_status`, `on_position_update`, `on_mode_change`, `on_error`
- Thread-safe with `threading.Lock`

**Methods:**
- `connect_gripper()`, `disconnect_gripper()`, `is_connected()`
- `open_full()`, `open_wide()`, `open_medium()`, `open_narrow()`
- `close()`
- `grip(force: str)` - grip with force control ("soft", "medium", "firm")
- `point_mode()` - enter pointing configuration
- `push_mode()` - enter pushing configuration
- `set_position(percent)` - arbitrary position
- `get_position()` - current position
- `emergency_stop()`

### 3. GUI Integration
Modify [main_window.py](packages/gui/src/aaa_gui/flet/main_window.py):

Replace Lite6 gripper calls with SCServo gripper:
- Import `GripperControllerFlet` when `scservo_available`
- Initialize `self.gripper_controller` in `_setup_components()`

**Control mapping:**
| GUI Control | Action |
|-------------|--------|
| Grip Toggle (closed) | `gripper_controller.grip(force)` with selected force |
| Grip Toggle (open) | `gripper_controller.open_full()` |
| Grip slider | `gripper_controller.set_position(percent)` |
| Preset buttons (new) | `open_full()`, `open_wide()`, `open_medium()`, `open_narrow()` |
| Force selector (new) | Dropdown: Soft/Medium/Firm - affects `grip()` call |
| Point button (new) | `gripper_controller.point_mode()` |
| Push button (new) | `gripper_controller.push_mode()` |

**New GUI elements to add:**
1. **Preset buttons row**: Full | Wide | Medium | Narrow
2. **Force dropdown**: Soft | Medium | Firm (default: Medium)
3. **Mode buttons row**: Grip | Point | Push

---

## Phase 1 Files to Create/Modify

| File | Changes |
|------|---------|
| `packages/gripper_driver/` | New package (create) |
| `packages/gripper_driver/pyproject.toml` | Package config |
| `packages/gripper_driver/src/aaa_gripper_driver/` | Driver module |
| `packages/gripper_driver/src/aaa_gripper_driver/vendor/` | Vendored SDK |
| `packages/gripper_driver/examples/` | Test scripts |
| `requirements.txt` | Add `-e packages/gripper_driver` |

## Phase 2 Files (Future)

| File | Changes |
|------|---------|
| [settings.py](packages/core/src/aaa_core/config/settings.py) | Add `scservo_*` config fields, capability detection |
| [workers/](packages/core/src/aaa_core/workers/) | Add `gripper_controller_flet.py` |
| [main_window.py](packages/gui/src/aaa_gui/flet/main_window.py) | Replace Lite6 gripper calls with SCServo |
| `config/config.yaml.template` | Add `gripper:` section |

## Existing Patterns to Reuse

- [lite6_arm.py:19-314](packages/lite6_driver/src/aaa_lite6_driver/lite6_arm.py#L19-L314) - Driver class pattern
- [arm_controller_flet.py:23-266](packages/core/src/aaa_core/workers/arm_controller_flet.py#L23-L266) - Flet worker pattern (Phase 2)
- [settings.py:279-344](packages/core/src/aaa_core/config/settings.py#L279-L344) - Capability detection pattern (Phase 2)

## Phase 1 Verification

1. **Connection test**: `python examples/test_connection.py`
   - Verify serial port opens
   - Verify servo responds to ping
   - Check servo model number returned

2. **Position test**: `python examples/test_positions.py`
   - Test all preset positions (full, wide, medium, narrow, close)
   - Verify servo moves to expected positions
   - Check position feedback matches commanded position

3. **Force test**: `python examples/test_force.py`
   - Test grip with soft/medium/firm force
   - Verify servo stops when resistance exceeds torque limit
   - Test with an object in gripper

4. **Mode test**: `python examples/test_modes.py`
   - Test point mode (single finger extended)
   - Test push mode (closed for pushing)

5. **Interactive test**: `python examples/interactive.py`
   - Manual testing via CLI
   - Calibrate min/max positions for your specific gripper

6. **Calibration**:
   - Find actual min/max positions for your gripper mechanism
   - Note values for Phase 2 config integration

## Notes

- SC series uses SCSCL protocol (different from ST series SMS_STS)
- Serial port names vary by OS: `/dev/ttyUSB0` (Linux), `/dev/cu.usbserial-xxx` (macOS), `COM3` (Windows)
- Servo min/max positions need calibration for specific gripper mechanism
- Torque control uses servo's torque limit register - servo will stop when load exceeds limit
- Point mode assumes gripper geometry allows single-finger extension (may need mechanical design consideration)
