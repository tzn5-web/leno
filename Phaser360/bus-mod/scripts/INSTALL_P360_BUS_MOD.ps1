#requires -version 5.1
# PHASER360 Gemini Lake bus mod installer
# Replaces only the driver bound to PCI VEN_8086 DEV_3198.
# Does not delete the Intel package and does not start audio playback.

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
$cer  = (Resolve-Path (Join-Path $root 'PHASER360_TEST_DRIVER.cer')).Path

$target = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*' } |
    Select-Object -First 1
if (-not $target) { throw 'PCI 8086:3198 is not enumerated. Stop.' }

$hwids = @()
try {
    $hwids = @((Get-PnpDeviceProperty -InstanceId $target.PNPDeviceID -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction Stop).Data)
} catch {}
$hardwareId = $hwids | Where-Object { $_ -ieq 'PCI\VEN_8086&DEV_3198&CC_0401' } | Select-Object -First 1
if (-not $hardwareId) {
    $hardwareId = $hwids | Where-Object { $_ -like 'PCI\VEN_8086&DEV_3198*' } | Select-Object -First 1
}
if (-not $hardwareId) { $hardwareId = 'PCI\VEN_8086&DEV_3198&CC_0401' }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "C:\P360_AUDIO_SAFE\P360_BUS_MOD_BACKUP_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$bound = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1

@(
    "InstanceId=$($target.PNPDeviceID)"
    "HardwareId=$hardwareId"
    "BeforeName=$($target.Name)"
    "BeforeStatus=$($target.Status)"
    "BeforeProblem=$($target.ConfigManagerErrorCode)"
    "BeforeService=$($target.Service)"
    "BeforeInf=$($bound.InfName)"
    "BeforeProvider=$($bound.DriverProviderName)"
    "BeforeVersion=$($bound.DriverVersion)"
) | Set-Content -LiteralPath (Join-Path $backup 'BASELINE.txt') -Encoding UTF8

if ($bound -and $bound.InfName) {
    $export = Join-Path $backup 'ORIGINAL_DRIVER'
    New-Item -ItemType Directory -Force -Path $export | Out-Null
    & pnputil.exe /export-driver $bound.InfName $export |
        Tee-Object -FilePath (Join-Path $backup 'EXPORT_ORIGINAL.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not export current audio bus driver.' }
}

Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPublisher' | Out-Null

# Stage package first. Do not rely on PnP ranking to choose a test-signed driver.
& pnputil.exe /add-driver $inf |
    Tee-Object -FilePath (Join-Path $backup 'STAGE_MOD.txt')
if ($LASTEXITCODE -ne 0) { throw "pnputil staging failed: $LASTEXITCODE" }

$rebootRequired = $false
$ok = [P360.NewDev]::UpdateDriverForPlugAndPlayDevices(
    [IntPtr]::Zero,
    $hardwareId,
    $inf,
    $INSTALLFLAG_FORCE,
    [ref]$rebootRequired)

if (-not $ok) {
    $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "Forced driver update failed. Win32=$err. Backup: $backup"
}

"ForceBindHardwareId=$hardwareId" | Set-Content -LiteralPath (Join-Path $backup 'FORCE_BIND.txt') -Encoding UTF8
"RebootRequired=$rebootRequired" | Add-Content -LiteralPath (Join-Path $backup 'FORCE_BIND.txt') -Encoding UTF8

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
    throw "Bus mod did not bind cleanly. Backup/rollback data: $backup"
}

& pnputil.exe /enum-devices /instanceid "$($target.PNPDeviceID)" /relations 2>&1 |
    Set-Content -LiteralPath (Join-Path $backup 'RELATIONS.txt') -Encoding UTF8

Write-Host ''
Write-Host 'PHASER360 BUS MOD: FORCE-BIND COMPLETED'
Write-Host "Parent service: $($after.Service)"
Write-Host "Reboot required: $rebootRequired"
Write-Host "Backup: $backup"
Write-Host 'No DSP firmware boot and no audio playback were attempted.'
