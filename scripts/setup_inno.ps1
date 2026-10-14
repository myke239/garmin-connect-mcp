param([string]$Directory = (Join-Path $PSScriptRoot '..\work\tools\inno'))
$ErrorActionPreference = 'Stop'
$directoryPath = [IO.Path]::GetFullPath($Directory)
New-Item -ItemType Directory -Force -Path $directoryPath | Out-Null
$download = Join-Path $directoryPath 'innosetup-6.7.3.exe'
Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $download
$signature = Get-AuthenticodeSignature -LiteralPath $download
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -ne 'Pyrsys B.V.') { throw 'Inno compiler download signature is not trusted' }
$process = Start-Process -FilePath $download -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',('/DIR="'+$directoryPath+'"')) -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) { throw 'Compiler installation failed' }
$env:DAS_KREB_INNO = Join-Path $directoryPath 'ISCC.exe'
