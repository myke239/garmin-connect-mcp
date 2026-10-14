$ErrorActionPreference = 'Stop'
$directory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\tools\artifact-signing'))
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$msi = Join-Path $directory 'client-tools.msi'
Invoke-WebRequest 'https://download.microsoft.com/download/70ad2c3b-761f-4aa9-a9de-e7405aa2b4c1/ArtifactSigningClientTools.msi' -OutFile $msi
$signature = Get-AuthenticodeSignature -LiteralPath $msi
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -ne 'Microsoft Corporation') { throw 'Microsoft signing client signature is not trusted' }
$process = Start-Process msiexec.exe -ArgumentList @('/a', ('"'+$msi+'"'), '/qn', ('TARGETDIR="'+$directory+'\extracted"')) -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) { throw 'Signing tools extraction failed' }
$tool = @(Get-ChildItem -LiteralPath (Join-Path $directory 'extracted') -Recurse -File -Filter signtool.exe | Where-Object { $_.FullName -match '\\x64\\' })
$dll = @(Get-ChildItem -LiteralPath (Join-Path $directory 'extracted') -Recurse -File -Filter Azure.CodeSigning.Dlib.dll | Where-Object { $_.FullName -match '\\x64\\' })
if ($tool.Count -ne 1 -or $dll.Count -ne 1) { throw 'Expected one x64 signing tool and plugin' }
$metadata = Join-Path $directory 'metadata.json'
@{Endpoint=$env:SIGNING_ENDPOINT;CodeSigningAccountName=$env:SIGNING_ACCOUNT;CertificateProfileName=$env:SIGNING_PROFILE} | ConvertTo-Json | Set-Content -LiteralPath $metadata -Encoding utf8
$env:DAS_KREB_SIGNTOOL = $tool[0].FullName
$env:DAS_KREB_SIGNING_DLL = $dll[0].FullName
$env:DAS_KREB_SIGNING_METADATA = $metadata
