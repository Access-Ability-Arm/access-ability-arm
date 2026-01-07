# iPad LiDAR as Backup Depth Sensor

This document explores using iPad Pro's LiDAR sensor as an alternative depth source when RealSense is unavailable.

## Motivation

- RealSense requires complex setup on macOS (daemon with sudo, USB permissions)
- Users may already own an iPad Pro with LiDAR
- iPad offers touchscreen interaction possibilities
- Could serve as both depth sensor AND remote display

## Hardware Requirements

### Supported Devices

| Device | LiDAR | Notes |
|--------|-------|-------|
| iPad Pro 11" (2020+) | Yes | Recommended |
| iPad Pro 12.9" (2020+) | Yes | Recommended |
| iPhone 12 Pro/Pro Max+ | Yes | Smaller screen, but works |
| iPad Air, iPad Mini | No | Not supported |
| Android tablets | No | No viable depth sensors |

### LiDAR Specifications

- **Type**: dToF (direct Time of Flight)
- **Resolution**: ~256x192 pixels
- **Range**: 0-5 meters
- **Accuracy**: ~1cm
- **Frame rate**: Up to 60Hz via ARKit

## Comparison: RealSense vs iPad LiDAR

| Feature | RealSense D435 | iPad Pro LiDAR |
|---------|---------------|----------------|
| Depth Resolution | 1280x720 | 256x192 |
| Depth Accuracy | ~2% at 2m | ~1cm |
| RGB Resolution | 1920x1080 | Up to 4K |
| Range | 0.3-3m | 0-5m |
| Latency | <5ms (USB) | 20-50ms (WiFi) |
| Setup Complexity | High (macOS) | Medium |
| Cost | ~$350 | Already owned? |
| Lighting | IR projected | Works in any light |

### Is 256x192 Depth Resolution Sufficient?

For pick-and-place robotics:
- Each depth pixel covers ~4mm at 1m distance
- Object detection uses high-res RGB (not depth)
- Depth only needed for distance to detected object center
- **Conclusion**: Sufficient for most use cases

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  iPad Pro (iOS Companion App)                           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ARKit Session                                  │    │
│  │  • Captures LiDAR depth (256x192 float32)       │    │
│  │  • Captures RGB video (1280x720 or higher)      │    │
│  │  • Camera intrinsics for alignment              │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                   │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Network Streamer                               │    │
│  │  • Bonjour/mDNS service advertisement           │    │
│  │  • UDP for depth frames (low latency)           │    │
│  │  • TCP for control commands                     │    │
│  └──────────────────┬──────────────────────────────┘    │
└─────────────────────┼───────────────────────────────────┘
                      │
                      │ WiFi / USB (Network over USB)
                      │ ~9 MB/s at 30fps
                      │
┌─────────────────────▼───────────────────────────────────┐
│  Mac/PC (Access Ability Arm)                            │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  iPadDepthClient                                │    │
│  │  • Discovers iPad via Bonjour                   │    │
│  │  • Receives depth + RGB frames                  │    │
│  │  • Same interface as RealsenseCamera            │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                   │
│  ┌──────────────────▼──────────────────────────────┐    │
│  │  Existing Pipeline                              │    │
│  │  • Detection Manager                            │    │
│  │  • Arm Controller                               │    │
│  │  • Flet GUI                                     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: iOS Companion App (Swift/SwiftUI)

**File Structure:**
```
ios-companion/
├── AAADepthStreamer/
│   ├── App.swift
│   ├── ContentView.swift
│   ├── ARSessionManager.swift      # ARKit depth capture
│   ├── NetworkStreamer.swift       # UDP/TCP streaming
│   ├── FrameEncoder.swift          # Compress frames
│   └── Info.plist                  # Camera permissions
└── AAADepthStreamer.xcodeproj
```

**Key Components:**

```swift
// ARSessionManager.swift
import ARKit

class ARSessionManager: NSObject, ARSessionDelegate {
    let session = ARSession()
    var onDepthFrame: ((ARFrame) -> Void)?
    
    func startSession() {
        let config = ARWorldTrackingConfiguration()
        config.frameSemantics = .sceneDepth  // Enable LiDAR
        session.delegate = self
        session.run(config)
    }
    
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard let depthMap = frame.sceneDepth?.depthMap else { return }
        // depthMap is CVPixelBuffer with depth in meters
        onDepthFrame?(frame)
    }
}
```

```swift
// NetworkStreamer.swift
import Network

class NetworkStreamer {
    let listener: NWListener
    var connections: [NWConnection] = []
    
    // Advertise via Bonjour
    func startAdvertising() {
        let params = NWParameters.udp
        listener = try! NWListener(using: params, on: 9876)
        listener.service = NWListener.Service(
            name: "AAADepthSensor",
            type: "_aaa-depth._udp"
        )
        listener.start(queue: .main)
    }
    
    func sendFrame(depth: Data, rgb: Data, timestamp: Double) {
        // Frame format: [header][depth][rgb][metadata]
        let packet = encodeFrame(depth: depth, rgb: rgb, timestamp: timestamp)
        for connection in connections {
            connection.send(content: packet, completion: .idempotent)
        }
    }
}
```

### Phase 2: Python Client

**File:** `packages/core/src/aaa_core/hardware/ipad_depth_client.py`

```python
"""
iPad LiDAR Depth Client
Receives depth + RGB frames from iPad companion app
"""

import socket
import struct
import threading
from typing import Optional, Tuple
from zeroconf import ServiceBrowser, Zeroconf
import numpy as np


class iPadDepthClient:
    """
    Client for receiving depth data from iPad LiDAR
    
    Same interface as RealsenseCamera for drop-in replacement
    """
    
    DEPTH_WIDTH = 256
    DEPTH_HEIGHT = 192
    RGB_WIDTH = 1280
    RGB_HEIGHT = 720
    
    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.latest_frame = None
        self._lock = threading.Lock()
        
        # Discover iPad via Bonjour
        self._discover_ipad()
    
    def _discover_ipad(self):
        """Find iPad depth streamer on local network"""
        zeroconf = Zeroconf()
        browser = ServiceBrowser(
            zeroconf, 
            "_aaa-depth._udp.local.",
            handlers=[self._on_service_found]
        )
    
    def _on_service_found(self, zeroconf, service_type, name, state_change):
        """Handle discovered iPad service"""
        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._connect(info.addresses[0], info.port)
    
    def _connect(self, address: str, port: int):
        """Connect to iPad streamer"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', port))
        self.connected = True
        
        # Start receive thread
        self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._recv_thread.start()
    
    def _receive_loop(self):
        """Receive frames from iPad"""
        while self.connected:
            try:
                data, addr = self.socket.recvfrom(65535)
                frame = self._decode_frame(data)
                with self._lock:
                    self.latest_frame = frame
            except Exception as e:
                print(f"[iPadDepth] Receive error: {e}")
    
    def _decode_frame(self, data: bytes) -> dict:
        """Decode received frame packet"""
        # Header: depth_size (4) + rgb_size (4) + timestamp (8)
        header_size = 16
        depth_size, rgb_size, timestamp = struct.unpack('<IId', data[:header_size])
        
        offset = header_size
        depth_data = data[offset:offset + depth_size]
        offset += depth_size
        rgb_data = data[offset:offset + rgb_size]
        
        # Reconstruct arrays
        depth = np.frombuffer(depth_data, dtype=np.float32).reshape(
            self.DEPTH_HEIGHT, self.DEPTH_WIDTH
        )
        rgb = np.frombuffer(rgb_data, dtype=np.uint8).reshape(
            self.RGB_HEIGHT, self.RGB_WIDTH, 3
        )
        
        # Convert depth from meters to millimeters (match RealSense format)
        depth_mm = (depth * 1000).astype(np.uint16)
        
        return {
            'depth': depth_mm,
            'rgb': rgb,
            'timestamp': timestamp
        }
    
    def get_frame_stream(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get latest frame (same interface as RealsenseCamera)
        
        Returns:
            Tuple of (success, rgb_frame, depth_frame)
        """
        with self._lock:
            if self.latest_frame is None:
                return False, None, None
            
            return (
                True,
                self.latest_frame['rgb'],
                self.latest_frame['depth']
            )
    
    def disconnect(self):
        """Disconnect from iPad"""
        self.connected = False
        if self.socket:
            self.socket.close()
```

### Phase 3: Integration with Main App

**Modify `image_processor.py`:**

```python
def _initialize_camera(self):
    # Try RealSense first
    if self._try_realsense():
        return
    
    # Try iPad LiDAR as backup
    if self._try_ipad_depth():
        return
    
    # Fall back to webcam (no depth)
    self._use_webcam()

def _try_ipad_depth(self) -> bool:
    """Try to connect to iPad depth sensor"""
    try:
        from aaa_core.hardware.ipad_depth_client import iPadDepthClient
        
        client = iPadDepthClient()
        if client.connected:
            self.ipad_client = client
            self.use_ipad_depth = True
            success("Connected to iPad LiDAR")
            return True
    except Exception as e:
        status(f"iPad depth not available: {e}")
    return False
```

## Streaming Protocol

### Frame Format

```
┌────────────────────────────────────────────────────────┐
│ Header (16 bytes)                                      │
│ ├─ depth_size: uint32 (4 bytes)                        │
│ ├─ rgb_size: uint32 (4 bytes)                          │
│ └─ timestamp: float64 (8 bytes)                        │
├────────────────────────────────────────────────────────┤
│ Depth Data (variable, ~200KB uncompressed)             │
│ └─ 256x192 float32 (meters)                            │
├────────────────────────────────────────────────────────┤
│ RGB Data (variable, ~100KB JPEG compressed)            │
│ └─ 1280x720 JPEG                                       │
└────────────────────────────────────────────────────────┘
```

### Bandwidth Requirements

| Component | Size | At 30fps |
|-----------|------|----------|
| Depth (uncompressed) | 196 KB | 5.9 MB/s |
| Depth (compressed) | ~50 KB | 1.5 MB/s |
| RGB (JPEG Q85) | ~100 KB | 3.0 MB/s |
| **Total** | ~150 KB | **4.5 MB/s** |

WiFi 5/6 easily handles this with room to spare.

## UI Integration

### Camera Dropdown Addition

```python
# In main_window.py _build_ui()

# Check for iPad depth availability
ipad_available = self._check_ipad_available()

if ipad_available:
    camera_options.append(
        ft.dropdown.Option(
            key="ipad",
            text="iPad Pro LiDAR (via WiFi - with depth)",
        )
    )
```

### Status Display

```
RealSense: ✗ Not detected | iPad: ✓ Connected (WiFi) | Detection: RF-DETR
```

## Mounting Considerations

The iPad needs to be positioned to view the workspace:

```
        ┌─────────────┐
        │   iPad Pro  │  ← On adjustable stand/mount
        │   (LiDAR)   │     pointing at workspace
        └──────┬──────┘
               │
               ▼
    ┌─────────────────────┐
    │     Workspace       │
    │   (objects to pick) │
    └─────────────────────┘
```

**Mounting Options:**
- Tablet floor stand with adjustable arm
- Desk clamp mount
- 3D printed bracket for specific setup
- Standard tripod with tablet adapter

## Latency Considerations

| Source | Latency |
|--------|---------|
| ARKit capture | ~8ms |
| Encoding | ~5ms |
| WiFi transmission | 5-20ms |
| Decoding | ~3ms |
| **Total** | **21-36ms** |

For comparison, RealSense USB is <10ms total.

**Mitigation:**
- Use WiFi 6 for lower latency
- USB tethering reduces to ~15ms total
- Predictive algorithms can compensate

## Development Effort Estimate

| Task | Effort |
|------|--------|
| iOS companion app (ARKit + networking) | 2-3 days |
| Python client class | 1 day |
| Bonjour/mDNS discovery | 0.5 days |
| Integration with existing pipeline | 1 day |
| Testing and refinement | 2 days |
| **Total** | **6-8 days** |

## Future Enhancements

1. **iPad as Remote Display**
   - Show camera feed on iPad
   - Touch to select objects
   - Control arm from iPad

2. **Dual Camera Mode**
   - Use iPad for wide view
   - Use RealSense for close-up precision

3. **AR Overlay**
   - Show arm trajectory in AR
   - Visualize detected objects
   - Safety zone warnings

## Conclusion

iPad Pro LiDAR is a viable backup depth sensor that:
- Provides sufficient accuracy for pick-and-place
- Requires moderate development effort
- Could enhance accessibility with touchscreen control
- Works around macOS RealSense permission issues

The main tradeoffs are lower depth resolution (256x192 vs 1280x720) and added WiFi latency (20-40ms vs <10ms). For most use cases, these are acceptable.
