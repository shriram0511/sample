#!/usr/bin/env bash
# Creates a virtual environment, installs dependencies,
# and downloads Playwright browser binaries.
set -e

VENV_DIR=".venv"

echo "==> Creating virtual environment in $VENV_DIR ..."
python -m venv "$VENV_DIR"

echo "==> Activating virtual environment ..."
# shellcheck disable=SC1091
source "$VENV_DIR/Scripts/activate" 2>/dev/null || source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip ..."
pip install --upgrade pip

echo "==> Installing Python dependencies ..."
pip install -r requirements.txt

echo "==> Installing Playwright Chromium browser ..."
playwright install chromium

echo ""
echo "Setup complete!"
echo ""
echo "To activate the environment in a new shell, run:"
echo "  source .venv/Scripts/activate   # Windows Git Bash / MSYS2"
echo "  source .venv/bin/activate       # Linux / macOS"
echo ""
echo "Then run the converter:"
echo "  python convert_mermaid.py"
echo ""
echo "To also generate diagram descriptions, set your key first:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  python convert_mermaid.py"
