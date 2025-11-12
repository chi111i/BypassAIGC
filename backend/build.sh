#!/bin/bash
# Build script for Unix-like systems (can also build Windows exe on Wine)

echo "Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-build.txt

echo "Building executable..."
pyinstaller build.spec

echo ""
echo "Build complete! Executable is in the dist folder."
