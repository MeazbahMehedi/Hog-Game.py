@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
py -3 tools\build_desktop.py
if errorlevel 1 exit /b 1
echo Native Windows build: dist\Hog\Hog.exe
