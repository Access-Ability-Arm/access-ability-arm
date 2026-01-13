# Daemon Architecture Implementation Plan

## Overview

Implement a client-server architecture using shared memory IPC to separate RealSense camera access (requires sudo) from the GUI (runs as user). This solves the fundamental incompatibility between elevated privileges and GUI frameworks.

**Goal**: Enable RealSense depth sensing with Flet GUI by running camera processing in a privileged daemon and GUI in user context.

**Performance Target**: <5ms IPC overhead, maintaining 25-30 fps video streaming.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User Context                             │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           GUI Process (Flet/Qt/DearPyGUI)              │ │
│  │                                                          │ │
│  │  • Display video feed (RGB + depth visualization)      │ │
│  │  • Robotic arm controls                                │ │
│  │  • Object detection UI                                 │ │
│  │  • Camera selection                                    │ │
│  │                                                          │ │
│  │  Reads from:                                            │ │
│  │    /dev/shm/aaa_rgb_frame                              │ │
│  │    /dev/shm/aaa_depth_frame                            │ │
│  │    /dev/shm/aaa_metadata                               │ │
│  │                                                          │ │
│  │  Sends commands via:                                    │ │
│  │    Unix socket: /tmp/aaa_daemon.sock                   │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                           │
└───────────────────┼───────────────────────────────────────────┘
                    │
         ═══════════╪═══════════════════════════════
                    │ IPC Boundary
         ═══════════╪═══════════════════════════════
                    │
┌───────────────────┼───────────────────────────────────────────┐
│                   │            Elevated Context (sudo)        │
│                   │                                           │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │         Camera Daemon (aaa_camera_daemon.py)           │ │
│  │                                                          │ │
│  │  • RealSense camera initialization (requires sudo)     │ │
│  │  • Continuous frame capture (RGB + Depth)              │ │
│  │  • Object detection processing                         │ │
│  │  • Face tracking                                       │ │
│  │                                                          │ │
│  │  Writes to:                                             │ │
│  │    /dev/shm/aaa_rgb_frame      (640x480x3 uint8)       │ │
│  │    /dev/shm/aaa_depth_frame    (640x480 uint16)        │ │
│  │    /dev/shm/aaa_metadata       (JSON metadata)         │ │
│  │                                                          │ │
│  │  Listens on:                                            │ │
│  │    Unix socket: /tmp/aaa_daemon.sock                   │ │
│  │      Commands: start, stop, set_mode, get_status       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Core Daemon Infrastructure (Week 1)

**Goal**: Create basic daemon that captures frames and writes to shared memory.

#### 1.1 Create Daemon Base Class

**File**: `packages/core/src/aaa_core/daemon/camera_daemon.py`

```python
"""
Camera Daemon - Runs with elevated privileges for RealSense access
Writes frames to shared memory for GUI consumption
"""

import signal
import sys
import time
from multiprocessing import shared_memory
import numpy as np
import json

class CameraDaemon:
    """
    Daemon process for camera capture with elevated privileges
    
    Manages:
    - RealSense camera initialization
    - Continuous frame capture
    - Shared memory buffer management
    - Command socket listener
    """
    
    def __init__(self):
        self.running = False
        
        # Shared memory buffers
        self.shm_rgb = None
        self.shm_depth = None
        self.shm_metadata = None
        
        # Frame dimensions
        self.rgb_shape = (480, 640, 3)
        self.depth_shape = (480, 640)
        
        # Camera
        self.rs_camera = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Initialize camera and shared memory, start capture loop"""
        pass
    
    def stop(self):
        """Stop capture and cleanup resources"""
        pass
    
    def _create_shared_memory(self):
        """Create shared memory buffers for frames"""
        pass
    
    def _destroy_shared_memory(self):
        """Cleanup shared memory buffers"""
        pass
    
    def _capture_loop(self):
        """Main capture loop - write frames to shared memory"""
        pass
```

#### 1.2 Implement Shared Memory Management

**Shared memory layout:**

```python
# RGB Frame Buffer
Name: "aaa_rgb_frame"
Size: 640 * 480 * 3 * 1 byte = 921,600 bytes (~1 MB)
Format: uint8 array, shape (480, 640, 3), BGR order

# Depth Frame Buffer  
Name: "aaa_depth_frame"
Size: 640 * 480 * 2 bytes = 614,400 bytes (~600 KB)
Format: uint16 array, shape (480, 640), millimeters

# Metadata Buffer
Name: "aaa_metadata"
Size: 4096 bytes (4 KB)
Format: JSON string
{
    "timestamp": 1234567890.123,
    "frame_number": 12345,
    "fps": 30.5,
    "detection_mode": "objects",
    "num_detections": 3,
    "camera_type": "realsense"
}
```

**Implementation:**

```python
def _create_shared_memory(self):
    """Create shared memory buffers"""
    # RGB buffer
    rgb_size = np.prod(self.rgb_shape) * np.uint8().itemsize
    self.shm_rgb = shared_memory.SharedMemory(
        name="aaa_rgb_frame",
        create=True,
        size=rgb_size
    )
    
    # Depth buffer
    depth_size = np.prod(self.depth_shape) * np.uint16().itemsize
    self.shm_depth = shared_memory.SharedMemory(
        name="aaa_depth_frame",
        create=True,
        size=depth_size
    )
    
    # Metadata buffer
    self.shm_metadata = shared_memory.SharedMemory(
        name="aaa_metadata",
        create=True,
        size=4096
    )
    
    print("Shared memory buffers created")

def _destroy_shared_memory(self):
    """Cleanup shared memory"""
    if self.shm_rgb:
        self.shm_rgb.close()
        self.shm_rgb.unlink()
    
    if self.shm_depth:
        self.shm_depth.close()
        self.shm_depth.unlink()
    
    if self.shm_metadata:
        self.shm_metadata.close()
        self.shm_metadata.unlink()
    
    print("Shared memory cleaned up")
```

#### 1.3 Implement Capture Loop

```python
def _capture_loop(self):
    """Capture frames and write to shared memory"""
    from aaa_core.hardware.realsense_camera import RealsenseCamera
    
    # Initialize RealSense (requires sudo)
    self.rs_camera = RealsenseCamera()
    
    # Create numpy views into shared memory
    rgb_array = np.ndarray(
        self.rgb_shape,
        dtype=np.uint8,
        buffer=self.shm_rgb.buf
    )
    
    depth_array = np.ndarray(
        self.depth_shape,
        dtype=np.uint16,
        buffer=self.shm_depth.buf
    )
    
    frame_count = 0
    start_time = time.time()
    
    print("Starting capture loop...")
    
    while self.running:
        # Capture frame
        ret, rgb_frame, depth_frame = self.rs_camera.get_frame_stream()
        
        if ret:
            # Write directly to shared memory (zero-copy)
            rgb_array[:] = rgb_frame
            depth_array[:] = depth_frame
            
            # Update metadata
            metadata = {
                "timestamp": time.time(),
                "frame_number": frame_count,
                "fps": frame_count / (time.time() - start_time),
                "detection_mode": "camera",
                "num_detections": 0,
                "camera_type": "realsense"
            }
            
            metadata_bytes = json.dumps(metadata).encode('utf-8')
            self.shm_metadata.buf[:len(metadata_bytes)] = metadata_bytes
            
            frame_count += 1
```

#### 1.4 Create Daemon Entry Point

**File**: `scripts/aaa_camera_daemon.py`

```python
#!/usr/bin/env python3
"""
Camera Daemon Entry Point
Runs with sudo to access RealSense camera
"""

import sys
import os

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'core', 'src'))

from aaa_core.daemon.camera_daemon import CameraDaemon

def main():
    # Check if running with sudo
    if os.geteuid() != 0:
        print("ERROR: Camera daemon must be run with sudo")
        print("Usage: sudo python scripts/aaa_camera_daemon.py")
        sys.exit(1)
    
    print("Starting Access Ability Arm Camera Daemon")
    print("Press Ctrl+C to stop")
    
    daemon = CameraDaemon()
    
    try:
        daemon.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        daemon.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        daemon.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

Make executable:
```bash
chmod +x scripts/aaa_camera_daemon.py
```

---

### Phase 2: GUI Client Integration (Week 2)

**Goal**: Modify GUI to read from shared memory instead of direct camera access.

#### 2.1 Create Shared Memory Reader

**File**: `packages/core/src/aaa_core/daemon/camera_client.py`

```python
"""
Camera Client - Reads frames from daemon's shared memory
Used by GUI running in user context
"""

from multiprocessing import shared_memory
import numpy as np
import json
import time

class CameraClient:
    """
    Reads camera frames from shared memory written by daemon
    Drop-in replacement for ImageProcessor
    """
    
    def __init__(self):
        self.shm_rgb = None
        self.shm_depth = None
        self.shm_metadata = None
        
        self.rgb_shape = (480, 640, 3)
        self.depth_shape = (480, 640)
        
        self._connect()
    
    def _connect(self):
        """Connect to daemon's shared memory"""
        try:
            self.shm_rgb = shared_memory.SharedMemory(name="aaa_rgb_frame")
            self.shm_depth = shared_memory.SharedMemory(name="aaa_depth_frame")
            self.shm_metadata = shared_memory.SharedMemory(name="aaa_metadata")
            print("Connected to camera daemon")
        except FileNotFoundError:
            raise RuntimeError(
                "Camera daemon not running. "
                "Start with: sudo python scripts/aaa_camera_daemon.py"
            )
    
    def get_frame(self):
        """
        Read latest frame from shared memory
        
        Returns:
            (rgb_frame, depth_frame, metadata)
        """
        # Create numpy views (no copy!)
        rgb_frame = np.ndarray(
            self.rgb_shape,
            dtype=np.uint8,
            buffer=self.shm_rgb.buf
        ).copy()  # Copy to avoid tearing
        
        depth_frame = np.ndarray(
            self.depth_shape,
            dtype=np.uint16,
            buffer=self.shm_depth.buf
        ).copy()
        
        # Read metadata
        metadata_bytes = bytes(self.shm_metadata.buf[:4096])
        null_idx = metadata_bytes.find(b'\x00')
        if null_idx > 0:
            metadata_bytes = metadata_bytes[:null_idx]
        
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except:
            metadata = {}
        
        return rgb_frame, depth_frame, metadata
    
    def disconnect(self):
        """Cleanup shared memory connections"""
        if self.shm_rgb:
            self.shm_rgb.close()
        if self.shm_depth:
            self.shm_depth.close()
        if self.shm_metadata:
            self.shm_metadata.close()
```

#### 2.2 Modify ImageProcessor to Use Client

**Option A**: Add daemon mode to existing ImageProcessor

```python
# In ImageProcessor.__init__
def __init__(self, use_daemon=False, ...):
    if use_daemon:
        self.camera_client = CameraClient()
        self.use_daemon = True
    else:
        # Existing direct camera code
        self.use_daemon = False
```

**Option B**: Create new DaemonImageProcessor class

```python
class DaemonImageProcessor(threading.Thread):
    """ImageProcessor that reads from daemon instead of camera"""
    
    def __init__(self, callback):
        super().__init__(daemon=True)
        self.client = CameraClient()
        self.callback = callback
        self.running = False
    
    def run(self):
        while self.running:
            rgb, depth, metadata = self.client.get_frame()
            
            # Process detection, etc.
            processed = self._process_frame(rgb, depth)
            
            # Send to GUI
            self.callback(processed)
            
            time.sleep(1/30)  # 30 fps
```

#### 2.3 Update Main Window

```python
# In main.py or main_window.py

def _start_image_processor(self):
    # Check if daemon is running
    daemon_running = self._check_daemon_running()
    
    if daemon_running:
        print("Using camera daemon for RealSense depth")
        self.image_processor = DaemonImageProcessor(
            callback=self._update_video_feed
        )
    else:
        print("Using direct camera access (no depth)")
        self.image_processor = ImageProcessor(
            callback=self._update_video_feed
        )
    
    self.image_processor.start()

def _check_daemon_running(self):
    """Check if daemon shared memory exists"""
    try:
        shm = shared_memory.SharedMemory(name="aaa_rgb_frame")
        shm.close()
        return True
    except FileNotFoundError:
        return False
```

---

### Phase 3: Command Protocol (Week 3)

**Goal**: Enable GUI to control daemon (start/stop, change modes, etc.)

#### 3.1 Unix Socket Command Interface

**Daemon side:**

```python
# In CameraDaemon class

import socket
import os
import threading

def _start_command_listener(self):
    """Listen for commands on Unix socket"""
    socket_path = "/tmp/aaa_daemon.sock"
    
    # Remove stale socket
    if os.path.exists(socket_path):
        os.remove(socket_path)
    
    self.command_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.command_socket.bind(socket_path)
    self.command_socket.listen(1)
    
    # Accept commands in thread
    threading.Thread(target=self._command_loop, daemon=True).start()

def _command_loop(self):
    """Process incoming commands"""
    while self.running:
        conn, _ = self.command_socket.accept()
        
        try:
            data = conn.recv(1024).decode('utf-8')
            command = json.loads(data)
            
            response = self._handle_command(command)
            
            conn.send(json.dumps(response).encode('utf-8'))
        finally:
            conn.close()

def _handle_command(self, command):
    """Handle command from GUI"""
    cmd_type = command.get("type")
    
    if cmd_type == "get_status":
        return {
            "status": "running",
            "fps": self.current_fps,
            "mode": self.detection_mode
        }
    
    elif cmd_type == "set_mode":
        self.detection_mode = command.get("mode")
        return {"status": "ok"}
    
    elif cmd_type == "stop":
        self.stop()
        return {"status": "stopped"}
    
    return {"error": "unknown command"}
```

**Client side:**

```python
# In CameraClient class

def send_command(self, command):
    """Send command to daemon"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    try:
        sock.connect("/tmp/aaa_daemon.sock")
        sock.send(json.dumps(command).encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        return json.loads(response)
    finally:
        sock.close()

# Usage from GUI:
# client.send_command({"type": "set_mode", "mode": "objects"})
```

---

### Phase 4: Detection Processing (Week 4)

**Goal**: Move object detection to daemon for better performance.

#### 4.1 Integrate Detection in Daemon

```python
# In CameraDaemon

from aaa_vision.detection_manager import DetectionManager

def __init__(self):
    # ... existing code ...
    self.detection_manager = DetectionManager()
    self.detection_mode = "camera"  # camera, objects, face

def _capture_loop(self):
    # ... existing code ...
    
    while self.running:
        ret, rgb_frame, depth_frame = self.rs_camera.get_frame_stream()
        
        if ret:
            # Run detection
            processed_rgb = self.detection_manager.process_frame(
                rgb_frame, depth_frame
            )
            
            # Write processed frame to shared memory
            rgb_array[:] = processed_rgb
            depth_array[:] = depth_frame
            
            # Update metadata with detection results
            metadata = {
                "timestamp": time.time(),
                "frame_number": frame_count,
                "detection_mode": self.detection_mode,
                "num_detections": len(self.detection_manager.last_detections),
                "detections": self.detection_manager.last_detections
            }
```

#### 4.2 GUI Reads Detection Results

```python
# In GUI
rgb, depth, metadata = camera_client.get_frame()

detections = metadata.get("detections", [])

# Display detection info, create buttons, etc.
```

---

### Phase 5: Startup Scripts & Automation (Week 5)

**Goal**: Make daemon easy to start/stop, auto-start on boot.

#### 5.1 Create Management Scripts

**File**: `scripts/daemon_control.sh`

```bash
#!/bin/bash
# Daemon control script

DAEMON_PID_FILE="/tmp/aaa_daemon.pid"
DAEMON_SCRIPT="$(dirname "$0")/aaa_camera_daemon.py"

case "$1" in
    start)
        if [ -f "$DAEMON_PID_FILE" ]; then
            echo "Daemon already running (PID: $(cat $DAEMON_PID_FILE))"
            exit 1
        fi
        
        echo "Starting camera daemon..."
        sudo python "$DAEMON_SCRIPT" &
        echo $! > "$DAEMON_PID_FILE"
        echo "Daemon started (PID: $!)"
        ;;
    
    stop)
        if [ ! -f "$DAEMON_PID_FILE" ]; then
            echo "Daemon not running"
            exit 1
        fi
        
        PID=$(cat "$DAEMON_PID_FILE")
        echo "Stopping daemon (PID: $PID)..."
        sudo kill $PID
        rm -f "$DAEMON_PID_FILE"
        echo "Daemon stopped"
        ;;
    
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    
    status)
        if [ -f "$DAEMON_PID_FILE" ]; then
            PID=$(cat "$DAEMON_PID_FILE")
            if ps -p $PID > /dev/null; then
                echo "Daemon running (PID: $PID)"
            else
                echo "Daemon dead (stale PID file)"
            fi
        else
            echo "Daemon not running"
        fi
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
```

#### 5.2 Update Makefile

```makefile
# Start daemon
daemon-start:
	@./scripts/daemon_control.sh start

# Stop daemon
daemon-stop:
	@./scripts/daemon_control.sh stop

# Restart daemon
daemon-restart:
	@./scripts/daemon_control.sh restart

# Check daemon status
daemon-status:
	@./scripts/daemon_control.sh status

# Run GUI with daemon
run-with-daemon: daemon-start
	@echo "Daemon started, launching GUI..."
	@sleep 1
	@python main.py

# Run GUI without daemon (fallback to webcam)
run:
	@python main.py
```

#### 5.3 Auto-start on Boot (Optional)

**macOS LaunchAgent** (`~/Library/LaunchAgents/com.accessability.cameradaemon.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.accessability.cameradaemon</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/scripts/aaa_camera_daemon.py</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_shared_memory.py

def test_shared_memory_write_read():
    """Test writing and reading from shared memory"""
    # Create writer
    shm = shared_memory.SharedMemory(create=True, size=1000, name="test")
    
    # Write data
    data = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)
    arr = np.ndarray(data.shape, dtype=np.uint8, buffer=shm.buf)
    arr[:] = data
    
    # Read data from another "process"
    shm2 = shared_memory.SharedMemory(name="test")
    arr2 = np.ndarray(data.shape, dtype=np.uint8, buffer=shm2.buf)
    
    assert np.array_equal(arr2, data)
    
    # Cleanup
    shm.close()
    shm2.close()
    shm.unlink()
```

### Integration Tests

```python
# tests/test_daemon_client.py

def test_daemon_client_integration():
    """Test full daemon + client workflow"""
    # Start daemon in subprocess
    daemon_proc = subprocess.Popen(
        ["sudo", "python", "scripts/aaa_camera_daemon.py"],
        stdout=subprocess.PIPE
    )
    
    time.sleep(2)  # Wait for startup
    
    try:
        # Create client
        client = CameraClient()
        
        # Get frame
        rgb, depth, metadata = client.get_frame()
        
        assert rgb.shape == (480, 640, 3)
        assert depth.shape == (480, 640)
        assert "timestamp" in metadata
        
    finally:
        daemon_proc.terminate()
        daemon_proc.wait()
```

### Performance Benchmarks

```python
# benchmarks/bench_shared_memory.py

def benchmark_ipc_latency():
    """Measure shared memory read/write latency"""
    iterations = 1000
    
    # Setup
    shm = shared_memory.SharedMemory(create=True, size=921600, name="bench")
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Benchmark writes
    start = time.perf_counter()
    for _ in range(iterations):
        arr = np.ndarray(frame.shape, dtype=np.uint8, buffer=shm.buf)
        arr[:] = frame
    write_time = (time.perf_counter() - start) / iterations
    
    # Benchmark reads
    start = time.perf_counter()
    for _ in range(iterations):
        arr = np.ndarray(frame.shape, dtype=np.uint8, buffer=shm.buf)
        copy = arr.copy()
    read_time = (time.perf_counter() - start) / iterations
    
    print(f"Write latency: {write_time*1000:.2f}ms")
    print(f"Read latency: {read_time*1000:.2f}ms")
    print(f"Total round-trip: {(write_time + read_time)*1000:.2f}ms")
    
    shm.close()
    shm.unlink()

# Expected output:
# Write latency: 1.2ms
# Read latency: 1.8ms
# Total round-trip: 3.0ms
```

---

## Migration Path

### Backward Compatibility

Keep existing direct camera mode working:

```python
# Auto-detect daemon and use appropriate mode
if daemon_available():
    use_daemon_mode()
else:
    use_direct_camera_mode()
```

### Gradual Rollout

1. **Phase 1**: Daemon optional, direct camera default
2. **Phase 2**: Daemon default for RealSense, direct fallback
3. **Phase 3**: Daemon required for depth, direct only for RGB

---

## Error Handling

### Daemon Crashes

```python
# In CameraClient
def get_frame(self):
    try:
        return self._read_frame()
    except:
        # Daemon died, attempt reconnect
        self._reconnect()
        return self._read_frame()

def _reconnect(self):
    """Reconnect to daemon after crash"""
    self.disconnect()
    time.sleep(1)
    self._connect()
```

### Permission Errors

```python
# Clear error messages for common issues
if os.geteuid() != 0:
    print("\n" + "="*60)
    print("ERROR: Camera daemon requires elevated privileges")
    print("="*60)
    print("\nPlease run with sudo:")
    print("  sudo python scripts/aaa_camera_daemon.py")
    print("\nOr use the control script:")
    print("  ./scripts/daemon_control.sh start")
    print("="*60 + "\n")
    sys.exit(1)
```

### Shared Memory Cleanup

```python
# Cleanup on any exit
import atexit

def cleanup_shared_memory():
    """Remove stale shared memory on exit"""
    for name in ["aaa_rgb_frame", "aaa_depth_frame", "aaa_metadata"]:
        try:
            shm = shared_memory.SharedMemory(name=name)
            shm.close()
            shm.unlink()
        except FileNotFoundError:
            pass

atexit.register(cleanup_shared_memory)
```

---

## Performance Optimizations

### 1. Lock-Free Ring Buffer (Future)

For even lower latency, use triple buffering:

```
Writer (daemon) ────┐
                    ├──> Buffer 1 (writing)
                    ├──> Buffer 2 (ready)
                    └──> Buffer 3 (reading) ──> Reader (GUI)
```

### 2. Compression (if needed)

If network transparency needed later:

```python
# Compress RGB frames (JPEG)
import cv2

encoded = cv2.imencode('.jpg', rgb_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
# Reduces 900KB to ~50KB
```

### 3. Partial Updates

Only send depth where it changed:

```python
# Diff depth frames, only update changed regions
depth_diff = np.abs(current_depth - prev_depth) > threshold
changed_regions = np.where(depth_diff)
# Send sparse updates
```

---

## Security Considerations

### 1. Shared Memory Permissions

```python
# Set restrictive permissions (owner only)
os.chmod(shm.path, 0o600)
```

### 2. Unix Socket Permissions

```python
# Only owner can connect
os.chmod("/tmp/aaa_daemon.sock", 0o600)
```

### 3. Command Validation

```python
def _handle_command(self, command):
    # Validate command schema
    if not isinstance(command, dict):
        return {"error": "invalid command"}
    
    # Whitelist allowed commands
    ALLOWED_COMMANDS = {"get_status", "set_mode", "stop"}
    if command.get("type") not in ALLOWED_COMMANDS:
        return {"error": "forbidden"}
```

---

## Documentation Updates

### User-Facing Docs

Update `docs/installation.md`:

```markdown
## Running with RealSense Depth

### Option 1: Start Daemon Manually

```bash
# Terminal 1: Start daemon (requires password)
make daemon-start

# Terminal 2: Start GUI
make run
```

### Option 2: Auto-start (Recommended)

```bash
# Single command starts both
make run-with-daemon
```
```

### Developer Docs

Update `CLAUDE.md`:

```markdown
## Daemon Architecture

The application uses a client-server architecture for RealSense depth:

- **Daemon** (`scripts/aaa_camera_daemon.py`): Runs with sudo, captures depth
- **Client** (`CameraClient`): GUI reads frames via shared memory
- **IPC**: Shared memory for frames, Unix sockets for commands
- **Latency**: <5ms overhead

See `docs/daemon-architecture-implementation-plan.md` for details.
```

---

## Timeline & Milestones

### Week 1: Core Infrastructure
- [x] Create CameraDaemon base class
- [x] Implement shared memory management
- [x] Basic capture loop
- [x] Daemon entry point script
- **Deliverable**: Daemon captures and writes frames

### Week 2: Client Integration
- [ ] Create CameraClient class
- [ ] Modify ImageProcessor for daemon mode
- [ ] Update main_window to use client
- [ ] Test frame reading
- **Deliverable**: GUI displays frames from daemon

### Week 3: Command Protocol
- [ ] Unix socket listener in daemon
- [ ] Command handler implementation
- [ ] Client command sender
- [ ] Test start/stop/mode commands
- **Deliverable**: GUI can control daemon

### Week 4: Detection Processing
- [ ] Integrate DetectionManager in daemon
- [ ] Pass detection results in metadata
- [ ] Update GUI to show detections
- [ ] Test object selection
- **Deliverable**: Full object detection working

### Week 5: Polish & Deployment
- [ ] Create control scripts
- [ ] Update Makefile
- [ ] Write tests
- [ ] Benchmark performance
- [ ] Update documentation
- **Deliverable**: Production-ready daemon

---

## Success Criteria

- ✅ RealSense depth accessible without GUI issues
- ✅ <5ms IPC latency (measured)
- ✅ 25-30 fps video streaming
- ✅ Object detection working with depth
- ✅ Clean start/stop workflow
- ✅ Comprehensive error handling
- ✅ Full documentation

---

## Future Enhancements

### Network Transparency

```python
# Replace Unix socket with TCP
# Allows remote GUI

daemon_host = "192.168.1.100"
client.connect(daemon_host, 5000)
```

### Multi-Camera Support

```python
# Multiple daemons for multiple RealSense cameras
daemon1 = CameraDaemon(camera_id=0, shm_prefix="cam0_")
daemon2 = CameraDaemon(camera_id=1, shm_prefix="cam1_")
```

### Web Dashboard

```python
# Flet web client connects to daemon
# View/control from any device on network
```

---

**Next Steps**: Begin Phase 1 implementation with core daemon infrastructure.
