param(
 [Parameter(Mandatory=$true)][string]$Bundle,
 [string]$Output = (Join-Path $PSScriptRoot '..\dist\installer'),
 [string]$Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
 [switch]$UnsignedTest,
 [string]$SignTool,
 [string]$SigningDll,
 [string]$SigningMetadata,
 [string]$ExpectedPublisher
)
$ErrorActionPreference = 'Stop'
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\VERSION') -Raw).Trim()
$bundlePath = (Resolve-Path -LiteralPath $Bundle).Path
if (-not (Test-Path -LiteralPath (Join-Path $bundlePath 'garmin-connect.exe'))) { throw 'Complete executable bundle required' }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install the official Inno Setup compiler first' }
$argsList = @("/DAppVersion=$version", "/DBundleDir=$bundlePath", "/DOutputPath=$([IO.Path]::GetFullPath($Output))")
if (-not $UnsignedTest) {
 foreach ($required in @($SignTool,$SigningDll,$SigningMetadata,$ExpectedPublisher)) { if (-not $required) { throw 'Trusted builds require signing tools, metadata and verified publisher' } }
 & (Join-Path $PSScriptRoot 'verify_signatures.ps1') -Path $bundlePath -ExpectedPublisher $ExpectedPublisher -Recursive
 $signCommand = '$q' + $SignTool + '$q sign /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 /dlib $q' + $SigningDll + '$q /dmdf $q' + $SigningMetadata + '$q $f'
 $argsList += @('/DTrustedRelease=1', '/SdasKreb=' + $signCommand)
}
& $Compiler @argsList (Join-Path $PSScriptRoot 'windows-installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
$installer = Join-Path $Output "garmin-connect-mcp-$version-windows-x64-setup.exe"
if (-not $UnsignedTest) { & (Join-Path $PSScriptRoot 'verify_signatures.ps1') -Path $installer -ExpectedPublisher $ExpectedPublisher }
else { Write-Warning 'UNSIGNED TEST INSTALLER: do not publish as a verified release.' }
