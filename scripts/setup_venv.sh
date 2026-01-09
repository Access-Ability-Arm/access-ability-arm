#!/usr/bin/env bash
set -euo pipefail
VENV=${1:-.venv}
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment in $VENV"
  python3 -m venv "$VENV"
else
  echo "$VENV already exists"
fi

"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
if [ -f requirements.txt ]; then
  echo "Installing requirements.txt..."
  "$VENV/bin/python" -m pip install -r requirements.txt
fi

echo "To activate: source $VENV/bin/activate"
