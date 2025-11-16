# Flet GUI Version

Modern cross-platform GUI implementation using [Flet](https://flet.dev) framework.

## Overview

This is an alternative GUI implementation that provides the same functionality as the PyQt6 version with a more modern, Material Design-inspired interface. Flet enables deployment to:

- Desktop (Windows, macOS, Linux)
- Web browsers
- Mobile (iOS, Android) - future support

## Features

### Same Core Functionality
- ✓ Real-time video feed from camera
- ✓ YOLOv11 object detection and segmentation
- ✓ MediaPipe face landmark tracking
- ✓ RealSense depth sensing (optional)
- ✓ Manual robotic arm controls (x, y, z, grip)
- ✓ Camera selection dropdown
- ✓ Detection mode toggle (press 'T')

### Flet-Specific Advantages
- **Modern UI**: Material Design components
- **Cross-platform**: Same code runs on desktop, web, mobile
- **Responsive**: Auto-adjusts to different screen sizes
- **Hot reload**: Faster development iteration
- **Web deployment**: Can run in browser without installation

## Running the Flet Version

### Prerequisites

Install Flet in your virtual environment:

```bash
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install flet>=0.24.0
```

### Launch Desktop App

```bash
python main_flet.py
```

### Launch as Web App

```bash
python main_flet.py --web
```

This will start a local web server and open the app in your browser.

## UI Layout

### Main Window (1200x800)

```
┌────────────────────────────────────────────────────────┐
│  🤖 DE-GUI Assistive Robotic Arm                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌───────────────────┐    ┌─────────────────┐        │
│  │                   │    │ Manual Controls │        │
│  │   Video Feed      │    │                 │        │
│  │   800x650         │    │  X: [−] ⇔ [+]  │        │
│  │                   │    │  Y: [−] ⇕ [+]  │        │
│  │                   │    │  Z: [−] ⬍ [+]  │        │
│  └───────────────────┘    │  GRIP: [−] ✋ [+]│       │
│                           │                 │        │
│  [Select Camera ▼]        │  Grip State     │        │
│  [Toggle Mode (T)]        │  [Open/Close]   │        │
│                           └─────────────────┘        │
│                                                        │
│ Status: RealSense: ✓ | Detection: YOLOV11 | Mode: OBJECTS │
└────────────────────────────────────────────────────────┘
```

## Key Differences from PyQt6 Version

| Feature | PyQt6 | Flet |
|---------|-------|------|
| **UI Framework** | Qt Designer .ui file | Python code |
| **Deployment** | Desktop only | Desktop + Web + Mobile |
| **Design** | Custom widgets | Material Design |
| **Development** | QtDesigner + code | Pure Python |
| **Updates** | Manual recompile | Hot reload |
| **Web support** | No | Yes |

## Components

### flet_gui/main_window.py

Main Flet window class:
- `FletMainWindow`: Main application window
  - `_build_ui()`: Constructs Material Design layout
  - `_build_control_panel()`: Creates robotic arm controls
  - `_update_video_feed()`: Converts QImage to base64 for display
  - `_toggle_detection_mode()`: Switches between face/object detection
  - `_on_keyboard_event()`: Handles keyboard shortcuts

### main_flet.py

Entry point for Flet version:
- Uses `ft.app(target=main)` to launch
- Supports `--web` flag for browser mode
- Handles cleanup on close

## Architecture Integration

The Flet GUI seamlessly integrates with existing modules:

```python
# Uses same backend modules as PyQt6 version
from config.settings import app_config
from hardware.button_controller import ButtonController
from hardware.camera_manager import CameraManager
from workers.image_processor import ImageProcessor
```

**No changes needed** to existing vision, hardware, or worker modules!

## Known Limitations

1. **Qt Signal Integration**: Flet uses threading for updates instead of Qt signals
2. **Button Hold Detection**: Simplified to click events (no press/hold differentiation yet)
3. **Image Format**: Requires base64 conversion for video feed (slight performance overhead)
4. **Mobile Support**: Not yet tested on iOS/Android

## Future Enhancements

- [ ] Touch controls for mobile devices
- [ ] Responsive layout for different screen sizes
- [ ] WebSocket support for remote control
- [ ] Multi-user collaboration features
- [ ] Cloud deployment (Flet hosting)
- [ ] Progressive Web App (PWA) support

## Development

### Adding New Controls

```python
# In _build_control_panel()
new_button = ft.ElevatedButton(
    text="New Action",
    icon=ft.icons.NEW_ICON,
    on_click=lambda e: self._on_new_action(),
)
```

### Styling

Flet uses Material Design theming:

```python
# Change theme
self.page.theme_mode = ft.ThemeMode.DARK  # or LIGHT

# Custom colors
button = ft.ElevatedButton(
    bgcolor=ft.colors.BLUE_500,
    color=ft.colors.WHITE,
)
```

### Hot Reload

For development with hot reload:

```bash
flet run main_flet.py
```

Changes to the UI will update automatically!

## Troubleshooting

**Flet import error:**
```bash
pip install flet>=0.24.0
```

**Video feed not updating:**
- Check that ImageProcessor is running
- Verify camera permissions
- Check console for errors

**Web version not accessible:**
```bash
# Specify port
python main_flet.py --web --port 8080
```

**Keyboard shortcuts not working:**
- Click inside the app window first
- Web version may have browser conflicts

## Documentation

- [Flet Documentation](https://flet.dev/docs/)
- [Flet Gallery](https://flet.dev/gallery/)
- [Material Design Icons](https://fonts.google.com/icons)

## License

Same as main project - see [../LICENSE.txt](../LICENSE.txt)
