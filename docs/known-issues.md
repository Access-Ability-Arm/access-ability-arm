# Known Issues

## RealSense Camera Initialization Hangs

**Status**: Open  
**Severity**: High  
**Affects**: macOS (tested on macOS 14.x with M-series chip)

### Description

When a RealSense camera (D435) is physically connected, the initialization hangs indefinitely at "Loading Intel Realsense Camera" message. This affects:

1. **Direct RealSense initialization**: Calling `RealsenseCamera()` in `packages/core/src/aaa_core/hardware/realsense_camera.py` blocks indefinitely in `pipeline.start()`
2. **OpenCV fallback**: Even when RealSense is disabled, `cv2.VideoCapture(0)` hangs if camera index 0 is the RealSense device

### Symptoms

- App shows "Loading Intel Realsense Camera" and never progresses
- Cannot switch cameras using dropdown
- App becomes unresponsive and must be force-killed
- High CPU usage (48%+) during hang

### Console Output

```
[DEBUG ImageProcessor] Creating RealSense camera object...
Loading Intel Realsense Camera
<hangs indefinitely>
```

### Root Cause

The `pyrealsense2` library's `pipeline.start()` method blocks the calling thread indefinitely when:
- RealSense firmware/driver issue
- Camera is in use by another process
- Incorrect camera configuration
- macOS USB/camera permission issues

Python's threading cannot interrupt a blocked C/C++ library call, making timeout mechanisms ineffective:
- `signal.SIGALRM` only works in main thread
- `threading.Thread.join(timeout=X)` waits but cannot kill the blocked thread
- The thread remains alive and blocked even after timeout

### Current Workaround

**Important macOS Limitation**: The RealSense D435 RGB module does NOT appear as a UVC camera on macOS. Only the infrared/depth stream is accessible through OpenCV without the SDK.

**Option 1: Use Standard Webcam (Default, Recommended)**:

```bash
# Run with MacBook camera or other webcam (camera index 1+)
python main.py
# or
make run
```

On macOS, camera 0 = RealSense infrared (grayscale), camera 1+ = other cameras (MacBook, etc.). Use camera 1 for RGB color without RealSense SDK.

**Option 2: RealSense with Depth Support (Advanced)**:

```bash
# Run with full RealSense SDK (RGB color + depth enabled, requires sudo)
./scripts/launch_with_realsense.sh
# or
make run-realsense
```

⚠️ **Known Limitation**: On macOS, the RealSense SDK requires `sudo` for USB bulk transfers. However, Flet/Flutter GUI frameworks do not support running with elevated privileges (black window appears). This is a fundamental limitation of the GUI framework, not a bug.

**Why this happens**:
- macOS restricts USB bulk/control transfers for security
- RealSense SDK needs direct USB access for RGB color + depth data
- Flet/Flutter run in user context and cannot display GUI under sudo
- No workaround exists without rewriting the app architecture

**macOS Camera Mapping**:
- Camera 0: RealSense infrared/depth stream (grayscale, UVC)
- Camera 1+: MacBook Pro, Continuity, etc. (RGB color, UVC)
- RealSense RGB: NOT accessible as UVC device on macOS (SDK only)

**Implementation**:
- `main.py`: Added `--enable-realsense` command-line flag
- `image_processor.py`: Checks `sys._enable_realsense_override` flag
- When disabled: Uses OpenCV with camera index 1+ for RGB color (MacBook camera)
- When enabled: Uses RealSense SDK for RGB color + depth (requires sudo, GUI issues)

### Attempted Solutions

1. **Signal-based timeout** ❌
   - `signal.SIGALRM` only works in main thread
   - RealSense init happens in background thread
   
2. **Thread with timeout** ❌
   - `thread.join(timeout=5)` detects timeout but cannot kill thread
   - Blocked C library call remains stuck
   
3. **OpenCV fallback** ❌
   - `cv2.VideoCapture(0)` also hangs when opening RealSense device
   
4. **Skip camera 0** ✅ (current workaround)
   - Works but prevents using RealSense altogether

### Potential Solutions (TODO)

1. **Fix RealSense initialization**:
   - Investigate why `pipeline.start()` hangs
   - Check RealSense firmware version
   - Test with different RealSense SDK versions
   - Check macOS camera permissions
   - Ensure no other process is using camera

2. **Subprocess isolation**:
   - Run RealSense initialization in separate subprocess
   - Use `multiprocessing.Process` with timeout
   - Kill subprocess if it hangs
   - More overhead but fully isolated

3. **Better camera detection**:
   - Detect RealSense cameras by name before attempting to open
   - Skip RealSense devices in OpenCV enumeration when disabled
   - Provide UI warning when RealSense is detected but disabled

4. **Configuration option**:
   - Add config.yaml setting to permanently disable RealSense
   - Avoid command-line flag requirement

### Related Files

- `packages/core/src/aaa_core/workers/image_processor.py` - Camera initialization
- `packages/core/src/aaa_core/hardware/realsense_camera.py` - RealSense wrapper
- `packages/core/src/aaa_core/hardware/camera_manager.py` - Camera enumeration
- `main.py` - Command-line argument parsing

### Related Documentation

- [`docs/realsense-setup.md`](realsense-setup.md) - Complete RealSense installation and setup guide
  - Includes general troubleshooting for RealSense cameras
  - USB 3.0 cable issues and solutions
  - Firmware update procedures
  - macOS-specific configuration

### Testing Needed

- [ ] Test RealSense on different macOS versions
- [ ] Test RealSense on Windows
- [ ] Test RealSense on Linux
- [ ] Check RealSense firmware version requirements
- [ ] Test with different pyrealsense2 versions
- [ ] Investigate macOS camera permission dialogs
- [ ] Test subprocess-based initialization

### User Impact

**Workaround works**: Users can use the app with standard webcams by running `python main.py` (default).

**RealSense users affected**: Users who need depth sensing must use `--enable-realsense` flag and risk hanging.

---

**Last Updated**: 2025-01-16
**Reported By**: System
**Assigned To**: Unassigned

---

## RealSense RGB Module Not Accessible on macOS (UVC Limitation)

**Status**: Won't Fix (macOS limitation)
**Severity**: Medium
**Affects**: macOS only (all versions)

### Description

The Intel RealSense D435 camera exposes different video streams on macOS vs Windows:

**Windows (UVC Full Support)**:
- Camera 0: RealSense Infrared/Depth (grayscale)
- Camera 1: RealSense RGB Color (1920x1080)
- Both accessible via OpenCV without SDK

**macOS (UVC Limited Support)**:
- Camera 0: RealSense Infrared/Depth (grayscale) ✅
- Camera X: RealSense RGB Color ❌ NOT ACCESSIBLE
- RGB only available through RealSense SDK

### Root Cause

This is a platform-specific limitation:
- macOS AVFoundation does not expose the RealSense RGB module as a UVC device
- Windows UVC driver properly enumerates both infrared and RGB streams
- Only the infrared/depth stream appears in `system_profiler SPCameraDataType`
- The RGB module requires librealsense SDK for access on macOS

### Workarounds

**1. Use MacBook Pro Camera (Recommended)**:
```bash
# config/config.yaml
camera:
  default_camera: 1  # 0=RealSense IR, 1=MacBook Pro RGB
```

**2. Enable RealSense SDK for RGB + Depth**:
```bash
python main.py --enable-realsense  # Requires sudo, GUI issues
```

### Impact

- **Minor**: Most users have built-in MacBook cameras for RGB
- **Moderate**: Users specifically wanting RealSense RGB must use SDK
- **No Workaround**: Cannot get RealSense RGB via OpenCV on macOS

### References

- [GitHub Issue #3874](https://github.com/IntelRealSense/librealsense/issues/3874): RGB camera doesn't show up on Mac
- [StackOverflow](https://stackoverflow.com/questions/63235022): Changing RealSense default from depth to RGB with OpenCV
- Intel Forums: Multiple reports of macOS UVC limitations

---

**Last Updated**: 2025-11-16
**Reported By**: User Testing
**Status**: Documented (platform limitation)
