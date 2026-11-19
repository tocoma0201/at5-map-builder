$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonLauncher) {
    Write-Host "Python 3 for Windows is required. Install it from https://www.python.org/downloads/windows/ and enable the Python Launcher, then run this script again." -ForegroundColor Yellow
    exit 1
}

py -3 --version
py -3 -m pip install --user -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency setup failed (exit=$LASTEXITCODE)"
}

Write-Host ""
Write-Host "Setup complete. Start the tool with Start_AT5_Map_Builder.bat."
Write-Host "Insight Map Creator must be installed separately; see IMC_INSTALL.md."
