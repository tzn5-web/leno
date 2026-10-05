#requires -version 5.1
[CmdletBinding()]param([string]$BackupDir)
$ErrorActionPreference='Stop'
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}

if(-not ('P360.NewDevProbeRollback' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
  public static class NewDevProbeRollback {
    [DllImport("newdev.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool UpdateDriverForPlugAndPlayDevices(
      IntPtr hwndParent, string HardwareId, string FullInfPath,
      uint InstallFlags, out bool RebootRequired);
  }
}
'@
}

if(-not $BackupDir){
 $BackupDir=Get-ChildItem C:\P360_AUDIO_SAFE -Directory -Filter P360_ADSP_IRQ_PROBE_BACKUP_* |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if(-not $BackupDir){throw 'No passive IRQ probe backup found.'}

$base=@{}
Get-Content (Join-Path $BackupDir 'BASELINE.txt') | ForEach-Object {
 if($_ -match '^([^=]+)=(.*)$'){$base[$matches[1]]=$matches[2]}
}
$hardwareId='CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198'
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $base.Child | Select-Object -First 1
if(-not $dev){throw 'DSP child missing; refusing ambiguous rollback.'}
$current=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $dev.PNPDeviceID | Select-Object -First 1
$currentInf=$current.InfName

if($base.BeforeInf){
  $old=Get-ChildItem (Join-Path $BackupDir 'PREVIOUS_DRIVER') -Recurse -Filter $base.BeforeInf -File | Select-Object -First 1
  if(-not $old){$old=Get-ChildItem (Join-Path $BackupDir 'PREVIOUS_DRIVER') -Recurse -Filter *.inf -File | Select-Object -First 1}
  if(-not $old){throw 'Previous diagnostic INF export missing.'}
  & pnputil.exe /add-driver $old.FullName | Out-Null
  if($LASTEXITCODE){throw 'Could not stage previous diagnostic package.'}
  [bool]$reboot=$false
  $ok=[P360.NewDevProbeRollback]::UpdateDriverForPlugAndPlayDevices(
    [IntPtr]::Zero,$hardwareId,$old.FullName,[uint32]1,[ref]$reboot)
  if(-not $ok){throw "Could not restore previous probe; Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
} else {
  if($currentInf -and $currentInf -match '^oem\d+\.inf$'){
    & pnputil.exe /delete-driver $currentInf /uninstall | Tee-Object -FilePath (Join-Path $BackupDir 'REMOVE_CURRENT.txt')
    if($LASTEXITCODE){throw 'Current probe removal failed.'}
  }
  [bool]$reboot=$false
}

Start-Sleep -Seconds 2
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $base.Child | Select-Object -First 1
if($currentInf -and $base.BeforeInf -and $currentInf -ne $base.BeforeInf){
  & pnputil.exe /delete-driver $currentInf /force 2>&1 | Out-Null
}

if($base.Cert){
 if($base.HadRoot -eq 'False'){Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $base.Cert | Remove-Item -Force -ErrorAction SilentlyContinue}
 if($base.HadPublisher -eq 'False'){Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $base.Cert | Remove-Item -Force -ErrorAction SilentlyContinue}
}
Write-Host "RestoredService=$($dev.Service)"
Write-Host "RestoredCode=$($dev.ConfigManagerErrorCode)"
Write-Host "RebootRequired=$reboot"
Write-Host 'SklHDAudBus parent was not changed.'
