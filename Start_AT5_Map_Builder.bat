@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE="

for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE for /f "delims=" %%I in ('python3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE (
  echo Python 3.9 or later was not found.
  echo Run Install_Python.bat or install Python for Windows, then try again.
  echo The py launcher is optional. Python must be available as py, python, or python3.
  pause
  exit /b 1
)

"%PYTHON_EXE%" at5_map_builder_ui.py
if errorlevel 1 pause
