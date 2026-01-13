# Application Builds and Packaging

This guide covers building distributable applications for different platforms. **Note:** These steps are only required if you plan to package/distribute the app, not for running it in development mode.

## Development Tools Required

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
# macOS (requires Xcode + CocoaPods) - build on macOS only
make package-macos

# Linux (requires standard build tools) - build on Linux only
make package-linux

# Windows (requires Visual Studio Build Tools) - build on Windows only
make package-windows
```

**Note:** Flutter/Flet do **not support cross-compilation** for desktop platforms. You must build on the target OS. For cross-platform builds from macOS, use:
- **GitHub Actions** with Windows/Linux runners (recommended, free)
- **Virtual Machines** (Parallels, VMware, VirtualBox)
- **Cloud CI/CD** services (AppVeyor, CircleCI)

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

## Troubleshooting

### "CocoaPods not installed or not in valid state"

**Error:** Flet build fails with CocoaPods errors during macOS app packaging.

This occurs when:
1. CocoaPods was installed via Homebrew instead of Ruby gems
2. The gem binary path is not in your PATH
3. Flutter is using system Ruby 2.6 instead of Homebrew Ruby

**Solution:**
1. Follow the [macOS Application Packaging](#macos-application-packaging-flet) section above
2. Ensure CocoaPods is installed via `gem install cocoapods` (not Homebrew)
3. Verify with: `which pod` should show `/opt/homebrew/lib/ruby/gems/3.4.0/bin/pod`
4. Open a **new terminal** for PATH changes to take effect

### Android Build Errors

**Issue:** `ANDROID_HOME not set`

**Solution:**
```bash
export ANDROID_HOME=$HOME/Library/Android/sdk  # macOS
export ANDROID_HOME=$HOME/Android/Sdk  # Linux
```

**Issue:** `sdkmanager not found`

**Solution:**
Install Android SDK via Android Studio or use command line tools.

### iOS Build Errors

**Issue:** `Signing for "Runner" requires a development team`

**Solution:**
1. Open the Xcode project in `build/ios/`
2. Select the Runner target
3. Go to Signing & Capabilities
4. Select your development team

## Next Steps

Once you've built your application, see:
- [Size Optimization](size-optimization.md) - Reduce application bundle size
- [Build Size Analysis](build-size-analysis.md) - Detailed size breakdown
