<#
Creates a .venv in the project root, installs dependencies from requirements.txt,
and prints instructions to activate the venv in the current shell.
Usage (PowerShell):
  .\scripts\setup_venv.ps1        # creates venv and installs deps
  # To activate in current shell, dot-source the activate script:
  . .\.venv\Scripts\Activate.ps1
#>

param(
  [string]$VenvDir = ".venv"
)

if (-not (Test-Path $VenvDir)) {
  Write-Host "Creating virtual environment in $VenvDir"
  python -m venv $VenvDir
} else {
  Write-Host "Virtual environment $VenvDir already exists"
}

$pythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  Write-Error "Python executable not found at $pythonExe"
  exit 1
}

# Upgrade pip and ensure basic packaging tools
& $pythonExe -m pip install --upgrade pip setuptools wheel

if (Test-Path "requirements.txt") {
  Write-Host "Installing requirements.txt..."
  & $pythonExe -m pip install -r requirements.txt
}

Write-Host ""
Write-Host "To activate the venv in PowerShell run (dot-source to activate in this shell):"
Write-Host "  . .\$VenvDir\Scripts\Activate.ps1"
Write-Host "Or in cmd.exe:"
Write-Host "  .\$VenvDir\Scripts\activate.bat"
