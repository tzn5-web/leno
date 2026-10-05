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

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$inf  = Join-Path $root 'sklhdaudbus.inf'
$cer  = Join-Path $root 'PHASER360_TEST_DRIVER.cer'
if (!(Test-Path $inf)) { throw "Missing $inf" }
if (!(Test-Path $cer)) { throw "Missing $cer" }

$target = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*' } |
    Select-Object -First 1
if (-not $target) { throw 'PCI 8086:3198 is not enumerated. Stop.' }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "C:\P360_AUDIO_SAFE\P360_BUS_MOD_BACKUP_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$bound = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1

@(
    "InstanceId=$($target.PNPDeviceID)"
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

& pnputil.exe /add-driver $inf /install |
    Tee-Object -FilePath (Join-Path $backup 'INSTALL.txt')
if ($LASTEXITCODE -ne 0) { throw "pnputil install failed: $LASTEXITCODE" }

Start-Sleep -Seconds 2
$after = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -eq $target.PNPDeviceID } |
    Select-Object -First 1

if ($after.Service -ne 'SklHDAudBus') {
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
) | Set-Content -LiteralPath (Join-Path $backup 'AFTER.txt') -Encoding UTF8

if ($after.Service -ne 'SklHDAudBus' -or [int]$after.ConfigManagerErrorCode -ne 0) {
    throw "Bus mod did not bind cleanly. Backup/rollback data: $backup"
}

$children = & pnputil.exe /enum-devices /instanceid "$($target.PNPDeviceID)" /relations 2>&1
$children | Set-Content -LiteralPath (Join-Path $backup 'RELATIONS.txt') -Encoding UTF8

Write-Host ''
Write-Host 'PHASER360 BUS MOD: BOUND'
Write-Host "Parent service: $($after.Service)"
Write-Host "Backup: $backup"
Write-Host 'No audio playback was attempted.'
Write-Host 'Run VERIFY_P360_BUS_MOD.ps1 next.'
