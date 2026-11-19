@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher "py" was not found.
  echo Install Python 3 for Windows, then run setup.ps1 again.
  pause
  exit /b 1
)
py -3 at5_map_builder_ui.py
if errorlevel 1 pause
