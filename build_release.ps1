# Zostavi prenosny balik AirDrop s priloženym Pythonom (netreba ho instalovat).
# Pouzitie:  powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.0.0
param(
    [string]$Version = "1.0.0",
    [string]$PythonVersion = "3.14.8"
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$dist = Join-Path $root "dist"
$cache = Join-Path $dist "cache"
$name = "AirDrop-Windows-v$Version"
$stage = Join-Path $dist $name
$zip = Join-Path $dist "AirDrop-Windows.zip"  # stabilny nazov -> odkaz releases/latest/download/AirDrop-Windows.zip

New-Item -ItemType Directory -Force $cache | Out-Null
$pyZip = Join-Path $cache "python-$PythonVersion-embed-amd64.zip"
if (-not (Test-Path $pyZip)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
    Write-Host "Stahujem $url"
    Invoke-WebRequest $url -OutFile $pyZip -UseBasicParsing
}

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory $stage | Out-Null
Expand-Archive $pyZip (Join-Path $stage "python")

# Kazdy spustitelny subor musi byt platne podpisany Python Software Foundation
# (alebo Microsoftom - runtime kniznica vcruntime140.dll).
$binaries = Get-ChildItem (Join-Path $stage "python") -Recurse -Include *.exe, *.dll, *.pyd
foreach ($f in $binaries) {
    $sig = Get-AuthenticodeSignature $f.FullName
    if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=(Python Software Foundation|Microsoft Corporation),") {
        throw "Neplatny podpis: $($f.Name) ($($sig.Status), $($sig.SignerCertificate.Subject))"
    }
}
Write-Host "Podpisy OK ($($binaries.Count) suborov)"

Copy-Item (Join-Path $root "airdrop.py"), (Join-Path $root "index.html"), (Join-Path $root "qrcode.min.js"), (Join-Path $root "start.bat"),
          (Join-Path $root "README.md"), (Join-Path $root "README_SK.md") -Destination $stage

if (Test-Path $zip) { Remove-Item $zip }
# tar.exe (sucast Windows 10/11) - Compress-Archive v PS 5.1 zapisuje cesty so spatnymi lomkami
& "$env:SystemRoot\System32\tar.exe" -a -c -f $zip -C $dist $name
if ($LASTEXITCODE -ne 0) { throw "Vytvorenie ZIP zlyhalo." }
Write-Host "Hotovo: $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
