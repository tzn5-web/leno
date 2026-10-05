#requires -version 5.1
[CmdletBinding()]param([string]$BackupDir)
$ErrorActionPreference='Stop'
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
if(-not $BackupDir){
 $BackupDir=Get-ChildItem C:\P360_AUDIO_SAFE -Directory -Filter P360_ADSP_PROBE_BACKUP_* |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if(-not $BackupDir){throw 'No probe install backup found.'}
$base=@{}
Get-Content (Join-Path $BackupDir 'BASELINE.txt') | ForEach-Object {if($_ -match '^([^=]+)=(.*)$'){$base[$matches[1]]=$matches[2]}}
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $base.Child | Select-Object -First 1
if(-not $dev){throw 'DSP child missing; do not remove certificates before restoring the device.'}
if($dev.Service -eq 'P360AdspProbe'){
 $signed=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $dev.PNPDeviceID | Select-Object -First 1
 if(-not $signed -or $signed.InfName -notmatch '^oem\d+\.inf$'){throw 'Current probe INF unknown; refusing blind driver removal.'}
 & pnputil.exe /delete-driver $signed.InfName /uninstall | Tee-Object -FilePath (Join-Path $BackupDir 'ROLLBACK.txt')
 if($LASTEXITCODE){throw 'Probe INF removal failed; certificate must remain trusted until resolved.'}
}
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $base.Child | Select-Object -First 1
if($dev.Service -eq 'P360AdspProbe'){throw 'Probe still loaded. Reboot before certificate cleanup.'}
if($base.Cert){
 if($base.HadRoot -eq 'False'){Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $base.Cert | Remove-Item -Force}
 if($base.HadPublisher -eq 'False'){Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $base.Cert | Remove-Item -Force}
}
Write-Host "DSP child: $($dev.Status), Code $($dev.ConfigManagerErrorCode), Service $($dev.Service)"
Write-Host 'Probe rollback complete; SklHDAudBus parent was not changed.'
