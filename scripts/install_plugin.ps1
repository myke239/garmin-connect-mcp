param([string]$PythonPath)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) {
    foreach ($relativePath in @('.venv313\Scripts\python.exe', '.venv\Scripts\python.exe')) {
        $candidate = Join-Path $projectDirectory $relativePath
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $PythonPath = $candidate
            break
        }
    }
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw 'Install the project virtual environment first, or supply -PythonPath.'
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
& $PythonPath -c 'import garmin_connect_mcp, mcp'
if ($LASTEXITCODE -ne 0) { throw 'The interpreter must have Garmin Connect MCP installed.' }
$manifestPath = Join-Path $projectDirectory 'plugins\garmin-connect\.mcp.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest.mcpServers.'garmin-connect'.command = $PythonPath.Replace('\', '/')
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10) + [Environment]::NewLine, $utf8)
& codex plugin marketplace add $projectDirectory
if ($LASTEXITCODE -ne 0) { throw 'Marketplace registration failed.' }
& codex plugin add 'garmin-connect@myke-garmin'
if ($LASTEXITCODE -ne 0) { throw 'Plugin installation failed.' }
Write-Host 'Garmin Connect plugin installed. Open a fresh Codex chat to load it.'
