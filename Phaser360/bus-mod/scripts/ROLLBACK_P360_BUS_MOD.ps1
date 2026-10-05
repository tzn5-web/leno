#requires -version 5.1
[CmdletBinding()]
param(
    [string]$BackupDir
)
$ErrorActionPreference = 'Stop'

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
if (-not $BackupDir -or !(Test-Path $BackupDir)) { throw 'No PHASER360 bus backup found.' }

$baseline = @{}
Get-Content (Join-Path $BackupDir 'BASELINE.txt') | ForEach-Object {
    if ($_ -match '^(.*?)=(.*)$') { $baseline[$matches[1]] = $matches[2] }
}
$instance = $baseline['InstanceId']
$hardwareId = $baseline['HardwareId']
$origInfName = $baseline['BeforeInf']
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

& pnputil.exe /add-driver $infPath.FullName | Out-Null
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
    & pnputil.exe /restart-device "$instance" | Out-Null
    Start-Sleep -Seconds 3
}

if ($modInfName -and $modInfName -ne $origInfName) {
    & pnputil.exe /delete-driver $modInfName /force 2>&1 | Out-Null
}

$dev = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -eq $instance } |
    Select-Object -First 1

Write-Host "Restored service: $($dev.Service)"
Write-Host "Status: $($dev.Status) Problem=$($dev.ConfigManagerErrorCode)"
Write-Host "Reboot required: $rebootRequired"
