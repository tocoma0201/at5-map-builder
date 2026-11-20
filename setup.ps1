$ErrorActionPreference = "Stop"
# 日本語: スクリプトのある場所を基準に依存ライブラリーを設定する。
Set-Location -LiteralPath $PSScriptRoot

# 日本語: py、python、python3のいずれかからPython 3.9以上を見つける。
function Find-PythonExecutable {
    $launchers = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $launchers += [pscustomobject]@{ Command = "py"; Prefix = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $launchers += [pscustomobject]@{ Command = "python"; Prefix = @() }
    }
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        $launchers += [pscustomobject]@{ Command = "python3"; Prefix = @() }
    }

    foreach ($launcher in $launchers) {
        try {
            $invokeArgs = @($launcher.Prefix) + @("-c", "import sys; print(sys.executable)")
            $pythonPath = (& $launcher.Command @invokeArgs 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
                continue
            }
            $pythonPath = $pythonPath.Trim()
            if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
                continue
            }

            $versionText = & $pythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$versionText -ge [version]"3.9") {
                return $pythonPath
            }
        } catch {
            continue
        }
    }
    return $null
}

$pythonExe = Find-PythonExecutable
# 日本語: 検出したPythonでrequirements.txtのライブラリーをインストールする。
if (-not $pythonExe) {
    Write-Host "Python 3.9 or later was not found." -ForegroundColor Yellow
    Write-Host "Run Install_Python.bat, or install Python for Windows using your preferred method."
    Write-Host "The py launcher is optional; python or python3 on PATH also works."
    exit 1
}

Write-Host "Using: $pythonExe"
& $pythonExe --version
& $pythonExe -m pip install --user -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency setup failed (exit=$LASTEXITCODE)"
}

Write-Host ""
Write-Host "Setup complete. Start the tool with Start_AT5_Map_Builder.bat."
Write-Host "Insight Map Creator must be installed separately; see IMC_INSTALL.md."
