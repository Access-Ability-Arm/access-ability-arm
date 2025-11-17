========================================
  Access Ability Arm - Quick Start
========================================

Thank you for trying Access Ability Arm!

This application provides computer vision and robotic arm control
for assistive technology applications.


GETTING STARTED
---------------

1. Extract this entire folder to your desktop

2. Double-click "AccessAbilityArm.exe" to launch

3. Allow Windows Firewall access if prompted

4. The app will automatically detect your webcam


FEATURES
--------

✓ Real-time object detection using RF-DETR (state-of-the-art)
✓ Face landmark tracking with MediaPipe
✓ Automatic camera detection and selection
✓ Optional Intel RealSense depth camera support
✓ Optional UFACTORY Lite6 robotic arm control


KEYBOARD SHORTCUTS
------------------

T - Toggle between detection modes:
    • Object detection (finds and labels objects)
    • Combined mode (objects + face tracking)
    • Face tracking (mouth landmarks)
    • Camera only (raw video)

ESC - Exit application


CONFIGURATION
-------------

Edit config/config.yaml to customize settings:

- Camera selection
- Window size and position
- Detection thresholds
- Robotic arm IP address (if you have one)


OPTIONAL: RealSense Camera
--------------------------

If you have an Intel RealSense D435 depth camera:

1. Install RealSense SDK:
   https://github.com/IntelRealSense/librealsense/releases

2. Launch with:
   AccessAbilityArm.exe --enable-realsense


TROUBLESHOOTING
---------------

Problem: "Camera not detected"
Solution:
  • Check Windows camera permissions (Settings → Privacy)
  • Close other apps using the camera (Zoom, Teams, etc.)
  • Try a different camera from the dropdown

Problem: "Slow performance"
Solution:
  • Press 'T' to switch to face tracking mode (faster)
  • Object detection is CPU-intensive without GPU
  • Consider using a computer with NVIDIA GPU for faster detection

Problem: "App won't start"
Solution:
  • Install Visual C++ Redistributable:
    https://aka.ms/vs/17/release/vc_redist.x64.exe
  • Run from Command Prompt to see error messages


SYSTEM REQUIREMENTS
-------------------

Minimum:
- Windows 10/11 (64-bit)
- 4 GB RAM
- Webcam
- 2 GB free disk space

Recommended:
- Windows 10/11 (64-bit)
- 8 GB RAM
- NVIDIA GPU with CUDA support (for fast object detection)
- Intel RealSense D435 camera (for depth sensing)


SUPPORT
-------

Documentation: See README.md and docs/ folder
GitHub: https://github.com/Access-Ability-Arm/access-ability-arm
Issues: https://github.com/Access-Ability-Arm/access-ability-arm/issues


LICENSE
-------

This project is licensed under the MIT License.
See LICENSE file for details.


PRIVACY
-------

This application processes video locally on your computer.
No data is sent to external servers.
No telemetry or analytics are collected.


VERSION INFORMATION
-------------------

Version: 1.0.0
Build date: 2025-11-16
Python: 3.11
Object Detection: RF-DETR Seg (44.3 mAP, Nov 2025 release)
Face Tracking: MediaPipe


Thank you for using Access Ability Arm!
