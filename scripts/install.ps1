param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\GarminConnectMCP'), [switch]$Remote)
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install.py'
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
$existingUv = Join-Path $InstallDir 'tools\uv.exe'
if (-not $uvCommand -and (Test-Path -LiteralPath $existingUv)) { $uvCommand = Get-Item -LiteralPath $existingUv }
if (-not $uvCommand) {
    $tools = Join-Path $InstallDir 'tools'
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $bootstrap = Join-Path $tools 'install-uv.ps1'
    Invoke-WebRequest 'https://astral.sh/uv/install.ps1' -OutFile $bootstrap
    $previousDir = $env:UV_INSTALL_DIR
    $previousNoPath = $env:UV_NO_MODIFY_PATH
    try {
        $env:UV_INSTALL_DIR = $tools
        $env:UV_NO_MODIFY_PATH = '1'
        & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap
        if ($LASTEXITCODE -ne 0) { throw 'uv installation failed.' }
    } finally {
        $env:UV_INSTALL_DIR = $previousDir
        $env:UV_NO_MODIFY_PATH = $previousNoPath
    }
    $uvPath = Join-Path $tools 'uv.exe'
} else { $uvPath = $(if ($uvCommand -is [System.IO.FileInfo]) { $uvCommand.FullName } else { $uvCommand.Source }) }
$previousEnvironment = @{}
foreach ($name in @('UV_SYSTEM_CERTS', 'UV_PYTHON_PREFERENCE', 'UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR')) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:UV_SYSTEM_CERTS = 'true'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    $env:UV_CACHE_DIR = Join-Path $InstallDir 'cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallDir 'python'
    $installerArgs = @('run', '--no-project', '--python', '3.13', $installer, '--uv', $uvPath, '--install-dir', $InstallDir)
    if ($Remote) { $installerArgs += '--remote' }
    & $uvPath @installerArgs
    if ($LASTEXITCODE -ne 0) { throw 'Garmin Connect installation failed; existing launcher was retained.' }
} finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
