@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment in .venv
  python -m venv .venv
) else (
  echo .venv already exists
)
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if exist requirements.txt (
  echo Installing requirements.txt...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo.
echo To activate the venv:
echo   PowerShell: . .\.venv\Scripts\Activate.ps1
echo   CMD:      .\.venv\Scripts\activate.bat
endlocal
