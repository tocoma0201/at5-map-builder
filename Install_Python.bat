@echo off
setlocal
rem 日本語: WinGetがあればPythonを導入し、なければ公式ページを開く。
echo This will install Python 3.14 for Windows using WinGet.
echo If WinGet is unavailable, the official Python downloads page will open.
echo.

rem 日本語: パッケージ管理ツールの有無で導入方法を切り替える。
where winget >nul 2>nul
if errorlevel 1 (
  echo WinGet was not found. Opening the official Python downloads page.
  start "" "https://www.python.org/downloads/windows/"
  echo Install Python 3.9 or later, then close and reopen this folder.
  pause
  exit /b 0
)

winget install --id Python.Python.3.14 --exact --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
  echo.
  echo WinGet could not complete the installation.
  echo You can install Python manually from:
  echo https://www.python.org/downloads/windows/
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

echo.
echo Python installation finished.
echo Close and reopen PowerShell or File Explorer, then run setup.ps1.
pause
