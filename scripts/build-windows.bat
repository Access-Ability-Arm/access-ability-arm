@echo off
REM Build script for Windows standalone executable
REM Run this on a Windows machine with Python 3.11

echo ========================================
echo Access Ability Arm - Windows Build
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist\" rmdir /s /q dist
if exist "build\" rmdir /s /q build

REM Build executable
echo Building Windows executable...
pyinstaller scripts\build-windows.spec

REM Check if build succeeded
if exist "dist\AccessAbilityArm\AccessAbilityArm.exe" (
    echo.
    echo ========================================
    echo Build successful!
    echo ========================================
    echo Executable location: dist\AccessAbilityArm\
    echo.
    echo To distribute, zip the entire dist\AccessAbilityArm\ folder
    echo and send to your colleague.
    echo.
) else (
    echo.
    echo ========================================
    echo Build FAILED!
    echo ========================================
    echo Check the output above for errors.
)

pause
