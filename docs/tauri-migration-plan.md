# Tauri + React Migration Plan

**Goal**: Migrate from Flet (2.2 GB) to Tauri + React (~100-150 MB)  
**Timeline**: 1-2 weeks  
**Expected Size Reduction**: 95% (2.2 GB → 100-150 MB)

---

## Phase 1: Setup & Architecture (Day 1-2)

### 1.1 Install Prerequisites

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install Node.js (if not already installed)
brew install node

# Verify installations
rustc --version
node --version
npm --version
```

### 1.2 Create Tauri Project

```bash
cd /Users/ck432/Dropbox/brh/Access\ Ability\ Arm/code/
npm create tauri-app@latest

# Prompts:
# - Project name: access-ability-arm-tauri
# - Choose package manager: npm
# - Choose UI template: React
# - Choose variant: TypeScript

cd access-ability-arm-tauri
```

### 1.3 Project Structure

```
access-ability-arm-tauri/
├── src-tauri/                  # Rust backend
│   ├── src/
│   │   └── main.rs            # Tauri entry point
│   ├── tauri.conf.json        # App configuration
│   ├── Cargo.toml             # Rust dependencies
│   └── icons/                 # App icons
├── src/                        # React frontend
│   ├── App.tsx                # Main React component
│   ├── components/
│   │   ├── CameraFeed.tsx     # Video stream display
│   │   ├── Controls.tsx       # Robot arm controls
│   │   ├── Settings.tsx       # Camera/mode settings
│   │   └── StatusBar.tsx      # Status indicators
│   ├── hooks/
│   │   └── usePythonBackend.ts # Python IPC hook
│   ├── styles/
│   │   └── App.css
│   └── main.tsx               # React entry point
├── python-backend/             # Python sidecar
│   ├── main.py                # FastAPI server
│   ├── config/
│   ├── vision/                # Copy from current project
│   ├── hardware/              # Copy from current project
│   ├── workers/
│   └── requirements.txt
├── package.json
└── README.md
```

### 1.4 Copy Python Backend

```bash
# From within access-ability-arm-tauri/
mkdir python-backend

# Copy modules from current project
cp -r ../access-ability-arm/config python-backend/
cp -r ../access-ability-arm/vision python-backend/
cp -r ../access-ability-arm/hardware python-backend/
cp -r ../access-ability-arm/workers python-backend/
cp ../access-ability-arm/requirements.txt python-backend/

# We'll create new main.py as FastAPI server
```

---

## Phase 2: Python Backend as Sidecar (Day 2-3)

### 2.1 Create FastAPI Server

**File**: `python-backend/main.py`

```python
#!/usr/bin/env python3
"""
Python backend server for Access Ability Arm
Runs as a sidecar process, exposing HTTP/WebSocket APIs
"""

import asyncio
import base64
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from config.settings import AppConfig, detect_hardware_capabilities
from hardware.camera_manager import CameraManager
from hardware.realsense_camera import RealsenseCamera
from vision.detection_manager import DetectionManager
from workers.image_processor import ImageProcessor

app = FastAPI(title="Access Ability Arm Backend")

# CORS for Tauri frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
config = None
camera_manager = None
detection_manager = None
image_processor = None
current_camera = None


@app.on_event("startup")
async def startup():
    """Initialize hardware and detection on startup"""
    global config, camera_manager, detection_manager
    
    # Detect capabilities
    capabilities = detect_hardware_capabilities()
    config = AppConfig(
        has_realsense=capabilities['has_realsense'],
        has_yolo=capabilities['has_yolo'],
        has_mask_rcnn=capabilities['has_mask_rcnn'],
        enable_face_detection=True,
        enable_object_detection=capabilities['has_yolo'] or capabilities['has_mask_rcnn']
    )
    
    # Initialize camera manager
    camera_manager = CameraManager()
    
    # Initialize detection
    detection_manager = DetectionManager(config)


@app.get("/api/cameras")
async def list_cameras():
    """Get list of available cameras"""
    cameras = camera_manager.get_available_cameras()
    return {"cameras": cameras}


@app.post("/api/camera/switch/{camera_id}")
async def switch_camera(camera_id: int):
    """Switch to a different camera"""
    global current_camera, image_processor
    
    # Stop current processor
    if image_processor:
        image_processor.stop()
    
    # Initialize new camera
    if config.has_realsense and camera_id == 0:
        current_camera = RealsenseCamera()
        current_camera.start()
    else:
        current_camera = cv2.VideoCapture(camera_id)
    
    # Start image processor
    image_processor = ImageProcessor(current_camera, detection_manager, config)
    image_processor.start()
    
    return {"status": "ok", "camera_id": camera_id}


@app.post("/api/mode/toggle")
async def toggle_detection_mode():
    """Toggle between face tracking and object detection"""
    if detection_manager:
        detection_manager.toggle_mode()
        mode = "face" if detection_manager.current_mode == "face" else "object"
        return {"status": "ok", "mode": mode}
    return {"status": "error", "message": "Detection manager not initialized"}


@app.get("/api/mode")
async def get_current_mode():
    """Get current detection mode"""
    if detection_manager:
        mode = "face" if detection_manager.current_mode == "face" else "object"
        return {"mode": mode}
    return {"mode": "unknown"}


@app.websocket("/ws/camera")
async def camera_websocket(websocket: WebSocket):
    """WebSocket endpoint for camera feed"""
    await websocket.accept()
    
    try:
        while True:
            if image_processor and image_processor.latest_frame is not None:
                # Get latest processed frame
                frame = image_processor.latest_frame
                
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                # Send as base64
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                await websocket.send_json({
                    "type": "frame",
                    "data": frame_base64
                })
            
            # 30 FPS
            await asyncio.sleep(1/30)
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


@app.post("/api/arm/move/{axis}/{direction}")
async def move_arm(axis: str, direction: str):
    """Move robotic arm"""
    # TODO: Implement actual arm control
    print(f"Move arm: {axis} {direction}")
    return {"status": "ok", "axis": axis, "direction": direction}


@app.post("/api/arm/grip/{state}")
async def control_grip(state: str):
    """Control gripper (open/close)"""
    # TODO: Implement actual gripper control
    print(f"Gripper: {state}")
    return {"status": "ok", "state": state}


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    if image_processor:
        image_processor.stop()
    if current_camera:
        if hasattr(current_camera, 'stop'):
            current_camera.stop()
        else:
            current_camera.release()


if __name__ == "__main__":
    # Run server on localhost:8765
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
```

### 2.2 Update Requirements

**File**: `python-backend/requirements.txt`

```txt
# Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
websockets>=12.0

# Computer Vision (keep existing)
opencv-python-headless>=4.8.0
mediapipe>=0.10.0

# Object Detection & Segmentation
ultralytics>=8.3.0

# Numerical Computing
numpy>=1.24.0

# Optional: RealSense
# pyrealsense2>=2.54.0
```

### 2.3 Update Image Processor

**File**: `python-backend/workers/image_processor.py`

Add this property to store the latest frame:

```python
class ImageProcessor(QThread):  # Or regular Thread
    def __init__(self, camera, detection_manager, config):
        super().__init__()
        self.camera = camera
        self.detection_manager = detection_manager
        self.config = config
        self.latest_frame = None  # Add this
        self.running = True
    
    def run(self):
        while self.running:
            # ... existing processing ...
            
            # Store latest frame for WebSocket
            self.latest_frame = processed_frame
    
    def stop(self):
        self.running = False
        self.wait()  # Wait for thread to finish
```

### 2.4 Build Python Sidecar

```bash
cd python-backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install PyInstaller
pip install pyinstaller

# Build standalone executable
pyinstaller --onefile \
    --name python-backend \
    --add-data "config:config" \
    --add-data "vision:vision" \
    --add-data "hardware:hardware" \
    --add-data "workers:workers" \
    --hidden-import ultralytics \
    --hidden-import mediapipe \
    --hidden-import cv2 \
    main.py

# Binary will be in dist/python-backend
```

---

## Phase 3: React Frontend (Day 4-6)

### 3.1 Install Dependencies

```bash
cd access-ability-arm-tauri

npm install
npm install @tauri-apps/api
npm install lucide-react  # Icons
```

### 3.2 Main App Component

**File**: `src/App.tsx`

```typescript
import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import CameraFeed from './components/CameraFeed'
import Controls from './components/Controls'
import Settings from './components/Settings'
import StatusBar from './components/StatusBar'
import './App.css'

function App() {
  const [mode, setMode] = useState<'face' | 'object'>('face')
  const [cameras, setCameras] = useState<string[]>([])
  const [currentCamera, setCurrentCamera] = useState(0)
  const [backendRunning, setBackendRunning] = useState(false)

  useEffect(() => {
    // Start Python backend on mount
    startBackend()
    
    // Fetch available cameras
    fetchCameras()
    
    // Keyboard shortcuts
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 't' || e.key === 'T') {
        toggleMode()
      }
    }
    window.addEventListener('keydown', handleKeyPress)
    
    return () => {
      window.removeEventListener('keydown', handleKeyPress)
      stopBackend()
    }
  }, [])

  const startBackend = async () => {
    try {
      await invoke('start_python_backend')
      setBackendRunning(true)
      console.log('Python backend started')
    } catch (error) {
      console.error('Failed to start backend:', error)
    }
  }

  const stopBackend = async () => {
    try {
      await invoke('stop_python_backend')
      setBackendRunning(false)
    } catch (error) {
      console.error('Failed to stop backend:', error)
    }
  }

  const fetchCameras = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8765/api/cameras')
      const data = await response.json()
      setCameras(data.cameras)
    } catch (error) {
      console.error('Failed to fetch cameras:', error)
    }
  }

  const toggleMode = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8765/api/mode/toggle', {
        method: 'POST'
      })
      const data = await response.json()
      setMode(data.mode)
    } catch (error) {
      console.error('Failed to toggle mode:', error)
    }
  }

  const switchCamera = async (cameraId: number) => {
    try {
      await fetch(`http://127.0.0.1:8765/api/camera/switch/${cameraId}`, {
        method: 'POST'
      })
      setCurrentCamera(cameraId)
    } catch (error) {
      console.error('Failed to switch camera:', error)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Access Ability Arm</h1>
        <StatusBar mode={mode} backendRunning={backendRunning} />
      </header>

      <main>
        <CameraFeed />
        
        <div className="sidebar">
          <Settings
            cameras={cameras}
            currentCamera={currentCamera}
            onCameraChange={switchCamera}
            mode={mode}
            onToggleMode={toggleMode}
          />
          
          <Controls />
        </div>
      </main>
    </div>
  )
}

export default App
```

### 3.3 Camera Feed Component

**File**: `src/components/CameraFeed.tsx`

```typescript
import { useEffect, useRef, useState } from 'react'

export default function CameraFeed() {
  const [connected, setConnected] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket('ws://127.0.0.1:8765/ws/camera')
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'frame' && canvasRef.current) {
        // Decode base64 image
        const img = new Image()
        img.onload = () => {
          const canvas = canvasRef.current
          if (canvas) {
            const ctx = canvas.getContext('2d')
            if (ctx) {
              canvas.width = img.width
              canvas.height = img.height
              ctx.drawImage(img, 0, 0)
            }
          }
        }
        img.src = `data:image/jpeg;base64,${data.data}`
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    ws.onclose = () => {
      console.log('WebSocket closed')
      setConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [])

  return (
    <div className="camera-feed">
      <canvas ref={canvasRef} />
      {!connected && (
        <div className="loading">Connecting to camera...</div>
      )}
    </div>
  )
}
```

### 3.4 Controls Component

**File**: `src/components/Controls.tsx`

```typescript
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Hand } from 'lucide-react'

export default function Controls() {
  const moveArm = async (axis: string, direction: string) => {
    try {
      await fetch(`http://127.0.0.1:8765/api/arm/move/${axis}/${direction}`, {
        method: 'POST'
      })
    } catch (error) {
      console.error('Failed to move arm:', error)
    }
  }

  const controlGrip = async (state: string) => {
    try {
      await fetch(`http://127.0.0.1:8765/api/arm/grip/${state}`, {
        method: 'POST'
      })
    } catch (error) {
      console.error('Failed to control grip:', error)
    }
  }

  return (
    <div className="controls">
      <h3>Robotic Arm Controls</h3>
      
      <div className="control-group">
        <label>X Axis</label>
        <div className="button-group">
          <button onClick={() => moveArm('x', 'pos')}>
            <ArrowRight size={20} /> X+
          </button>
          <button onClick={() => moveArm('x', 'neg')}>
            <ArrowLeft size={20} /> X-
          </button>
        </div>
      </div>

      <div className="control-group">
        <label>Y Axis</label>
        <div className="button-group">
          <button onClick={() => moveArm('y', 'pos')}>
            <ArrowUp size={20} /> Y+
          </button>
          <button onClick={() => moveArm('y', 'neg')}>
            <ArrowDown size={20} /> Y-
          </button>
        </div>
      </div>

      <div className="control-group">
        <label>Z Axis</label>
        <div className="button-group">
          <button onClick={() => moveArm('z', 'pos')}>
            <ArrowUp size={20} /> Z+
          </button>
          <button onClick={() => moveArm('z', 'neg')}>
            <ArrowDown size={20} /> Z-
          </button>
        </div>
      </div>

      <div className="control-group">
        <label>Gripper</label>
        <div className="button-group">
          <button onClick={() => controlGrip('open')}>
            <Hand size={20} /> Open
          </button>
          <button onClick={() => controlGrip('close')}>
            <Hand size={20} /> Close
          </button>
        </div>
      </div>
    </div>
  )
}
```

### 3.5 Settings Component

**File**: `src/components/Settings.tsx`

```typescript
interface SettingsProps {
  cameras: string[]
  currentCamera: number
  onCameraChange: (id: number) => void
  mode: 'face' | 'object'
  onToggleMode: () => void
}

export default function Settings({
  cameras,
  currentCamera,
  onCameraChange,
  mode,
  onToggleMode
}: SettingsProps) {
  return (
    <div className="settings">
      <h3>Settings</h3>
      
      <div className="setting-group">
        <label>Camera</label>
        <select 
          value={currentCamera}
          onChange={(e) => onCameraChange(parseInt(e.target.value))}
        >
          {cameras.map((camera, index) => (
            <option key={index} value={index}>
              {camera}
            </option>
          ))}
        </select>
      </div>

      <div className="setting-group">
        <label>Detection Mode</label>
        <button className="mode-toggle" onClick={onToggleMode}>
          {mode === 'face' ? '👤 Face Tracking' : '📦 Object Detection'}
        </button>
        <small>Press 'T' to toggle</small>
      </div>
    </div>
  )
}
```

### 3.6 Status Bar Component

**File**: `src/components/StatusBar.tsx`

```typescript
interface StatusBarProps {
  mode: 'face' | 'object'
  backendRunning: boolean
}

export default function StatusBar({ mode, backendRunning }: StatusBarProps) {
  return (
    <div className="status-bar">
      <span className={`status ${backendRunning ? 'connected' : 'disconnected'}`}>
        {backendRunning ? '🟢 Backend Running' : '🔴 Backend Stopped'}
      </span>
      <span className="mode">
        Mode: {mode === 'face' ? 'Face Tracking' : 'Object Detection'}
      </span>
    </div>
  )
}
```

### 3.7 Styling

**File**: `src/App.css`

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, sans-serif;
  background: #1a1a1a;
  color: #ffffff;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: #2a2a2a;
  border-bottom: 1px solid #3a3a3a;
}

header h1 {
  font-size: 1.5rem;
  font-weight: 600;
}

main {
  display: flex;
  flex: 1;
  gap: 1rem;
  padding: 1rem;
  overflow: hidden;
}

.camera-feed {
  flex: 1;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-feed canvas {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.camera-feed .loading {
  position: absolute;
  color: #888;
  font-size: 1.2rem;
}

.sidebar {
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings, .controls {
  background: #2a2a2a;
  border-radius: 8px;
  padding: 1.5rem;
}

.settings h3, .controls h3 {
  margin-bottom: 1rem;
  font-size: 1.1rem;
  color: #fff;
}

.setting-group, .control-group {
  margin-bottom: 1rem;
}

.setting-group label, .control-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  color: #aaa;
}

select {
  width: 100%;
  padding: 0.5rem;
  background: #1a1a1a;
  color: #fff;
  border: 1px solid #3a3a3a;
  border-radius: 4px;
  font-size: 0.9rem;
}

.mode-toggle {
  width: 100%;
  padding: 0.75rem;
  background: #0066ff;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.2s;
}

.mode-toggle:hover {
  background: #0052cc;
}

.button-group {
  display: flex;
  gap: 0.5rem;
}

.button-group button {
  flex: 1;
  padding: 0.75rem;
  background: #3a3a3a;
  color: #fff;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  transition: background 0.2s;
}

.button-group button:hover {
  background: #4a4a4a;
}

.button-group button:active {
  background: #2a2a2a;
}

.status-bar {
  display: flex;
  gap: 1rem;
  font-size: 0.9rem;
}

.status {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  background: #2a2a2a;
}

.status.connected {
  color: #00ff00;
}

.status.disconnected {
  color: #ff0000;
}

small {
  display: block;
  margin-top: 0.25rem;
  color: #666;
  font-size: 0.8rem;
}
```

---

## Phase 4: Tauri Backend Integration (Day 7-8)

### 4.1 Configure Tauri

**File**: `src-tauri/tauri.conf.json`

```json
{
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  },
  "package": {
    "productName": "Access Ability Arm",
    "version": "1.0.0"
  },
  "tauri": {
    "allowlist": {
      "all": false,
      "shell": {
        "all": false,
        "execute": true,
        "sidecar": true,
        "open": false
      },
      "http": {
        "all": true,
        "request": true,
        "scope": ["http://127.0.0.1:8765/**"]
      }
    },
    "bundle": {
      "active": true,
      "identifier": "com.accessability.arm",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "resources": [],
      "externalBin": [
        "binaries/python-backend"
      ],
      "copyright": "",
      "category": "Utility",
      "shortDescription": "Assistive robotic arm control application",
      "longDescription": "Computer vision-powered control for assistive robotic arm with YOLO object detection and MediaPipe face tracking",
      "macOS": {
        "entitlements": null,
        "exceptionDomain": "",
        "frameworks": [],
        "providerShortName": null,
        "signingIdentity": null
      },
      "windows": {
        "certificateThumbprint": null,
        "digestAlgorithm": "sha256",
        "timestampUrl": ""
      }
    },
    "security": {
      "csp": null
    },
    "windows": [
      {
        "title": "Access Ability Arm",
        "width": 1280,
        "height": 800,
        "resizable": true,
        "fullscreen": false
      }
    ]
  }
}
```

### 4.2 Rust Backend

**File**: `src-tauri/src/main.rs`

```rust
// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

// Global state for Python backend process
struct PythonBackend {
    process: Mutex<Option<Child>>,
}

#[tauri::command]
fn start_python_backend(state: tauri::State<PythonBackend>) -> Result<String, String> {
    let mut process_lock = state.process.lock().unwrap();
    
    // Don't start if already running
    if process_lock.is_some() {
        return Ok("Backend already running".to_string());
    }
    
    // Get the sidecar command
    let (mut cmd, cmd_name) = if cfg!(target_os = "macos") {
        let sidecar = tauri::api::process::Command::new_sidecar("python-backend")
            .expect("Failed to create python-backend sidecar");
        (sidecar, "python-backend")
    } else {
        // For development, use direct python command
        let mut cmd = Command::new("python3");
        cmd.arg("../python-backend/main.py");
        (cmd, "python3")
    };
    
    // Spawn the process
    match cmd.spawn() {
        Ok(child) => {
            *process_lock = Some(child);
            Ok(format!("Python backend started: {}", cmd_name))
        }
        Err(e) => Err(format!("Failed to start Python backend: {}", e)),
    }
}

#[tauri::command]
fn stop_python_backend(state: tauri::State<PythonBackend>) -> Result<String, String> {
    let mut process_lock = state.process.lock().unwrap();
    
    if let Some(mut child) = process_lock.take() {
        match child.kill() {
            Ok(_) => Ok("Python backend stopped".to_string()),
            Err(e) => Err(format!("Failed to stop backend: {}", e)),
        }
    } else {
        Ok("Backend not running".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .manage(PythonBackend {
            process: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            start_python_backend,
            stop_python_backend
        ])
        .setup(|app| {
            // Auto-start Python backend
            let backend_state = app.state::<PythonBackend>();
            match start_python_backend(backend_state) {
                Ok(msg) => println!("{}", msg),
                Err(e) => eprintln!("Failed to auto-start backend: {}", e),
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### 4.3 Copy Python Backend Binary

```bash
# Build Python backend (if not already done)
cd python-backend
pyinstaller --onefile --name python-backend main.py

# Copy to Tauri binaries folder
mkdir -p ../src-tauri/binaries
cp dist/python-backend ../src-tauri/binaries/python-backend-x86_64-apple-darwin

# For universal binary (M1 + Intel)
# You'll need to build on both architectures and combine with lipo
```

---

## Phase 5: Testing & Debugging (Day 9-10)

### 5.1 Development Mode

```bash
# Terminal 1: Run Python backend directly
cd python-backend
source venv/bin/activate
python main.py

# Terminal 2: Run Tauri dev mode
cd ../access-ability-arm-tauri
npm run tauri dev
```

### 5.2 Test Checklist

- [ ] Python backend starts automatically
- [ ] Camera feed displays in React UI
- [ ] Camera switching works
- [ ] Face tracking mode works
- [ ] Object detection mode works
- [ ] Mode toggle works (T key)
- [ ] Arm controls send commands
- [ ] WebSocket reconnects on disconnect
- [ ] App closes cleanly (stops Python backend)
- [ ] No console errors

### 5.3 Debug Tips

**Python backend not starting**:
```bash
# Check if port 8765 is already in use
lsof -i :8765

# Run backend manually and check logs
cd python-backend
python main.py
```

**WebSocket connection failed**:
- Check CORS settings in Python backend
- Verify port 8765 in both frontend and backend
- Check browser console for errors

**Camera feed not showing**:
- Check Python backend logs
- Verify camera permissions (macOS Privacy settings)
- Test WebSocket connection in browser dev tools

---

## Phase 6: Build & Package (Day 11-12)

### 6.1 Production Build

```bash
cd access-ability-arm-tauri

# Build for production
npm run tauri build

# Output will be in:
# src-tauri/target/release/bundle/macos/Access Ability Arm.app
```

### 6.2 Measure Bundle Size

```bash
du -sh "src-tauri/target/release/bundle/macos/Access Ability Arm.app"

# Should be around 100-150 MB!
```

### 6.3 Test Production Build

```bash
# Open the app
open "src-tauri/target/release/bundle/macos/Access Ability Arm.app"

# Test all functionality
# Check console for errors (Console.app)
```

---

## Phase 7: Optimization (Day 13-14)

### 7.1 Further Size Reduction

If size is still too large, consider:

1. **Switch to ONNX Runtime**
   - Replace PyTorch (340 MB) with ONNX Runtime (17 MB)
   - See [docs/size-optimization.md](size-optimization.md)
   - Expected savings: ~320 MB

2. **Remove unused Python packages**
   - Manually delete jaxlib, polars from PyInstaller build
   - Expected savings: ~450 MB

3. **Optimize Python binary**
   ```bash
   pyinstaller --onefile \
       --strip \
       --exclude-module jax \
       --exclude-module jaxlib \
       --exclude-module polars \
       main.py
   ```

### 7.2 Performance Optimization

1. **WebSocket compression**
   ```python
   # In Python backend
   @app.websocket("/ws/camera")
   async def camera_websocket(websocket: WebSocket):
       await websocket.accept()
       
       # Lower JPEG quality for better performance
       _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
   ```

2. **React optimization**
   - Use React.memo for components
   - Debounce control button clicks
   - Lazy load Settings component

---

## Timeline Summary

| Phase | Days | Tasks |
|-------|------|-------|
| **1. Setup** | 1-2 | Install tools, create project, copy Python code |
| **2. Python Backend** | 2-3 | FastAPI server, WebSocket, build sidecar |
| **3. React Frontend** | 4-6 | Components, styling, WebSocket client |
| **4. Tauri Integration** | 7-8 | Rust backend, sidecar config, IPC |
| **5. Testing** | 9-10 | Debug, test all features, fix bugs |
| **6. Build & Package** | 11-12 | Production build, measure size |
| **7. Optimization** | 13-14 | ONNX migration, size reduction |

**Total**: 10-14 days

---

## Success Criteria

- ✅ Bundle size < 200 MB (goal: 100-150 MB)
- ✅ All features working (camera, detection, controls)
- ✅ Fast startup (< 2 seconds)
- ✅ Smooth camera feed (30 FPS)
- ✅ Clean shutdown (no zombie processes)
- ✅ No console errors

---

## Rollback Plan

If migration fails or takes too long:

1. Keep Flet version as `main.py`
2. Tauri version in separate directory
3. Can switch between versions easily
4. Python backend is reusable (same code!)

---

## Next Steps

1. Review this plan
2. Decide on timeline
3. Start Phase 1: Setup
4. Track progress in GitHub issues or todo list

Ready to start? 🚀
