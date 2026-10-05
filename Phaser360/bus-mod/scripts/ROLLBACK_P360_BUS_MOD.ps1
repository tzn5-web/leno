#requires -version 5.1
<#
Restores the parent driver exported by INSTALL_P360_BUS_MOD.ps1.
If the PHASER360 test certificate did not exist before installation,
the certificate is removed from Root and TrustedPublisher.
#>
[CmdletBinding()]
param(
    [string]$BackupDir
)
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

if (-not $BackupDir) {
    $BackupDir = Get-ChildItem 'C:\P360_AUDIO_SAFE' -Directory -Filter 'P360_BUS_MOD_BACKUP_*' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $BackupDir -or !(Test-Path $BackupDir)) {
    throw 'No PHASER360 bus backup found.'
}

$baseline = @{}
Get-Content (Join-Path $BackupDir 'BASELINE.txt') | ForEach-Object {
    if ($_ -match '^(.*?)=(.*)$') { $baseline[$matches[1]] = $matches[2] }
}

$instance = $baseline['InstanceId']
$hardwareId = $baseline['HardwareId']
$origInfName = $baseline['BeforeInf']
$certThumbprint = $baseline['CertThumbprint']
$certPreRoot = ($baseline['CertPreexistingRoot'] -eq 'True')
$certPrePublisher = ($baseline['CertPreexistingTrustedPublisher'] -eq 'True')

if (-not $instance -or -not $origInfName) {
    throw 'Backup metadata is incomplete; refusing an ambiguous rollback.'
}
if (-not $hardwareId) { $hardwareId = 'PCI\VEN_8086&DEV_3198&CC_0401' }

$current = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $instance } |
    Select-Object -First 1
$modInfName = if ($current) { $current.InfName } else { $null }

$exportRoot = Join-Path $BackupDir 'ORIGINAL_DRIVER'
$infPath = Get-ChildItem $exportRoot -Recurse -Filter $origInfName -File | Select-Object -First 1
if (-not $infPath) {
    $infPath = Get-ChildItem $exportRoot -Recurse -Filter '*.inf' -File | Select-Object -First 1
}
if (-not $infPath) { throw 'Original exported INF not found.' }

& pnputil.exe /add-driver $infPath.FullName |
    Tee-Object -FilePath (Join-Path $BackupDir 'ROLLBACK_STAGE_ORIGINAL.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not stage original driver.' }

$rebootRequired = $false
$ok = [P360.NewDev]::UpdateDriverForPlugAndPlayDevices(
    [IntPtr]::Zero,
    $hardwareId,
    $infPath.FullName,
    $INSTALLFLAG_FORCE,
    [ref]$rebootRequired)

if (-not $ok) {
    $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "Forced original-driver restore failed. Win32=$err"
}

if (-not $rebootRequired) {
    & pnputil.exe /restart-device "$instance" |
        Tee-Object -FilePath (Join-Path $BackupDir 'ROLLBACK_RESTART.txt')
    Start-Sleep -Seconds 3
}

$dev = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -eq $instance } |
    Select-Object -First 1

# Only delete the modified package after the original is active without a pending reboot.
if (-not $rebootRequired -and $modInfName -and $modInfName -ne $origInfName) {
    & pnputil.exe /delete-driver $modInfName /force 2>&1 |
        Tee-Object -FilePath (Join-Path $BackupDir 'ROLLBACK_DELETE_MOD.txt')
}

# Restore the trust baseline, but never remove a certificate that existed before our install.
if ($certThumbprint) {
    if (-not $certPreRoot) {
        Get-ChildItem 'Cert:\LocalMachine\Root' |
            Where-Object Thumbprint -eq $certThumbprint |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
    if (-not $certPrePublisher) {
        Get-ChildItem 'Cert:\LocalMachine\TrustedPublisher' |
            Where-Object Thumbprint -eq $certThumbprint |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

@(
    "RestoredService=$($dev.Service)"
    "RestoredStatus=$($dev.Status)"
    "RestoredProblem=$($dev.ConfigManagerErrorCode)"
    "RebootRequired=$rebootRequired"
    "CertificateRootRestored=$(-not $certPreRoot)"
    "CertificateTrustedPublisherRestored=$(-not $certPrePublisher)"
) | Set-Content -LiteralPath (Join-Path $BackupDir 'ROLLBACK_RESULT.txt') -Encoding UTF8

Write-Host "Restored service: $($dev.Service)"
Write-Host "Status: $($dev.Status) Problem=$($dev.ConfigManagerErrorCode)"
Write-Host "Reboot required: $rebootRequired"
if ($rebootRequired) {
    Write-Host 'Reboot once. The modified INF can be cleaned after the original driver is active.'
}
