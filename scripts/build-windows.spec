# PyInstaller spec file for Windows executable
# Build with: pyinstaller build-windows.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include data files
        ('data/models', 'data/models'),  # YOLO/RF-DETR models
        ('config', 'config'),  # Configuration files
        ('README.md', '.'),
        ('LICENSE', '.'),
    ],
    hiddenimports=[
        # Core dependencies
        'flet',
        'cv2',
        'numpy',
        'mediapipe',
        'ultralytics',
        'torch',
        'torchvision',
        'PIL',

        # RF-DETR dependencies
        'rfdetr',
        'supervision',

        # Windows-specific
        'winsdk.windows.devices.enumeration',

        # Optional dependencies (include if available)
        'pyrealsense2',

        # Package internals
        'aaa_core',
        'aaa_core.config',
        'aaa_core.hardware',
        'aaa_core.workers',
        'aaa_core.daemon',
        'aaa_vision',
        'aaa_gui',
        'aaa_gui.flet',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AccessAbilityArm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for debug output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AccessAbilityArm',
)
