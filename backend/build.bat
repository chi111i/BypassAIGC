@echo off
REM Build script for Windows executable

echo Installing dependencies...
pip install -r requirements.txt
pip install -r requirements-build.txt

echo Building executable...
pyinstaller build.spec

echo.
echo Build complete! Executable is in the dist folder.
pause
