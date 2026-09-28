param(
    [Parameter(Mandatory = $true)][string]$AppDirectory,
    [string]$Python311 = "C:\Program Files\Python311\python.exe"
)
$ErrorActionPreference = "Stop"
$appRoot = (Resolve-Path -LiteralPath $AppDirectory).Path
$runtime = Join-Path $appRoot "ios-runtime"
$requirements = Join-Path $PSScriptRoot "../../src-tauri/src-python/adb_auto_player/device/ios/requirements.txt"
if (-not (Test-Path -LiteralPath $Python311)) { throw "Install Python 3.11 or pass -Python311 with its full path." }
$version = & $Python311 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($version -ne "3.11") { throw "The iOS runtime requires Python 3.11." }
& $Python311 -m venv $runtime
if ($LASTEXITCODE -ne 0) { throw "Could not create the iOS runtime." }
& (Join-Path $runtime "Scripts/python.exe") -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) { throw "Could not install iOS dependencies." }
Write-Host "iOS runtime ready. Open ADB Settings > iPhone / iOS > Enable iOS."
