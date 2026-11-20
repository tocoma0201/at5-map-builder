@echo off
setlocal
rem 日本語: このバッチのあるフォルダーを作業場所にする。
cd /d "%~dp0"
rem 日本語: py、python、python3の順に利用可能なPythonを探す。
set "PYTHON_EXE="

for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE for /f "delims=" %%I in ('python3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"

rem 日本語: Pythonが見つからない場合は、導入方法を案内して終了する。
if not defined PYTHON_EXE (
  echo Python 3.9以降が見つかりません。
  echo Install_Python.batを実行するか、Windows版Pythonを導入してから再実行してください。
  echo pyランチャーは必須ではありません。py、python、python3のいずれかで起動できます。
  pause
  exit /b 1
)

rem 日本語: 選択したPythonで地図範囲設定画面を起動する。
"%PYTHON_EXE%" at5_map_builder_ui.py
if errorlevel 1 pause
