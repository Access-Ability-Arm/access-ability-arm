# Windows Distribution Guide

This guide explains how to build and distribute the Access Ability Arm application for Windows users.

## Building the Windows Executable

### Prerequisites (on Windows machine)
- Python 3.11 installed
- Git (to clone the repository)
- At least 2 GB free disk space

### Build Steps

1. **Clone the repository**:
   ```cmd
   git clone https://github.com/Access-Ability-Arm/access-ability-arm.git
   cd access-ability-arm
   ```

2. **Run the build script**:
   ```cmd
   build-windows.bat
   ```

3. **Wait for the build to complete** (5-10 minutes):
   - Creates virtual environment
   - Installs all dependencies
   - Downloads AI models (~300 MB)
   - Compiles standalone executable

4. **Find the executable**:
   ```
   dist/AccessAbilityArm/
   ├── AccessAbilityArm.exe      # Main executable
   ├── data/                      # AI models
   ├── config/                    # Configuration
   └── [many .dll files]          # Dependencies
   ```

## Distributing to Colleagues

### Option 1: Zip File (Recommended)
1. Zip the entire `dist/AccessAbilityArm/` folder
2. Upload to Google Drive / Dropbox / shared network
3. Send link to colleague

**Size**: Approximately 400-600 MB (includes all dependencies and AI models)

### Option 2: Installer (Advanced)
Use NSIS or Inno Setup to create a proper installer:
```cmd
# Example with Inno Setup
iscc windows-installer.iss
```

## What Your Colleague Needs to Do

### Minimal Setup (Webcam Only)
1. Download and extract `AccessAbilityArm.zip`
2. Double-click `AccessAbilityArm.exe`
3. Allow Windows Firewall if prompted
4. The app will detect their webcam automatically

**No Python installation required!**

### Full Setup (with RealSense Camera)
If they have an Intel RealSense D435 camera:

1. Install RealSense SDK:
   - Download: https://github.com/IntelRealSense/librealsense/releases
   - Install `Intel.RealSense.SDK-WIN10-x.x.x.exe`

2. Launch with RealSense enabled:
   ```cmd
   AccessAbilityArm.exe --enable-realsense
   ```

### Full Setup (with Lite6 Arm)
If they have the UFACTORY Lite6 robotic arm:

1. Install Lite6 SDK:
   ```cmd
   pip install xarm-python-sdk
   ```

2. Configure arm IP in `config/config.yaml`:
   ```yaml
   lite6_ip: "192.168.1.xxx"  # Their arm's IP address
   ```

## Configuration

The executable includes a default `config/config.yaml`. Your colleague can edit it:

```yaml
# Camera settings
default_camera: 0
skip_cameras:
  - "virtual"  # Skip virtual cameras
  
# Window settings
window_width: 1400
window_height: 900

# Lite6 arm settings (optional)
lite6_ip: "192.168.1.202"
lite6_enabled: false  # Set to true if they have the arm
```

## Troubleshooting

### "VCRUNTIME140.dll is missing"
- Install Microsoft Visual C++ Redistributable:
  https://aka.ms/vs/17/release/vc_redist.x64.exe

### "Camera not detected"
- Check Windows camera permissions: Settings → Privacy → Camera
- Make sure webcam isn't in use by another app

### "Slow object detection"
- The app automatically uses GPU if available (NVIDIA CUDA)
- CPU fallback is slower but functional
- Consider switching to face tracking mode (press 'T')

### "App won't start"
- Run from command prompt to see error messages:
  ```cmd
  cd dist\AccessAbilityArm
  AccessAbilityArm.exe
  ```

## File Size Reduction Tips

If the 500 MB zip is too large for your distribution method:

1. **Exclude optional models**:
   - Remove `data/models/` folder (models auto-download on first run)
   - Reduces to ~200 MB

2. **Use UPX compression** (already enabled in build script):
   - Reduces .dll file sizes
   - Some antivirus may flag UPX-compressed files as suspicious

3. **Split into base + models**:
   - Distribute base app (~200 MB) separately from models (~300 MB)
   - User downloads models on first launch

## Building from macOS (Cross-compilation)

PyInstaller doesn't support cross-compilation. You need access to a Windows machine to build the Windows executable.

**Options**:
1. **Virtual Machine**: Run Windows in Parallels/VMware/VirtualBox
2. **Cloud**: Use AWS/Azure Windows instance
3. **GitHub Actions**: Automate builds in CI/CD (see `.github/workflows/build.yml`)

## Next Steps

See `docs/installation.md` for detailed development setup instructions if your colleague wants to modify the code.
