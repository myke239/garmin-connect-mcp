param(
 [Parameter(Mandatory=$true)][string]$Path,
 [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
 [switch]$Recursive
)
$ErrorActionPreference = 'Stop'
$target = Get-Item -LiteralPath $Path
$files = if ($target.PSIsContainer) { Get-ChildItem -LiteralPath $target.FullName -File -Recurse:$Recursive | Where-Object { $_.Extension -in '.exe','.dll','.pyd' } } else { @($target) }
if (-not $files) { throw 'No executable files to verify' }
foreach ($file in $files) {
 $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
 if ($signature.Status -ne 'Valid') { throw "Invalid signature: $($file.Name) ($($signature.Status))" }
 if (-not $signature.TimeStamperCertificate) { throw "Missing trusted timestamp: $($file.Name)" }
 $publisher = $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
 if ($publisher -ne $ExpectedPublisher) { throw "Unexpected publisher: $($file.Name)" }
 Write-Output "PASS: $($file.Name) signature, publisher and timestamp"
}
