#requires -version 5.1
[CmdletBinding()]
param(
    [string]$BackupDir
)
$ErrorActionPreference = 'Stop'

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
$origInf  = $baseline['BeforeInf']

$current = Get-CimInstance Win32_PnPSignedDriver |
    Where-Object { $_.DeviceID -eq $instance } |
    Select-Object -First 1

if ($current -and $current.InfName -and $current.InfName -ne $origInf) {
    & pnputil.exe /delete-driver $current.InfName /uninstall /force
}

$exportRoot = Join-Path $BackupDir 'ORIGINAL_DRIVER'
$infPath = Get-ChildItem $exportRoot -Recurse -Filter $origInf -File | Select-Object -First 1
if (-not $infPath) {
    $infPath = Get-ChildItem $exportRoot -Recurse -Filter '*.inf' -File | Select-Object -First 1
}
if (-not $infPath) { throw 'Original exported INF not found.' }

& pnputil.exe /add-driver $infPath.FullName /install
if ($LASTEXITCODE -ne 0) { throw 'Original driver restore failed.' }

& pnputil.exe /restart-device "$instance"
Start-Sleep -Seconds 3

$dev = Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -eq $instance } | Select-Object -First 1
Write-Host "Restored service: $($dev.Service)"
Write-Host "Status: $($dev.Status) Problem=$($dev.ConfigManagerErrorCode)"
