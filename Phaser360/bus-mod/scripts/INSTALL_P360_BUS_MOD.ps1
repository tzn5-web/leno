#requires -version 5.1
<#
PHASER360 Gemini Lake bus mod installer
Target: Google Phaser360 / Octopus, Windows 10 x64, PCI 8086:3198.

Changes:
- imports the package's test certificate
- exports the currently bound 8086:3198 driver for rollback
- stages and force-binds the test-signed SklHDAudBus-derived package

Does NOT:
- delete the original Intel package
- boot SOF firmware
- send DSP IPC
- create an audio endpoint
- play audio
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Is-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
if (-not (Is-Admin)) { throw 'Run this script as Administrator.' }

if (-not ('P360.NewDev' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
  public static class NewDev {
    [DllImport("newdev.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool UpdateDriverForPlugAndPlayDevices(
      IntPtr hwndParent,
      string HardwareId,
      string FullInfPath,
      uint InstallFlags,
      out bool bRebootRequired);
  }
}
'@
}

$INSTALLFLAG_FORCE = 0x00000001
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inf  = (Resolve-Path (Join-Path $root 'sklhdaudbus.inf')).Path
$sys  = (Resolve-Path (Join-Path $root 'sklhdaudbus.sys')).Path
$cat  = (Resolve-Path (Join-Path $root 'sklhdaudbus.cat')).Path
$cer  = (Resolve-Path (Join-Path $root 'PHASER360_TEST_DRIVER.cer')).Path

# Machine guard: never bind this package on an unrelated PC.
$cs = Get-CimInstance Win32_ComputerSystem
$bb = Get-CimInstance Win32_BaseBoard
$identity = "$($cs.Manufacturer) $($cs.Model) $($bb.Manufacturer) $($bb.Product)"
if ($identity -notmatch '(?i)Google' -or $identity -notmatch '(?i)(Phaser360|Octopus)') {
    throw "Target guard failed. This package is only for Google Phaser360/Octopus. Detected: $identity"
}

# This is a test-signed kernel package. Refuse to proceed unless TestSigning is already enabled.
$bcd = (& bcdedit.exe /enum "{current}" 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw 'Could not read current BCD configuration.' }
if ($bcd -notmatch '(?im)^\s*testsigning\s+(Yes|Da|On)\s*$') {
    throw 'Windows TestSigning is not enabled. No driver changes were made.'
}

# Validate that all signed payloads carry the certificate shipped with the package.
$certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
$certThumbprint = $certObj.Thumbprint.ToUpperInvariant()
foreach ($file in @($sys,$cat)) {
    $sig = Get-AuthenticodeSignature -LiteralPath $file
    if (-not $sig.SignerCertificate) {
        throw "Package signature missing: $file"
    }
    if ($sig.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $certThumbprint) {
        throw "Package signer mismatch: $file"
    }
}
$infText = Get-Content -LiteralPath $inf -Raw
if ($infText -notmatch 'PCI\\VEN_8086&DEV_3198&CC_0401') {
    throw 'INF target mismatch: Gemini Lake 8086:3198 match is missing.'
}

$target = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*' } |
    Select-Object -First 1
if (-not $target) { throw 'PCI 8086:3198 is not enumerated. No changes were made.' }
if ($target.Status -ne 'OK' -or [int]$target.ConfigManagerErrorCode -ne 0) {
    throw "Current 8086:3198 parent is not healthy: Status=$($target.Status) Problem=$($target.ConfigManagerErrorCode)"
}
if ($target.Service -eq 'SklHDAudBus') {
    Write-Host 'PHASER360 bus mod is already bound. Nothing to change.'
    exit 0
}
if ($target.Service -ne 'IntcAudioBus') {
    throw "Unexpected current parent service '$($target.Service)'. Expected IntcAudioBus; refusing force-bind."
}

$hwids = @()
try {
    $hwids = @((Get-PnpDeviceProperty -InstanceId $target.PNPDeviceID -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction Stop).Data)
} catch {}
$hardwareId = $hwids | Where-Object { $_ -ieq 'PCI\VEN_8086&DEV_3198&CC_0401' } | Select-Object -First 1
if (-not $hardwareId) {
    $hardwareId = $hwids | Where-Object { $_ -like 'PCI\VEN_8086&DEV_3198*' } | Select-Object -First 1
}
if (-not $hardwareId) { $hardwareId = 'PCI\VEN_8086&DEV_3198&CC_0401' }

$bound = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1
if (-not $bound -or -not $bound.InfName) {
    throw 'Could not identify the currently bound parent driver package. No changes were made.'
}

$rootCertExists = [bool](Get-ChildItem 'Cert:\LocalMachine\Root' |
    Where-Object Thumbprint -eq $certThumbprint | Select-Object -First 1)
$publisherCertExists = [bool](Get-ChildItem 'Cert:\LocalMachine\TrustedPublisher' |
    Where-Object Thumbprint -eq $certThumbprint | Select-Object -First 1)

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "C:\P360_AUDIO_SAFE\P360_BUS_MOD_BACKUP_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

@(
    "Identity=$identity"
    "InstanceId=$($target.PNPDeviceID)"
    "HardwareId=$hardwareId"
    "BeforeName=$($target.Name)"
    "BeforeStatus=$($target.Status)"
    "BeforeProblem=$($target.ConfigManagerErrorCode)"
    "BeforeService=$($target.Service)"
    "BeforeInf=$($bound.InfName)"
    "BeforeProvider=$($bound.DriverProviderName)"
    "BeforeVersion=$($bound.DriverVersion)"
    "CertThumbprint=$certThumbprint"
    "CertPreexistingRoot=$rootCertExists"
    "CertPreexistingTrustedPublisher=$publisherCertExists"
    "PackageSysSHA256=$((Get-FileHash $sys -Algorithm SHA256).Hash)"
    "PackageCatSHA256=$((Get-FileHash $cat -Algorithm SHA256).Hash)"
) | Set-Content -LiteralPath (Join-Path $backup 'BASELINE.txt') -Encoding UTF8
$bcd | Set-Content -LiteralPath (Join-Path $backup 'BCD_BEFORE.txt') -Encoding UTF8

# Freeze the exact current package before changing trust or binding.
$export = Join-Path $backup 'ORIGINAL_DRIVER'
New-Item -ItemType Directory -Force -Path $export | Out-Null
& pnputil.exe /export-driver $bound.InfName $export |
    Tee-Object -FilePath (Join-Path $backup 'EXPORT_ORIGINAL.txt')
if ($LASTEXITCODE -ne 0) {
    throw "Could not export current driver $($bound.InfName). No bind was attempted."
}

Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPublisher' | Out-Null

# After trust import, require Windows to see both signatures as valid.
foreach ($file in @($sys,$cat)) {
    $sig = Get-AuthenticodeSignature -LiteralPath $file
    if ($sig.Status -ne 'Valid') {
        throw "Signature validation failed after certificate import: $file -> $($sig.Status). Backup: $backup"
    }
}

# Stage only; do not rely on PnP driver ranking because the current Intel package is WHQL.
& pnputil.exe /add-driver $inf |
    Tee-Object -FilePath (Join-Path $backup 'STAGE_MOD.txt')
if ($LASTEXITCODE -ne 0) { throw "pnputil staging failed: $LASTEXITCODE. Backup: $backup" }

$rebootRequired = $false
$ok = [P360.NewDev]::UpdateDriverForPlugAndPlayDevices(
    [IntPtr]::Zero,
    $hardwareId,
    $inf,
    $INSTALLFLAG_FORCE,
    [ref]$rebootRequired)

if (-not $ok) {
    $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "Forced driver update failed. Win32=$err. Backup/rollback data: $backup"
}

@(
    "ForceBindHardwareId=$hardwareId"
    "RebootRequired=$rebootRequired"
) | Set-Content -LiteralPath (Join-Path $backup 'FORCE_BIND.txt') -Encoding UTF8

Start-Sleep -Seconds 2
$after = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1

if ($after.Service -ne 'SklHDAudBus' -and -not $rebootRequired) {
    & pnputil.exe /restart-device "$($target.PNPDeviceID)" |
        Tee-Object -FilePath (Join-Path $backup 'RESTART.txt')
    Start-Sleep -Seconds 3
    $after = Get-CimInstance Win32_PnPEntity |
        Where-Object { $_.PNPDeviceID -eq $target.PNPDeviceID } |
        Select-Object -First 1
}

$modBound = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1

@(
    "AfterName=$($after.Name)"
    "AfterStatus=$($after.Status)"
    "AfterProblem=$($after.ConfigManagerErrorCode)"
    "AfterService=$($after.Service)"
    "AfterInf=$($modBound.InfName)"
    "AfterProvider=$($modBound.DriverProviderName)"
    "AfterVersion=$($modBound.DriverVersion)"
    "RebootRequired=$rebootRequired"
) | Set-Content -LiteralPath (Join-Path $backup 'AFTER.txt') -Encoding UTF8

if (-not $rebootRequired -and ($after.Service -ne 'SklHDAudBus' -or [int]$after.ConfigManagerErrorCode -ne 0)) {
    throw "Bus mod did not bind cleanly. Run ROLLBACK_P360_BUS_MOD.ps1. Backup: $backup"
}

& pnputil.exe /enum-devices /instanceid "$($target.PNPDeviceID)" /relations 2>&1 |
    Set-Content -LiteralPath (Join-Path $backup 'RELATIONS.txt') -Encoding UTF8

Write-Host ''
Write-Host 'PHASER360 BUS MOD: FORCE-BIND COMPLETED'
Write-Host "Parent service now: $($after.Service)"
Write-Host "Reboot required: $rebootRequired"
Write-Host "Rollback snapshot: $backup"
Write-Host 'No SOF firmware boot, DSP IPC, endpoint creation or audio playback was attempted.'
if ($rebootRequired) {
    Write-Host 'REBOOT ONCE, then run VERIFY_P360_BUS_MOD.ps1.'
} else {
    Write-Host 'Run VERIFY_P360_BUS_MOD.ps1 now.'
}
