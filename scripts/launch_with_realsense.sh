#!/bin/bash
# RealSense Launcher - Runs app with elevated privileges for USB access
# Preserves user environment for proper GUI display

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=================================================="
echo "Access Ability Arm - RealSense Mode"
echo "=================================================="
echo ""
echo "This launcher runs the app with elevated privileges"
echo "to enable RealSense depth camera access."
echo ""
echo "Note: You will be prompted for your password"
echo "      (unless sudo credentials are cached)"
echo ""

# Preserve display environment variables
export DISPLAY="${DISPLAY:-:0}"

# Run with sudo but preserve user environment for GUI
cd "$SCRIPT_DIR/.."
sudo -E "$SCRIPT_DIR/../venv/bin/python" "$SCRIPT_DIR/../main.py" --enable-realsense "$@"
