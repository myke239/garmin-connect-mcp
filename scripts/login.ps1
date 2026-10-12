$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv313/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
}
& $pythonPath -m garmin_connect_mcp.cli login
if ($LASTEXITCODE -ne 0) { throw 'Garmin login failed' }
& $pythonPath -m garmin_connect_mcp.cli verify
if ($LASTEXITCODE -ne 0) { throw 'Garmin saved-session verification failed' }
