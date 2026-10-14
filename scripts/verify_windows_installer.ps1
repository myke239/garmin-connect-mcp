param([Parameter(Mandatory=$true)][string]$Installer,[string]$ExpectedPublisher)
$ErrorActionPreference='Stop'
$testRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\installer-test'))
$version=(Get-Content (Join-Path $PSScriptRoot '..\VERSION') -Raw).Trim()
$priorLocal=$env:LOCALAPPDATA;$priorData=$env:GARMIN_MCP_DATA_DIR
try {
 $env:LOCALAPPDATA=Join-Path $testRoot 'local'
 $env:GARMIN_MCP_DATA_DIR=Join-Path $testRoot 'private'
 New-Item -ItemType Directory -Force -Path $env:GARMIN_MCP_DATA_DIR | Out-Null
 $sentinel=Join-Path $env:GARMIN_MCP_DATA_DIR 'preserve.txt'
 Set-Content -LiteralPath $sentinel 'private data must remain' -Encoding ascii
 $application=Join-Path $env:LOCALAPPDATA "Programs\GarminConnectMCP\releases\$version-installer"
 $process=Start-Process -FilePath ([IO.Path]::GetFullPath($Installer)) -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="'+$application+'"')) -Wait -PassThru -WindowStyle Hidden
 if ($process.ExitCode -ne 0) { throw 'Installer execution failed' }
 $receipt=Join-Path $env:LOCALAPPDATA 'Programs\GarminConnectMCP\installation.json'
 $metadata=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
 if ($metadata.version -ne $version -or $metadata.launcher -ne (Join-Path $application 'garmin-connect.exe')) { throw 'Installed receipt mismatch' }
 & $metadata.launcher doctor
 if ($LASTEXITCODE -ne 0) { throw 'Installed launcher failed' }
 $fileVersion=(Get-Item -LiteralPath $metadata.launcher).VersionInfo
 if ($fileVersion.CompanyName -ne 'Das Kreb' -or $fileVersion.ProductVersion -ne $version) { throw 'Executable publisher metadata mismatch' }
 $uninstaller=Join-Path $application 'unins000.exe'
 if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'Missing uninstaller' }
 if ($ExpectedPublisher) { & (Join-Path $PSScriptRoot 'verify_signatures.ps1') -Path $uninstaller -ExpectedPublisher $ExpectedPublisher }
 $process=Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru -WindowStyle Hidden
 if ($process.ExitCode -ne 0 -or (Test-Path -LiteralPath $receipt)) { throw 'Uninstall registration cleanup failed' }
 if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'private data must remain') { throw 'Uninstaller modified private data' }
 Write-Output 'PASS: per-user installation, launch, vendor metadata, uninstall and private-data preservation'
} finally { $env:LOCALAPPDATA=$priorLocal;$env:GARMIN_MCP_DATA_DIR=$priorData }
