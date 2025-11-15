# Installation Guide

## Requirements

**Python Version:** This project requires **Python 3.11** (MediaPipe does not support Python 3.14+).

**Disk Space:** At least **15GB free** (Xcode ~12GB, Android Studio ~3GB, dependencies ~1GB).

## Setting Up the Virtual Environment

### 1. Install Python 3.11

- **macOS with Homebrew:**
  ```bash
  brew install python@3.11
  ```
- **Windows/Linux:** Download from [python.org](https://www.python.org/downloads/)

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
# Or on macOS with Homebrew:
/opt/homebrew/bin/python3.11 -m venv venv
```

### 3. Activate Virtual Environment

- **macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** `pyrealsense2` is commented out in `requirements.txt` as it requires manual installation from source (v2.56.5). See [Intel RealSense Installation](#optional-intel-realsense-camera-support) below.

## Model Files

### YOLOv11 (Recommended - Used by main.py)

**No setup required!** Models download automatically on first run (~6MB for nano model).

### Mask R-CNN (Legacy - Used by main-rd.py)

If you need the legacy Mask R-CNN version, download model files manually:

#### 1. Create dnn Directory

```bash
mkdir dnn && cd dnn
```

#### 2. Download Model Files

```bash
# Download model archive
wget http://download.tensorflow.org/models/object_detection/mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
tar -xvf mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
mv mask_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb frozen_inference_graph_coco.pb

# Download config file
wget https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/mask_rcnn_inception_v2_coco_2018_01_28.pbtxt

# Download COCO classes
wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O classes.txt

# Clean up
rm mask_rcnn_inception_v2_coco_2018_01_28.tar.gz
cd ..
```

#### 3. Verify Installation

```bash
ls dnn/
# Should show:
# - frozen_inference_graph_coco.pb
# - mask_rcnn_inception_v2_coco_2018_01_28.pbtxt
# - classes.txt
```

**Note:** These files are large (~200MB) and only required for legacy `main-rd.py`.

## Optional: Intel RealSense Camera Support

For depth sensing capabilities, install RealSense SDK:

### macOS/Linux

Follow the official guide: [Intel RealSense Installation](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation.md)

After installing the SDK:
```bash
pip install pyrealsense2
```

### Windows

1. Download and install [Intel RealSense SDK 2.0](https://github.com/IntelRealSense/librealsense/releases)
2. Install Python wrapper:
   ```bash
   pip install pyrealsense2
   ```

**Note:** The application works without RealSense using standard webcams (no depth sensing).

## Development Tools for Application Packaging

To build distributable applications for different platforms, you'll need additional tools. **Note:** These are only required if you plan to package/distribute the app, not for running it in development mode.

### Xcode (Required for macOS/iOS builds)

**Platform:** macOS only

Xcode is required to build macOS and iOS applications.

#### Installation

1. **Install Xcode from the App Store:**
   - Open the Mac App Store
   - Search for "Xcode"
   - Download and install (requires ~12GB disk space)
   - **Minimum Version:** Xcode 15 (for Apple Silicon Macs)

2. **Install Xcode Command Line Tools:**
   ```bash
   xcode-select --install
   ```

3. **Accept Xcode License:**
   ```bash
   sudo xcodebuild -license accept
   ```

4. **Configure Xcode:**
   ```bash
   sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
   ```

5. **Verify Installation:**
   ```bash
   xcodebuild -version
   ```
   Should show: `Xcode 15.x` or newer

#### Additional Setup for iOS Development

If building for iOS (iPhone/iPad):

1. **Install iOS Simulator:**
   - Open Xcode
   - Go to Xcode → Settings → Platforms
   - Download the iOS platform you want to target

2. **Setup Signing (for device deployment):**
   - You'll need an Apple Developer account ($99/year)
   - Configure signing in Xcode project settings

### Flutter SDK (Auto-installed by Flet)

**Platform:** All platforms

**Good news:** You don't need to manually install Flutter! Flet automatically downloads and manages the correct Flutter version when you first run `flet build`.

The Flutter SDK will be installed to: `$HOME/flutter/{version}`

If you want to install Flutter manually or use it for other projects, see: https://docs.flutter.dev/get-started/install

### Android Studio (Required for Android builds)

**Platform:** All platforms (for building Android apps)

Android Studio is only needed if you plan to build Android APK/AAB files.

#### Installation

1. **Download Android Studio:**
   - Visit: https://developer.android.com/studio
   - Download for your platform
   - Install (~3GB disk space)

2. **Run Android Studio Setup Wizard:**
   - Launch Android Studio
   - Follow the setup wizard to install:
     - Android SDK
     - Android SDK Platform
     - Android Virtual Device (for testing)

3. **Accept Android Licenses:**
   ```bash
   flutter doctor --android-licenses
   ```
   **Note:** This requires Flutter to be installed first (happens automatically on first `flet build`)

4. **Verify Installation:**
   ```bash
   flutter doctor
   ```
   Should show Android toolchain properly configured.

#### Android SDK Requirements

- **Minimum SDK:** API 21 (Android 5.0)
- **Target SDK:** API 33+ (Android 13+)
- **Build Tools:** Latest version

### Flutter Doctor (Verify All Requirements)

After installing Xcode and/or Android Studio, verify your setup:

```bash
# Flet will install Flutter on first build, but you can check manually:
flutter doctor -v
```

You should see:
- ✓ Flutter (automatically managed by Flet)
- ✓ Xcode - develop for iOS and macOS (if installed)
- ✓ Android toolchain - develop for Android devices (if installed)
- ✓ VS Code or Android Studio (optional)

**Note:** You don't need all platforms - only install tools for platforms you're targeting.

## macOS Application Packaging (Flet)

To build macOS application bundles, you need CocoaPods properly configured:

### 1. Install Homebrew Ruby

macOS includes an old Ruby 2.6. Install a newer version via Homebrew:

```bash
brew install ruby
```

### 2. Install CocoaPods via Ruby Gems

**Important:** Install CocoaPods using Ruby gems, NOT Homebrew. Flutter requires the gem version.

```bash
# If you previously installed via Homebrew, uninstall it first
brew uninstall cocoapods  # Only if previously installed

# Install via Ruby gems with Homebrew's Ruby
/opt/homebrew/opt/ruby/bin/gem install cocoapods
```

### 3. Update Your Shell PATH

Add Homebrew's Ruby and gem binaries to your PATH. Add these lines to `~/.zshrc` (or `~/.bash_profile` for bash):

```bash
# Homebrew Ruby (for Flutter/CocoaPods)
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"
export LDFLAGS="-L/opt/homebrew/opt/ruby/lib"
export CPPFLAGS="-I/opt/homebrew/opt/ruby/include"
export PKG_CONFIG_PATH="/opt/homebrew/opt/ruby/lib/pkgconfig"

# Add gem binaries to PATH for CocoaPods
export PATH="/opt/homebrew/lib/ruby/gems/3.4.0/bin:$PATH"
```

**Note:** The gem path version (3.4.0) may differ based on your Ruby version. Check with:
```bash
/opt/homebrew/opt/ruby/bin/gem environment
```
Look for "EXECUTABLE DIRECTORY" in the output.

### 4. Apply Changes

Reload your shell configuration:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

### 5. Verify Installation

```bash
which pod && pod --version
```

Should show:
```
/opt/homebrew/lib/ruby/gems/3.4.0/bin/pod
1.16.2
```

### 6. Build macOS Application

```bash
make package-macos
```

Flutter will now properly detect and use CocoaPods during the build process.

## Platform Build Commands

Once development tools are installed, you can build for different platforms:

### Desktop

```bash
# macOS (requires Xcode + CocoaPods)
make package-macos

# Linux (requires standard build tools)
make package-linux

# Windows (requires Visual Studio Build Tools)
make package-windows
```

### Mobile

```bash
# Android APK (requires Android Studio)
flet build apk

# Android App Bundle (requires Android Studio)
flet build aab

# iOS (requires Xcode + Apple Developer account)
flet build ipa
```

### Web

```bash
# Web application (no additional tools required)
flet build web
```

## Optional: Zed Editor Integration

For Jupyter notebook support in Zed editor:

### 1. Register Jupyter Kernel

```bash
./venv/bin/python -m ipykernel install --user --name de-gui-venv --display-name "Python (DE-GUI venv)"
```

### 2. Configure Zed

- Open command palette (Cmd+Shift+P / Ctrl+Shift+P)
- Run: `repl: refresh kernelspecs`
- Select "Python (DE-GUI venv)" from kernel selector

## Verifying Installation

Test that everything is installed correctly:

```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -c "from config.settings import app_config; print('✓ Installation successful')"
```

You should see:
```
✓ RealSense camera support available  (or ✗ if not installed)
✓ YOLOv11-seg object detection available (recommended)
✓ Installation successful
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'mediapipe'"

Ensure you've activated the virtual environment and installed dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "TypeError: 'NoneType' object is not iterable" on macOS

This was fixed in recent versions. Update to the latest code.

### RealSense camera not detected

- Ensure RealSense SDK is installed
- Install pyrealsense2: `pip install pyrealsense2`
- The app will fall back to webcam if RealSense is unavailable

### Camera enumeration warnings on macOS

The `AVCaptureDeviceTypeExternal` warning is harmless and can be ignored. Camera detection will still work correctly.

### "CocoaPods not installed or not in valid state" (Flet build)

This occurs when:
1. CocoaPods was installed via Homebrew instead of Ruby gems
2. The gem binary path is not in your PATH
3. Flutter is using system Ruby 2.6 instead of Homebrew Ruby

**Solution:**
1. Follow the [macOS Application Packaging](#optional-macos-application-packaging-flet) section above
2. Ensure CocoaPods is installed via `gem install cocoapods` (not Homebrew)
3. Verify with: `which pod` should show `/opt/homebrew/lib/ruby/gems/3.4.0/bin/pod`
4. Open a **new terminal** for PATH changes to take effect

## Next Steps

Once installation is complete, see [README.md](../README.md) for usage instructions.
