# Client-Server Architecture Plan

This document outlines a client-server architecture approach for the Access Ability Arm application, which would allow a lightweight mobile app to connect to a server running the Python backend.

## Overview

Instead of bundling all Python dependencies (2.2 GB) on mobile, split the application:
- **Mobile Client**: Lightweight UI only (50-100 MB)
- **Server**: Full Python backend with CV and arm control (runs on Mac/Linux/Raspberry Pi)

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│  Mobile App (iOS/Android)               │
│  ┌───────────────────────────────────┐  │
│  │  Flutter/React Native/Flet        │  │
│  │  - Camera feed display            │  │
│  │  - Control buttons (x/y/z/grip)   │  │
│  │  - Object selection UI            │  │
│  │  - Settings                       │  │
│  └───────────────────────────────────┘  │
│         Bundle: 50-100 MB                │
└─────────────────────────────────────────┘
              ↕ (WiFi/Network)
         WebSocket/HTTP REST API
              ↕
┌─────────────────────────────────────────┐
│  Server (Mac/Linux/Raspberry Pi)        │
│  ┌───────────────────────────────────┐  │
│  │  Python Backend (FastAPI/Flask)   │  │
│  │  - YOLO inference                 │  │
│  │  - MediaPipe face tracking        │  │
│  │  - RealSense camera               │  │
│  │  - xArm control                   │  │
│  │  - Video streaming                │  │
│  └───────────────────────────────────┘  │
│         Your existing Python code!       │
└─────────────────────────────────────────┘
```

## Key Benefits

✅ **Keep all your Python code** - No rewrite needed!  
✅ **Tiny mobile app** - Just UI (50-100 MB vs 2.2 GB)  
✅ **Server does heavy lifting** - CV processing on powerful hardware  
✅ **Multiple clients** - Control from phone, tablet, web browser  
✅ **Easy updates** - Update server, all clients benefit  
✅ **Better performance** - Server has more RAM/GPU than mobile  
✅ **No mobile CV limitations** - Full OpenCV, YOLO, MediaPipe on server

## Implementation Options

### Option A: Flet Server Mode ⭐ (EASIEST)

Flet has built-in server mode. Minimal changes to existing code.

**Server (your Mac with the arm/camera):**

```python
# main.py (minimal changes to your existing code!)
import flet as ft

def main(page: ft.Page):
    # Your existing Flet code
    page.add(ft.Text("Access Ability Arm"))
    # ... rest of your UI ...

# Run as server instead of desktop app
ft.app(
    target=main,
    view=ft.AppView.FLET_APP,  # or FLET_APP_WEB
    host="0.0.0.0",  # Listen on all network interfaces
    port=8550
)
```

**Mobile/Client:**
- Navigate to `http://your-mac-ip:8550` in browser
- Or build a native Flet mobile app that connects to server
- **No code changes needed!**

**Pros:**
- ✅ Works with existing code
- ✅ Zero migration effort
- ✅ Access from any device with browser
- ✅ Mobile app is just a web wrapper (~20 MB)

**Cons:**
- ❌ Still need to package Flet server (~2 GB on server, but server can handle it)
- ❌ Web app in browser (not native mobile feel)
- ❌ Network dependency

---

### Option B: FastAPI Server + Flutter/React Native Client (BEST PERFORMANCE)

Separate the UI completely from the backend.

**Server (Python - FastAPI):**

```python
# server/main.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
import cv2
import asyncio
from contextlib import asynccontextmanager

app = FastAPI()

# Your existing Python code
from aaa_core.workers.image_processor import ImageProcessor
from aaa_core.workers.arm_controller import ArmController

# Global state
camera = None
arm_controller = None
detection_mode = "face"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global camera, arm_controller
    camera = ImageProcessor()
    arm_controller = ArmController()
    yield
    # Shutdown
    camera.stop()

app = FastAPI(lifespan=lifespan)

# Video streaming endpoint
@app.get("/video/stream")
async def video_stream():
    def generate():
        while True:
            frame = camera.get_latest_frame()
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# Detection endpoints
@app.post("/detection/mode/{mode}")
async def set_detection_mode(mode: str):
    global detection_mode
    detection_mode = mode
    camera.set_detection_mode(mode)
    return {"mode": mode}

@app.post("/detection/freeze")
async def freeze_detection():
    results = camera.freeze_frame()
    return {
        "objects": [
            {"id": i, "class": obj["class"], "center": obj["center"]}
            for i, obj in enumerate(results)
        ]
    }

@app.post("/object/select/{object_id}")
async def select_object(object_id: int):
    camera.select_object(object_id)
    return {"selected": object_id}

# Arm control endpoints
@app.post("/arm/move/{axis}/{direction}")
async def move_arm(axis: str, direction: str):
    # axis: x, y, z, grip
    # direction: pos, neg
    arm_controller.move(axis, direction)
    return {"status": "moving"}

@app.post("/arm/stop")
async def stop_arm():
    arm_controller.emergency_stop()
    return {"status": "stopped"}

@app.post("/arm/home")
async def home_arm():
    arm_controller.home()
    return {"status": "homing"}

# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send status updates
            status = {
                "mode": detection_mode,
                "arm_position": arm_controller.get_position(),
                "selected_object": camera.selected_object
            }
            await websocket.send_json(status)
            await asyncio.sleep(0.1)  # 10 Hz updates
    except:
        pass

# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
```

**Mobile Client (Flutter):**

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ArmControlApp extends StatefulWidget {
  @override
  _ArmControlAppState createState() => _ArmControlAppState();
}

class _ArmControlAppState extends State<ArmControlApp> {
  final String serverUrl = "http://192.168.1.100:8765";  // Your server IP
  String detectionMode = "face";
  List<DetectedObject> objects = [];
  int? selectedObject;
  
  // Video stream
  Widget get videoFeed => Image.network(
    "$serverUrl/video/stream",
    fit: BoxFit.contain,
  );
  
  // Toggle detection mode
  Future<void> toggleMode() async {
    final newMode = detectionMode == "face" ? "objects" : "face";
    final response = await http.post(
      Uri.parse("$serverUrl/detection/mode/$newMode"),
    );
    if (response.statusCode == 200) {
      setState(() {
        detectionMode = newMode;
      });
    }
  }
  
  // Freeze and detect objects
  Future<void> findObjects() async {
    final response = await http.post(
      Uri.parse("$serverUrl/detection/freeze"),
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      setState(() {
        objects = (data['objects'] as List)
            .map((obj) => DetectedObject.fromJson(obj))
            .toList();
      });
    }
  }
  
  // Select object
  Future<void> selectObject(int id) async {
    await http.post(
      Uri.parse("$serverUrl/object/select/$id"),
    );
    setState(() {
      selectedObject = selectedObject == id ? null : id;
    });
  }
  
  // Move arm
  Future<void> moveArm(String axis, String direction) async {
    await http.post(
      Uri.parse("$serverUrl/arm/move/$axis/$direction"),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Access Ability Arm")),
      body: Column(
        children: [
          // Video feed
          Expanded(child: videoFeed),
          
          // Auto controls
          Padding(
            padding: EdgeInsets.all(16),
            child: Column(
              children: [
                ElevatedButton(
                  onPressed: findObjects,
                  child: Text("Find Objects"),
                ),
                
                // Object selection buttons
                Wrap(
                  spacing: 8,
                  children: objects.map((obj) => ChoiceChip(
                    label: Text("#${obj.id}: ${obj.className}"),
                    selected: selectedObject == obj.id,
                    onSelected: (_) => selectObject(obj.id),
                  )).toList(),
                ),
                
                ElevatedButton(
                  onPressed: () => moveArm("x", "pos"),
                  child: Text("Execute"),
                ),
              ],
            ),
          ),
          
          // Manual controls
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              Column(
                children: [
                  IconButton(
                    icon: Icon(Icons.arrow_upward),
                    onPressed: () => moveArm("y", "pos"),
                  ),
                  IconButton(
                    icon: Icon(Icons.arrow_downward),
                    onPressed: () => moveArm("y", "neg"),
                  ),
                ],
              ),
              Column(
                children: [
                  IconButton(
                    icon: Icon(Icons.arrow_forward),
                    onPressed: () => moveArm("x", "pos"),
                  ),
                  IconButton(
                    icon: Icon(Icons.arrow_back),
                    onPressed: () => moveArm("x", "neg"),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class DetectedObject {
  final int id;
  final String className;
  final List<int> center;
  
  DetectedObject({required this.id, required this.className, required this.center});
  
  factory DetectedObject.fromJson(Map<String, dynamic> json) {
    return DetectedObject(
      id: json['id'],
      className: json['class'],
      center: List<int>.from(json['center']),
    );
  }
}
```

**Pros:**
- ✅ Tiny mobile app (~50 MB Flutter app)
- ✅ Keep all Python code on server
- ✅ Native mobile UI performance
- ✅ Can build for iOS/Android/web
- ✅ Multiple clients can connect simultaneously

**Cons:**
- ❌ Need to write mobile app (but much simpler than full Flutter migration)
- ❌ Network dependency (need WiFi)
- ❌ Server must be running

---

### Option C: Progressive Web App (PWA) (EASIEST MOBILE)

Same FastAPI server, but use a web app that can be "installed" on mobile.

**Server:** Same as Option B

**Frontend (HTML/JavaScript):**

```html
<!-- static/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Access Ability Arm</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #video { width: 100%; max-height: 60vh; object-fit: contain; }
        .controls { padding: 16px; }
        button { padding: 12px 24px; margin: 8px; font-size: 16px; }
    </style>
</head>
<body>
    <img id="video" src="/video/stream" alt="Camera feed">
    
    <div class="controls">
        <h3>Auto Controls</h3>
        <button onclick="findObjects()">🔍 Find Objects</button>
        <div id="objects"></div>
        <button onclick="execute()">▶️ Execute</button>
        <button onclick="stop()">⏹️ Stop</button>
        <button onclick="home()">🏠 Home</button>
        
        <h3>Manual Controls</h3>
        <button onclick="move('x', 'pos')">X+</button>
        <button onclick="move('x', 'neg')">X-</button>
        <button onclick="move('y', 'pos')">Y+</button>
        <button onclick="move('y', 'neg')">Y-</button>
        <button onclick="move('z', 'pos')">Z+</button>
        <button onclick="move('z', 'neg')">Z-</button>
    </div>
    
    <script>
        async function findObjects() {
            const response = await fetch('/detection/freeze', { method: 'POST' });
            const data = await response.json();
            
            const objectsDiv = document.getElementById('objects');
            objectsDiv.innerHTML = data.objects.map(obj => 
                `<button onclick="selectObject(${obj.id})">#${obj.id}: ${obj.class}</button>`
            ).join('');
        }
        
        async function selectObject(id) {
            await fetch(`/object/select/${id}`, { method: 'POST' });
        }
        
        async function move(axis, direction) {
            await fetch(`/arm/move/${axis}/${direction}`, { method: 'POST' });
        }
        
        async function stop() {
            await fetch('/arm/stop', { method: 'POST' });
        }
        
        async function home() {
            await fetch('/arm/home', { method: 'POST' });
        }
    </script>
</body>
</html>
```

**Make it a PWA (installable on mobile):**

```json
// static/manifest.json
{
  "name": "Access Ability Arm",
  "short_name": "AAA",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#FFFFFF",
  "theme_color": "#2196F3",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

**Pros:**
- ✅ No app store needed
- ✅ Works on any device with browser
- ✅ Can "install" to home screen (looks like native app)
- ✅ Easiest to develop (HTML/JS)
- ✅ Zero bundle size (just web page)

**Cons:**
- ❌ Web UI (not fully native feel)
- ❌ Limited offline capabilities
- ❌ Browser-dependent features

---

## Network Considerations

### Local Network (WiFi)
- **Latency:** 10-50ms (excellent for video streaming)
- **Bandwidth:** 5-20 Mbps (enough for 720p H.264)
- **Setup:** Server and mobile on same WiFi network
- **Best for:** Home/lab use

### Remote Access (Internet)
- **VPN:** Use Tailscale/WireGuard for secure remote access
- **Cloud Tunnel:** ngrok, Cloudflare Tunnel
- **Port Forwarding:** Open port on router (security risk)
- **Best for:** Access from anywhere

### Video Streaming Options

| Method | Latency | Quality | Complexity |
|--------|---------|---------|------------|
| **MJPEG** (Motion JPEG) | Low (50-100ms) | Medium | Easy |
| **H.264** (via WebRTC) | Very Low (20-50ms) | High | Hard |
| **HLS** (HTTP Live Streaming) | High (2-10s) | High | Medium |

**Recommendation:** Start with MJPEG (easiest), upgrade to WebRTC if latency is issue.

---

## Comparison: Client-Server vs Standalone

| Aspect | Current (Flet Standalone) | Client-Server |
|--------|---------------------------|---------------|
| **Mobile bundle** | 2.2 GB | 50-100 MB |
| **Server bundle** | N/A | 2 GB (but on Mac, no issue) |
| **Performance** | Good (native) | Good (server does CV) |
| **Mobile support** | Yes | Yes |
| **Offline use** | ✅ Works offline | ❌ Needs WiFi/network |
| **Multiple devices** | ❌ One device only | ✅ Phone, tablet, laptop |
| **Code reuse** | 100% | 80% (server) + new client |
| **Complexity** | Low | Medium |
| **Best for** | Single device | Multi-device, remote access |

---

## Recommended Implementation Plan

### Phase 1: Quick Test (1 day)
**Goal:** Validate client-server approach with minimal effort

1. Run existing Flet app in server mode:
   ```python
   ft.app(target=main, host="0.0.0.0", port=8550)
   ```
2. Access from phone browser: `http://your-mac-ip:8550`
3. Evaluate if client-server fits your workflow

**Decision Point:** If this works well, proceed to Phase 2

### Phase 2: Build Proper Backend (1-2 weeks)
**Goal:** Create clean REST API with FastAPI

1. **Setup FastAPI project structure** (2 days)
   ```
   server/
   ├── main.py              # FastAPI app
   ├── api/
   │   ├── detection.py     # Detection endpoints
   │   ├── arm.py           # Arm control endpoints
   │   └── video.py         # Video streaming
   ├── services/
   │   ├── image_processor.py
   │   └── arm_controller.py
   └── requirements.txt
   ```

2. **Implement core endpoints** (3-4 days)
   - Video streaming (`/video/stream`)
   - Detection mode toggle (`/detection/mode/{mode}`)
   - Object detection (`/detection/freeze`)
   - Object selection (`/object/select/{id}`)
   - Arm movement (`/arm/move/{axis}/{direction}`)
   - Emergency stop (`/arm/stop`)
   - Home position (`/arm/home`)

3. **Add WebSocket for real-time updates** (2 days)
   - Arm position updates
   - Detection status
   - System health

4. **Test API with Postman/curl** (1 day)

### Phase 3: Build Client (1-3 weeks depending on option)

**Option A: PWA (1 week)**
1. Create HTML/CSS/JavaScript frontend
2. Implement video display and controls
3. Add PWA manifest and service worker
4. Test on mobile devices

**Option B: Flutter App (3 weeks)**
1. Setup Flutter project
2. Implement screens (home, settings)
3. Create API service layer
4. Implement video player
5. Build control widgets
6. Test and deploy

### Phase 4: Polish & Deploy (1 week)
1. Improve video streaming (H.264/WebRTC)
2. Add authentication/security
3. Setup VPN for remote access (Tailscale recommended)
4. Error handling and reconnection logic
5. Documentation

---

## Timeline Summary

| Approach | Timeline | Effort | Bundle Size |
|----------|----------|--------|-------------|
| **Flet server mode** | 1 day | Minimal | 2.2 GB (server) + browser |
| **FastAPI + PWA** | 2-3 weeks | Low | 2 GB (server) + web page |
| **FastAPI + Flutter app** | 4-5 weeks | Medium | 2 GB (server) + 50 MB (mobile) |

---

## Security Considerations

### Authentication
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.post("/arm/move/{axis}/{direction}")
async def move_arm(
    axis: str, 
    direction: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Verify token
    if not verify_token(credentials.credentials):
        raise HTTPException(status_code=401)
    
    arm_controller.move(axis, direction)
    return {"status": "moving"}
```

### HTTPS/SSL
- Use Let's Encrypt for free SSL certificates
- Or run behind reverse proxy (nginx, Caddy)

### Network Security
- **Local only:** Firewall rules to restrict access to local network
- **Remote:** Use VPN (Tailscale/WireGuard) instead of exposing to internet
- **API keys:** Require authentication for all endpoints
- **Rate limiting:** Prevent abuse

---

## Alternative: Hybrid Local + Cloud

If you need both offline and remote capabilities:

```
┌─────────────────┐         ┌─────────────────┐
│  Mobile App     │ ←WiFi→  │  Local Server   │
│  (50 MB)        │         │  (Mac, 2 GB)    │
└─────────────────┘         └─────────────────┘
        ↕                            ↕
    Internet                    Internet
        ↕                            ↕
┌─────────────────┐         ┌─────────────────┐
│  Cloud Relay    │ ←────→  │  VPN/Tunnel     │
│  (FastAPI)      │         │  (Tailscale)    │
└─────────────────┘         └─────────────────┘
```

**Benefits:**
- Works on local WiFi (low latency)
- Falls back to cloud when remote
- Best of both worlds

---

## Next Steps

### Immediate (This Week)
1. Test Flet server mode (1 hour)
2. Evaluate if client-server fits your needs
3. Decide on implementation option

### Short-term (Next Month)
1. Build FastAPI backend
2. Create simple PWA or Flutter client
3. Test in real-world scenarios

### Long-term (3-6 Months)
1. Optimize video streaming (WebRTC)
2. Add advanced features (multiple cameras, recording)
3. Deploy to app stores (if Flutter option)

---

## Conclusion

The client-server architecture provides the best balance for your use case:
- ✅ Solves mobile bundle size (50 MB vs 2.2 GB)
- ✅ Keeps all Python code (no rewrite!)
- ✅ Enables multi-device access
- ✅ Much faster than full Flutter migration
- ✅ Low risk with quick validation (Flet server mode test)

**Recommended first step:** Run your existing Flet app in server mode today and see if the client-server model works for you. If yes, invest 2-3 weeks in building a proper FastAPI backend with a PWA or Flutter client.
