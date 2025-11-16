# Intel RealSense Setup Guide

Complete guide for installing and configuring Intel RealSense depth cameras with the Access Ability Arm project on macOS.

## Table of Contents

- [Overview](#overview)
- [Hardware Requirements](#hardware-requirements)
- [Installation](#installation)
- [Firmware Update](#firmware-update)
- [Testing the Camera](#testing-the-camera)
- [macOS-Specific Issues](#macos-specific-issues)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Access Ability Arm project supports Intel RealSense depth cameras for enhanced 3D perception. While optional, RealSense cameras provide depth sensing capabilities that can improve object detection and tracking.

**Supported Cameras:**
- Intel RealSense D435
- Intel RealSense D435i
- Intel RealSense D455
- Other D400-series cameras

**Installation Summary:**
- ✅ librealsense SDK (built from source)
- ✅ pyrealsense2 Python bindings
- ⚠️ RealSense Viewer (has OpenGL compatibility issues on macOS)
- ⚠️ Requires sudo for USB access on macOS

---

## Hardware Requirements

### Camera
- Intel RealSense D400-series depth camera

### Cable (Critical!)
- **Recommended**: Original Intel cable (black USB-C cable included with D435)
- **Alternative**: Thunderbolt 3/4 cable (⚡ symbol, backward compatible with USB 3.1)
- **Specification**: USB 3.1 Gen 1 or higher (5 Gbps minimum)
- **⚠️ Known Issue**: D435 has firmware-level USB enumeration bug causing USB 2.0 fallback with most cables
  - Must insert cable **quickly and firmly** (slow insertion triggers USB 2.0 mode)
  - Generic/charging cables often fail even if marked "USB 3.0"
  - See [USB 2.0 vs USB 3.0](#usb-20-vs-usb-30) for detailed troubleshooting

### System
- macOS 12.0+ (tested on macOS Sequoia 24.6.0)
- Apple Silicon (M-series) or Intel Mac
- USB 3.0+ port (Thunderbolt/USB-C)
- Python 3.11 (required by MediaPipe)

---

## Installation

### Prerequisites

Install required system dependencies:

```bash
# Install Xcode Command Line Tools
sudo xcode-select --install

# Install Homebrew packages
brew install cmake libusb pkg-config

# Install Vulkan components
brew install vulkan-loader vulkan-headers molten-vk vulkan-tools
```

### Build librealsense from Source

**Important:** Intel does not provide pre-built macOS packages. You must build from source.

```bash
# Clone librealsense repository
cd "/Users/ck432/Dropbox/brh/Access Ability Arm"
git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense

# Create build directory
mkdir build && cd build

# Configure build with Python bindings
cmake .. \
  -DBUILD_EXAMPLES=true \
  -DBUILD_PYTHON_BINDINGS=true \
  -DPYTHON_EXECUTABLE="/Users/ck432/Dropbox/brh/Access Ability Arm/code/access-ability-arm/venv/bin/python" \
  -DBUILD_WITH_OPENMP=false \
  -DHWM_OVER_XU=false

# Build (takes 10-20 minutes on M-series Macs)
make -j4

# Install system libraries (requires password)
sudo make install
```

### Install Python Bindings

```bash
# Navigate to your project
cd "/Users/ck432/Dropbox/brh/Access Ability Arm/code/access-ability-arm"
source venv/bin/activate

# Copy Python module to site-packages
cp "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/pyrealsense2.cpython-311-darwin.so" \
   "venv/lib/python3.11/site-packages/"

# Verify installation
python -c "import pyrealsense2 as rs; print(f'RealSense version: {rs.__version__}')"
```

**Expected output:** `RealSense version: 2.56.5`

---

## Firmware Update

### Why Update Firmware?

- Improved macOS compatibility
- Bug fixes and performance improvements
- New features and sensor calibration

### Check Current Firmware

```bash
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-enumerate-devices"
```

**Sample output:**
```
Device info:
    Name                          :     Intel RealSense D435
    Serial Number                 :     944622072288
    Firmware Version              :     5.15.0.2          ← Current version
    Recommended Firmware Version  :     5.17.0.10         ← Update available
    ...
```

### Update Process

**⚠️ Important Warnings:**
- Do NOT unplug the camera during firmware update
- Update can take 5-10 minutes
- Camera will disconnect/reconnect during update
- Ensure stable USB connection (avoid hubs if possible)

**Step 1: Prepare the camera**

```bash
# Kill any processes accessing the camera
sudo pkill -f pyrealsense2
sudo pkill -f realsense

# Unplug camera, wait 10 seconds, plug back in
# This resets the camera to a clean state
```

**Step 2: Verify camera is detected**

```bash
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-enumerate-devices"
```

**Step 3: Update firmware using serial number**

```bash
# Replace SERIAL_NUMBER with your camera's serial (e.g., 944622072288)
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-fw-update" \
  -s SERIAL_NUMBER \
  -f "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/common/fw/D4XX_FW_Image-5.17.0.10.bin"
```

**Example:**
```bash
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-fw-update" \
  -s 944622072288 \
  -f "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/common/fw/D4XX_FW_Image-5.17.0.10.bin"
```

**Step 4: Verify update**

After update completes:

```bash
# Unplug and replug camera
# Wait 5 seconds

# Check new firmware version
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-enumerate-devices"
```

Verify `Firmware Version` shows `5.17.0.10` (or newer).

### Firmware Update Troubleshooting

**Error: "cannot access depth sensor"**

This usually means another process is holding the camera. Solution:

```bash
# Kill all processes
sudo pkill -f pyrealsense2
sudo pkill -f realsense

# Hard reset camera
# 1. Unplug USB cable
# 2. Wait 10 seconds (important!)
# 3. Plug back in
# 4. Wait 5 seconds
# 5. Try update again immediately
```

**Error: "failed to read firmware file"**

Check the firmware file path. The firmware is located at:
```
/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/common/fw/D4XX_FW_Image-5.17.0.10.bin
```

NOT in `build/Release/` (common mistake).

**Error: "mutex lock failed"**

Background processes are interfering. Solution:

```bash
# Restart your terminal/session
# Or reboot the Mac
# Then try update process from Step 1
```

---

## Testing the Camera

### Quick Test (Command Line)

```bash
# Test with sudo (required on macOS)
# Use venv's Python to ensure correct pyrealsense2 version
cd "/Users/ck432/Dropbox/brh/Access Ability Arm/code/access-ability-arm"
sudo ./venv/bin/python scripts/test_realsense.py
```

**Expected output:**
```
RealSense Camera Test
==================================================
Attempting to start streaming...
✓ Streaming started successfully!

Connected to: Intel RealSense D435
Serial Number: 944622072288
Firmware: 5.17.0.10

Capturing frames...
  Frame 1: Color 640x480, Depth 640x480
  Frame 2: Color 640x480, Depth 640x480
  ...

✓ Camera is working correctly!
```

### RealSense Viewer (GUI)

**⚠️ Known Issue:** The RealSense Viewer has OpenGL compatibility issues on macOS and will crash with:

```
ERROR: ImGui_ImplOpenGL3_CreateDeviceObjects: failed to compile shader
GLFW Driver Error: Cocoa: Failed to find service port for display
Segmentation fault
```

**Workaround:** Use the Python test script instead of the GUI viewer.

### Integration with Access Ability Arm

To use RealSense in your project:

```python
import pyrealsense2 as rs
import numpy as np

# Initialize pipeline
pipeline = rs.pipeline()
config = rs.config()

# Configure streams
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

# Start streaming
pipeline.start(config)

try:
    while True:
        # Wait for frames
        frames = pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()

        # Convert to numpy arrays
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        # Your processing code here

finally:
    pipeline.stop()
```

---

## macOS-Specific Issues

### USB Permission Requirements

**Problem:** macOS restricts direct USB device access for security.

**Symptom:**
```
failed to claim usb interface: 0, error: RS2_USB_STATUS_ACCESS
failed to set power state
```

**Solution:** Run RealSense applications with `sudo`:

```bash
sudo python your_realsense_script.py
```

**Why this happens:**
- RealSense uses USB bulk/control transfers
- macOS blocks these for regular user applications
- No official macOS kernel extension (kext) from Intel
- Elevated privileges (sudo) bypass this restriction

### USB 2.0 vs USB 3.0

**Check current USB speed:**

```bash
system_profiler SPUSBDataType | grep -A 10 "RealSense"
```

Look for `Speed: Up to 480 Mb/s` (USB 2.0) vs `Speed: Up to 5 Gb/s` (USB 3.0).

**⚠️ CRITICAL: Known D435 USB-C Cable Issue**

The RealSense D435 has a **documented firmware-level issue** causing USB 2.1 enumeration even with USB 3.0 cables and ports. This affects many users on all platforms.

**Root Cause (Confirmed by Intel):**
- **Slow insertion**: When the USB-C connector is inserted slowly, the camera's firmware enumerates as USB 2.0/2.1 instead of USB 3.0
- **Cable quality**: Only certain high-quality cables work reliably - many generic cables fail even if marked "USB 3.0"
- **Cable direction**: Some USB-C cables only work in USB 3.0 mode in one orientation (flip connector 180°)
- Intel quote: *"Slow-insertion is currently a known issue, we are looking for firmware work-arounds"*

**Solutions (in order of effectiveness):**

1. **Use Original Intel Cable** (Most Reliable)
   - The black USB-C cable that came with your D435
   - Multiple users reported: "Only the original cable works"
   - If lost, order replacement from Intel

2. **Use Thunderbolt 3/4 Cable** (Highly Recommended)
   - ✅ Thunderbolt 3/4 cables are backward compatible with USB 3.1
   - ✅ Guaranteed to have all data pins wired correctly
   - ✅ High quality manufacturing standards
   - Look for ⚡ thunderbolt symbol on connector
   - Often came with MacBook Pro or external drives
   - **This solves the problem for most users**

3. **Quick, Firm Insertion Technique**
   ```bash
   # DO NOT insert slowly!
   # 1. Unplug camera completely
   # 2. Wait 5 seconds
   # 3. Insert USB-C plug in ONE QUICK, FIRM MOTION
   # 4. Check speed immediately:
   system_profiler SPUSBDataType | grep -A 3 "RealSense"
   ```

4. **Try Cable in Reverse**
   ```bash
   # Some USB-C cables only work in one direction
   # Unplug and flip the connector 180 degrees
   # Insert quickly and test again
   ```

5. **Recommended Third-Party Cables** (if original unavailable)
   - Cable Matters USB 3.1 Gen 1 Type-C cable
   - Anker PowerLine USB-C 3.1 Gen 2 (3ft/6ft)
   - Belkin USB-C 3.1 Gen 1
   - **Must be marked**: "USB 3.1 Gen 1" or "SuperSpeed USB 5Gbps"
   - Look for "SS" (SuperSpeed) symbol on connector

**Cables to AVOID:**
- ❌ Generic "USB-C cables" without USB 3.0 marking
- ❌ Charging cables (often USB 2.0 only for cost savings)
- ❌ Thin/flexible cables (likely missing USB 3.0 data pins)
- ❌ Cables from phone chargers or power banks

**Verification After Cable Change:**

```bash
# Check hardware level speed
system_profiler SPUSBDataType | grep -A 15 "RealSense"

# Look for these indicators:
# USB 3.0: "Speed: Up to 5 Gb/s"
# USB 2.0: "Speed: Up to 480 Mb/s" ← Problem!

# Also check with librealsense
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-enumerate-devices" | grep "Usb Type"

# USB 3.0 shows: "Usb Type Descriptor: 3.2"
# USB 2.0 shows: "Usb Type Descriptor: 2.1" ← Problem!
```

**Performance Impact:**
- **USB 2.0** (480 Mb/s):
  - ⚠️ Limited to 15 fps max
  - ⚠️ Single stream only (depth OR color, not both)
  - ⚠️ Lower resolutions only
  - ✅ Good enough for testing/development

- **USB 3.0** (5 Gb/s):
  - ✅ Full 30 fps on both streams
  - ✅ Simultaneous depth + color streaming
  - ✅ High resolution modes (1280x720, 1920x1080)
  - ✅ Multiple cameras simultaneously

**If Stuck at USB 2.0:**

The camera will still work for basic testing, but you'll need a proper USB 3.0 cable for production use. Try borrowing a Thunderbolt 3/4 cable from another device as a quick test.

### Camera Locked Status

If enumeration shows `Camera Locked: YES`, this is normal and doesn't prevent operation. It's a security feature that restricts certain advanced calibration operations.

---

## Troubleshooting

### Camera Not Detected

**Check 1: Is it visible to macOS?**

```bash
system_profiler SPUSBDataType | grep -i "realsense\|intel"
```

Should show:
```
Intel(R) RealSense(TM) Depth Camera 435 :
  Product ID: 0x0b07
  Vendor ID: 0x8086  (Intel Corporation)
```

**Check 2: Try with sudo**

```bash
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-enumerate-devices"
```

**Check 3: Reset the camera**

```bash
# Unplug USB cable
# Wait 10 seconds
# Plug back in
# Try again
```

### "failed to set power state" Error

**Cause:** USB permission issue or camera in locked state

**Solutions:**
1. Always use `sudo` for RealSense commands on macOS
2. Reset camera (unplug/replug with 10 second wait)
3. Kill background processes: `sudo pkill -f pyrealsense2`
4. Check no other software is accessing the camera

### Streaming Hangs or Crashes

**⚠️ KNOWN ISSUE (2025-01-16):** RealSense initialization hangs indefinitely on macOS when calling `pipeline.start()`. This is an open issue being investigated. See [`docs/known-issues.md`](known-issues.md) for details.

**Current Workaround:**

RealSense is disabled by default in the Access Ability Arm application. To enable:

```bash
# Run without RealSense (default, safe)
python main.py

# Run with RealSense enabled (may hang during initialization)
python main.py --enable-realsense
```

If you encounter hanging:

**Solution 1: Check for background processes**

```bash
ps aux | grep -i realsense
sudo pkill -f pyrealsense2
```

**Solution 2: Reset camera and try with fresh pipeline**

```python
# Don't enumerate devices on macOS - go straight to pipeline
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
pipeline.start(config)  # This is more reliable than ctx.query_devices()
```

**Solution 3: Check camera permissions**

```bash
# Reset macOS camera service
sudo killall VDCAssistant

# Check for processes holding camera
lsof | grep -i realsense
```

### Camera Stuck at USB 2.1 / USB 2.0

**Problem:** Camera shows `Usb Type Descriptor: 2.1` and `Speed: Up to 480 Mb/s` instead of USB 3.0.

**This is the #1 most common RealSense issue!** See detailed documentation in the [USB 2.0 vs USB 3.0 section](#usb-20-vs-usb-30) above.

**Quick Diagnostic:**

```bash
# Check hardware speed
system_profiler SPUSBDataType | grep -A 15 "RealSense" | grep Speed

# Expected: "Speed: Up to 5 Gb/s" (USB 3.0) ✅
# Problem:  "Speed: Up to 480 Mb/s" (USB 2.0) ❌
```

**Quick Fixes (Try in Order):**

1. **Test with Thunderbolt 3/4 Cable** (if available)
   - Thunderbolt cables work reliably with RealSense
   - Look for ⚡ symbol on connector
   - Often included with MacBook Pro or external drives

2. **Quick Insertion Technique**
   ```bash
   # Unplug camera completely
   # Wait 5 seconds
   # Insert USB-C connector in ONE QUICK MOTION (firmware issue with slow insertion!)
   # Verify: system_profiler SPUSBDataType | grep -A 3 "RealSense"
   ```

3. **Flip Cable Orientation**
   ```bash
   # Some USB-C cables only work in one direction
   # Unplug and rotate connector 180°
   # Insert quickly and test
   ```

4. **Use Original Intel Cable**
   - The black cable that came with the D435
   - Community consensus: "Only the original cable works"
   - If lost, order from Intel or use Thunderbolt 3/4 cable

5. **Verify Cable Specifications**
   - Must support USB 3.1 Gen 1 (5 Gbps) minimum
   - Look for "SS" (SuperSpeed) marking
   - Avoid: charging cables, generic cables, thin/flexible cables

**Reference:** See [USB 2.0 vs USB 3.0](#usb-20-vs-usb-30) for comprehensive troubleshooting including:
- Firmware slow-insertion issue details
- Recommended cable brands
- Performance impact comparison
- Community-reported solutions

### Build Errors

**Error: `vulkan-sdk` not found**

```bash
# Use individual Vulkan components instead
brew install vulkan-loader vulkan-headers molten-vk vulkan-tools
```

**Error: `libusb not found`**

```bash
brew install libusb
export LIBRARY_PATH=/opt/homebrew/lib
```

**Error: Python bindings not found after build**

Check these locations:
- `build/Release/pyrealsense2.cpython-311-darwin.so`
- `build/wrappers/python/`

Copy the `.so` file directly to your venv site-packages.

---

## Additional Resources

### Useful Commands

```bash
# List all RealSense tools
ls "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/"

# Check firmware update help
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-fw-update" --help

# Backup current firmware
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-fw-update" \
  -s SERIAL_NUMBER -b ~/realsense_firmware_backup.bin

# Recovery mode (if camera becomes unresponsive)
sudo "/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/build/Release/rs-fw-update" -r
```

### Official Documentation

- [librealsense GitHub](https://github.com/IntelRealSense/librealsense)
- [macOS Installation Guide](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_osx.md)
- [Python API Documentation](https://intelrealsense.github.io/librealsense/python_docs/)

### Project Files

- Test script: `scripts/test_realsense.py`
- SDK location: `/Users/ck432/Dropbox/brh/Access Ability Arm/librealsense/`
- Python bindings: `venv/lib/python3.11/site-packages/pyrealsense2.cpython-311-darwin.so`

---

## Summary

### What Works ✅

- librealsense SDK 2.56.5 built from source
- pyrealsense2 Python bindings installed
- Camera enumeration with sudo
- Firmware update via command line
- Streaming depth and color data
- Integration with Python applications

### What Doesn't Work ⚠️

- RealSense Viewer GUI (OpenGL crashes on macOS)
- Camera access without sudo (macOS USB restrictions)
- Most USB-C cables (firmware slow-insertion issue causes USB 2.0 fallback)

### Best Practices

1. **Use proper USB cable** - Original Intel cable or Thunderbolt 3/4 cable (most critical!)
2. **Quick cable insertion** - Insert USB-C connector quickly and firmly (firmware issue)
3. **Always use sudo** for RealSense operations on macOS
4. **Reset camera** (unplug 10s) before firmware updates
5. **Use serial number flag** (`-s`) for firmware updates
6. **Verify USB 3.0** connection - Check `system_profiler` shows "5 Gb/s" not "480 Mb/s"
7. **Skip device enumeration** in code - Go straight to pipeline
8. **Keep firmware updated** - Version 5.17.0.10+ for best macOS compatibility

---

**Last Updated:** November 16, 2025
**SDK Version:** librealsense 2.56.5
**Tested On:** macOS Sequoia 24.6.0 (Apple Silicon)
**Camera:** Intel RealSense D435 (Firmware 5.17.0.10)
