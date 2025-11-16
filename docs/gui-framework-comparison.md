# GUI Framework Comparison for Size Optimization

This document compares alternative GUI frameworks to reduce the Access Ability Arm app bundle size from the current 2.2 GB.

## Current State: Flet (Flutter-based)

**Bundle Size**: 2.2 GB
- Flet/Flutter framework: **761 MB** (App.framework)
- Flutter macOS framework: **27 MB**
- Python packages: **1.4 GB**

**Pros**:
- ✅ Cross-platform (macOS, Windows, Linux, web)
- ✅ Modern, reactive UI
- ✅ Pure Python code (no frontend/backend split)
- ✅ Hot reload for development

**Cons**:
- ❌ Large bundle size (bundles Flutter engine)
- ❌ Heavy framework for desktop apps
- ❌ **Startup loading screen issue**: `FLET_APP_HIDDEN` feature is broken since v0.16.0 ([#2705](https://github.com/flet-dev/flet/issues/2705), [#3223](https://github.com/flet-dev/flet/issues/3223)). Cannot hide window during initialization to prevent white screen on startup. Workaround (`page.window.visible = False`) causes event loop to close prematurely when loading screen tries to update.

## Alternative GUI Frameworks

### 1. **Tauri + React/Vue (RECOMMENDED)** ⭐

**Bundle Size**: 2.5-10 MB (base) + Python sidecar
- Tauri core: **2.5-3 MB**
- Python backend (PyInstaller): **50-200 MB** (depends on dependencies)
- **Total estimated**: **60-210 MB** 🎯

**Architecture**:
```
Frontend (React/Vue/Svelte)
    ↕ (IPC/Commands)
Rust Backend (Tauri)
    ↕ (Sidecar process)
Python ML Backend (PyInstaller bundle)
```

**How it works**:
1. Frontend: React/Vue for UI (uses system WebView)
2. Tauri: Rust core for app framework (tiny!)
3. Python sidecar: Bundled Python executable with ML dependencies

**Pros**:
- ✅ **Smallest possible bundle**: ~60-210 MB (73-90% reduction!)
- ✅ Uses system WebView (no Chromium bundled)
- ✅ Native performance
- ✅ Cross-platform
- ✅ Modern frontend development (React/Vue/Svelte)
- ✅ Active development & community
- ✅ Excellent documentation

**Cons**:
- ❌ Requires learning Rust (minimal - mostly config)
- ❌ Frontend/backend split (React + Python)
- ❌ More complex architecture
- ❌ IPC overhead for Python communication

**Implementation effort**: Medium (3-5 days)

**Example Projects**:
- [Tauri + Python Server Sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar)
- [Tauri + Vue + Python](https://hamza-senhajirhazi.medium.com/how-to-write-and-package-desktop-apps-with-tauri-vue-python-ecc08e1e9f2a)

---

### 2. **PyQt6/PySide6 (Native Qt)**

**Bundle Size**: 100-300 MB
- PyQt6/PySide6: **40-60 MB**
- Python packages: **50-200 MB**
- **Total estimated**: **100-300 MB**

**Pros**:
- ✅ Native performance
- ✅ Mature, well-documented
- ✅ Pure Python
- ✅ Cross-platform
- ✅ You already have PyQt6 experience (old codebase)

**Cons**:
- ❌ Still relatively large (~100 MB minimum)
- ❌ Less modern UI than web-based frameworks
- ❌ PyQt6 licensing (GPL/Commercial)

**Implementation effort**: Low (1-2 days) - you already have PyQt code!

---

### 3. **Tkinter (Built-in Python)**

**Bundle Size**: 50-200 MB
- Tkinter: **0 MB** (included with Python)
- Python packages: **50-200 MB**
- **Total estimated**: **50-200 MB**

**Pros**:
- ✅ Included with Python (no extra framework)
- ✅ Simple, lightweight
- ✅ No licensing issues
- ✅ Cross-platform

**Cons**:
- ❌ Outdated look & feel
- ❌ Limited widgets
- ❌ Poor for modern UIs

**Implementation effort**: Low (2-3 days)

---

### 4. **Pywebview (Lightweight Electron Alternative)**

**Bundle Size**: 30-200 MB
- Pywebview: **1-2 MB**
- Python packages: **50-200 MB**
- **Total estimated**: **60-210 MB**

**Architecture**: HTML/CSS/JS frontend + Python backend (uses system WebView)

**Pros**:
- ✅ Very small (uses system WebView)
- ✅ Modern web UI capabilities
- ✅ Pure Python backend
- ✅ Simple to learn

**Cons**:
- ❌ Less mature than Tauri
- ❌ Limited native integrations
- ❌ Frontend/backend split

**Implementation effort**: Medium (3-4 days)

---

### 5. **Pure Rust GUI (egui/iced)**

**Bundle Size**: 5-20 MB (smallest possible!)
- egui/iced: **2-5 MB**
- No Python needed - rewrite in Rust
- **Total estimated**: **5-20 MB** 🏆

**Pros**:
- ✅ **Absolute smallest bundle**
- ✅ Native performance
- ✅ Single binary
- ✅ Fast startup

**Cons**:
- ❌ Complete rewrite required (Rust)
- ❌ No Python ML libraries (need ONNX/C bindings)
- ❌ Steep learning curve
- ❌ Smaller ecosystem for ML

**Implementation effort**: Very High (2-4 weeks)

---

### 6. **Dear PyGui (Immediate Mode GUI)** ⭐

**Bundle Size**: 80-250 MB
- Dear PyGui: **5-10 MB**
- Python packages: **50-200 MB**
- OpenGL/Metal dependencies: **20-40 MB**
- **Total estimated**: **80-250 MB**

**Pros**:
- ✅ **GPU-accelerated** (OpenGL/Metal/DirectX)
- ✅ **Modern, fast rendering** (60+ fps)
- ✅ Cross-platform (Windows, macOS, Linux)
- ✅ Pure Python
- ✅ **Perfect for real-time applications** (robotics, CV, games)
- ✅ Built-in: plots, node editor, image display, tables
- ✅ **Works with sudo** (uses OpenGL context, not Electron/Flutter)
- ✅ Very active development (2025)
- ✅ Simple immediate mode paradigm
- ✅ No XML/QML - all Python code

**Cons**:
- ❌ **No mobile support** (desktop only: Windows/macOS/Linux)
- ❌ Different paradigm from traditional GUI (immediate mode vs retained mode)
- ❌ Less polished for "business apps" (optimized for tools/dashboards)
- ❌ Smaller ecosystem than Qt

**Best for**:
- ✅ Computer vision applications
- ✅ Robotics control interfaces
- ✅ Real-time data visualization
- ✅ Game development tools
- ✅ Scientific/engineering applications

**Not ideal for**:
- ❌ Mobile apps
- ❌ Traditional business applications
- ❌ Web deployment

**Implementation effort**: Low-Medium (2-4 days)

**Example Code**:
```python
import dearpygui.dearpygui as dpg

dpg.create_context()

# Create window
with dpg.window(label="Access Ability Arm", width=1200, height=800):
    # Display camera feed
    with dpg.texture_registry():
        dpg.add_raw_texture(width=640, height=480, 
                           default_value=rgb_frame.flatten(),
                           tag="camera_texture", format=dpg.mvFormat_Float_rgb)
    
    dpg.add_image("camera_texture")
    
    # Control buttons
    with dpg.group(horizontal=True):
        dpg.add_button(label="X+", callback=lambda: move_arm('x', 1))
        dpg.add_button(label="X-", callback=lambda: move_arm('x', -1))
    
    # Real-time plots
    dpg.add_plot(label="Depth Data", height=200, width=-1)

dpg.create_viewport(title='Access Ability Arm', width=1280, height=720)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
```

**Website**: https://github.com/hoffstadt/DearPyGui

---

### 7. **PyObjC (macOS Native)**

**Bundle Size**: 50-150 MB (macOS only)
- PyObjC: **~1 MB** (semi-standalone)
- Python packages: **50-150 MB**
- **Total estimated**: **60-160 MB**

**Pros**:
- ✅ True native macOS UI
- ✅ Small bundle (semi-standalone mode)
- ✅ Pure Python
- ✅ Best macOS integration

**Cons**:
- ❌ macOS ONLY (no cross-platform)
- ❌ Requires learning Cocoa APIs
- ❌ More complex than other options

**Implementation effort**: Medium-High (4-6 days)

---

## Size Comparison Summary

| Framework | Bundle Size | Reduction | Cross-Platform | Mobile | Works with sudo | Effort |
|-----------|-------------|-----------|----------------|--------|----------------|--------|
| **Flet (current)** | **2.2 GB** | 0% | ✅ | ✅ | ❌ | - |
| **Dear PyGui** | **80-250 MB** | 89-96% | ✅ Desktop | ❌ | ✅ | Low-Med |
| **Tauri + React** | **60-210 MB** | 90-97% | ✅ | ❌ | ⚠️ | Medium |
| **Pywebview** | **60-210 MB** | 90-97% | ✅ | ❌ | ⚠️ | Medium |
| **PyObjC** | **60-160 MB** | 93-97% | ❌ macOS | ❌ | ✅ | Med-High |
| **Tkinter** | **50-200 MB** | 91-98% | ✅ | ❌ | ✅ | Low |
| **PyQt6** | **100-300 MB** | 86-95% | ✅ | ❌ | ✅ | Low |
| **Rust (egui)** | **5-20 MB** | 99% | ✅ | ❌ | ✅ | Very High |

**Legend**:
- ✅ = Fully supported
- ❌ = Not supported
- ⚠️ = Possible but complex (needs daemon architecture)

## Recommended Migration Path

### Option A: **Tauri + React + Python Sidecar** (BEST)

**Target Size**: 100-150 MB (93% reduction)
**Timeline**: 1-2 weeks

**Why**:
- Modern, professional UI with React
- Tiny bundle size (Tauri is 2-3 MB)
- Keep all Python ML code as-is
- Cross-platform support
- Active community & excellent docs

**Migration Steps**:

1. **Setup Tauri project** (1 day)
   ```bash
   npm create tauri-app@latest
   # Choose: React/TypeScript
   ```

2. **Bundle Python as sidecar** (1 day)
   ```bash
   # Create standalone Python executable
   pyinstaller --onefile main.py
   # Configure in tauri.conf.json
   ```

3. **Build React UI** (2-3 days)
   - Port Flet UI components to React
   - Use React components for controls, video feed

4. **IPC Communication** (1-2 days)
   - Tauri commands to communicate with Python sidecar
   - WebSocket or HTTP for camera feed

5. **Testing & Polish** (2-3 days)

**Example Tauri Config**:
```json
{
  "tauri": {
    "bundle": {
      "externalBin": [
        "python-backend"
      ]
    }
  }
}
```

**Example IPC (Rust → Python)**:
```rust
#[tauri::command]
async fn start_camera() -> Result<String, String> {
    // Launch Python sidecar
    Command::new(sidecar_command("python-backend"))
        .arg("start-camera")
        .spawn()
}
```

---

### Option B: **Return to PyQt6** (EASIER)

**Target Size**: 150-200 MB (91% reduction)
**Timeline**: 2-3 days

**Why**:
- You already have PyQt6 code (`archive/` directory)
- Pure Python (no Rust/JS)
- Can reuse most existing code

**Migration Steps**:

1. **Restore PyQt6 code** (1 day)
   - Update from `archive/main_old.py`
   - Modernize UI with Qt Designer

2. **Integrate new features** (1 day)
   - Add Flet features back into PyQt6
   - Camera switching, mode toggle

3. **Test & Package** (1 day)
   - PyInstaller for distribution
   - Test on clean macOS

---

### Option C: **Quick Win - Keep Flet + Optimize** (FASTEST)

**Target Size**: 1.3-1.6 GB (27-41% reduction)
**Timeline**: 1-2 days

**Why**:
- No code changes
- Immediate results
- Low risk

**Steps**:
1. Manual cleanup (remove jaxlib, polars)
2. Migrate YOLO to ONNX Runtime
3. See [BUILD_SIZE_ANALYSIS.md](../BUILD_SIZE_ANALYSIS.md)

---

## Detailed Tauri Implementation Guide

### Architecture

```
┌─────────────────────────────────────────────┐
│  Tauri App (2.5 MB)                         │
│  ┌──────────────────────────────────────┐   │
│  │  React Frontend                       │   │
│  │  - Camera feed display               │   │
│  │  - Control buttons (x/y/z/grip)      │   │
│  │  - Settings UI                       │   │
│  └──────────────────────────────────────┘   │
│             ↕ (IPC Commands)                │
│  ┌──────────────────────────────────────┐   │
│  │  Rust Backend                        │   │
│  │  - Window management                 │   │
│  │  - File system access                │   │
│  │  - Python sidecar launcher           │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
             ↕ (HTTP/WebSocket)
┌─────────────────────────────────────────────┐
│  Python Sidecar (100-150 MB)                │
│  - YOLO inference                           │
│  - MediaPipe face tracking                  │
│  - RealSense camera integration             │
│  - HTTP/WebSocket server                    │
└─────────────────────────────────────────────┘
```

### Project Structure

```
access-ability-arm-tauri/
├── src-tauri/           # Rust backend
│   ├── src/
│   │   └── main.rs      # Tauri app entry
│   ├── tauri.conf.json  # App config
│   └── Cargo.toml       # Rust dependencies
├── src/                 # React frontend
│   ├── App.tsx
│   ├── components/
│   │   ├── CameraFeed.tsx
│   │   ├── Controls.tsx
│   │   └── Settings.tsx
│   └── main.tsx
├── python-backend/      # Python sidecar
│   ├── main.py          # FastAPI server
│   ├── vision/          # Your existing code
│   ├── hardware/
│   └── requirements.txt
└── package.json
```

### Python Backend as HTTP Server

```python
# python-backend/main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn
import cv2

app = FastAPI()

@app.get("/camera/feed")
async def camera_feed():
    def generate():
        # Your existing camera code
        while True:
            frame = get_camera_frame()
            yield frame
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace")

@app.post("/camera/switch/{camera_id}")
async def switch_camera(camera_id: int):
    # Switch camera logic
    return {"status": "ok"}

@app.post("/mode/toggle")
async def toggle_mode():
    # Toggle detection mode
    return {"mode": "face" or "object"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
```

### React Frontend

```typescript
// src/App.tsx
import { invoke } from '@tauri-apps/api/tauri'

function App() {
  const startCamera = async () => {
    await invoke('start_python_backend')
  }

  const toggleMode = async () => {
    const response = await fetch('http://127.0.0.1:8765/mode/toggle', {
      method: 'POST'
    })
    const data = await response.json()
    console.log('Mode:', data.mode)
  }

  return (
    <div className="app">
      <img src="http://127.0.0.1:8765/camera/feed" alt="Camera Feed" />
      <button onClick={toggleMode}>Toggle Mode (T)</button>
    </div>
  )
}
```

### Rust Backend

```rust
// src-tauri/src/main.rs
use tauri::Manager;
use std::process::Command;

#[tauri::command]
fn start_python_backend() {
    Command::new("python-backend")
        .spawn()
        .expect("Failed to start Python backend");
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_python_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

## Conclusion

**For 250 MB target**: Use **Tauri + React** (estimated 100-150 MB)

**For fastest implementation**: Use **PyQt6** (estimated 150-200 MB, 2-3 days)

**For best user experience**: Use **Tauri + React** (modern UI, tiny size, 1-2 weeks)

Both Tauri and PyQt6 would achieve your size goal and are realistic options!
