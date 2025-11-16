#!/bin/bash
# Setup RealSense USB Permissions for macOS
# This allows non-root access to RealSense cameras

set -e

echo "=================================================="
echo "RealSense USB Permissions Setup for macOS"
echo "=================================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ ERROR: Do not run this script with sudo"
    echo "   The script will request sudo permissions when needed"
    exit 1
fi

# Check if RealSense camera is connected
echo "Checking for RealSense camera..."
if ! system_profiler SPUSBDataType | grep -q "RealSense"; then
    echo "⚠️  WARNING: No RealSense camera detected"
    echo "   Please connect your RealSense camera and try again"
    exit 1
fi

echo "✓ RealSense camera detected"
echo ""

# Get camera details
echo "Camera information:"
system_profiler SPUSBDataType | grep -A 10 "RealSense" | head -n 15
echo ""

# Unfortunately, macOS doesn't support udev rules like Linux
# The only reliable way is to use sudo, but we can create a helper

echo "=================================================="
echo "macOS USB Permission Limitation"
echo "=================================================="
echo ""
echo "Unfortunately, macOS does not provide a way to grant"
echo "permanent USB device access without elevated privileges."
echo ""
echo "Unlike Linux (which uses udev rules), macOS requires"
echo "applications to run with sudo to access USB bulk transfers"
echo "used by RealSense cameras."
echo ""
echo "WORKAROUNDS:"
echo ""
echo "1. Run with sudo (GUI may not display properly):"
echo "   sudo ./venv/bin/python main.py --enable-realsense"
echo ""
echo "2. Use RealSense as standard webcam (no depth):"
echo "   python main.py"
echo "   This uses OpenCV to access RGB only, no sudo needed"
echo ""
echo "3. Create a launcher script (recommended):"
echo "   See setup below..."
echo ""

read -p "Create launcher script? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting without creating launcher"
    exit 0
fi

# Create launcher script
LAUNCHER_PATH="$(cd "$(dirname "$0")/.." && pwd)/launch_with_realsense.sh"

cat > "$LAUNCHER_PATH" << 'EOF'
#!/bin/bash
# RealSense Launcher - Runs app with elevated privileges for USB access
# This preserves the GUI environment while allowing RealSense access

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Preserve user environment for GUI
export USER="$SUDO_USER"
export HOME="/Users/$SUDO_USER"

# Run the app with venv Python
cd "$SCRIPT_DIR"
sudo -E ./venv/bin/python main.py --enable-realsense "$@"
EOF

chmod +x "$LAUNCHER_PATH"

echo ""
echo "✓ Launcher script created: $(basename "$LAUNCHER_PATH")"
echo ""
echo "=================================================="
echo "Usage"
echo "=================================================="
echo ""
echo "To run with RealSense depth support:"
echo "  ./launch_with_realsense.sh"
echo ""
echo "To run without depth (RGB only, no sudo):"
echo "  python main.py"
echo ""
echo "Note: You will be prompted for your password each time"
echo "      you run the launcher script."
echo ""
