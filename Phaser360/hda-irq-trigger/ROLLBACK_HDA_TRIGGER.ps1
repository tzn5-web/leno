#requires -version 5.1
[CmdletBinding()]param([string]$BackupDir)
$ErrorActionPreference='Stop'
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
if(-not $BackupDir){
 $BackupDir=Get-ChildItem C:\P360_AUDIO_SAFE -Directory -Filter P360_HDA_TRIGGER_BACKUP_* |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if(-not $BackupDir){throw 'No HDA trigger backup found.'}
$b=@{}
Get-Content (Join-Path $BackupDir BASELINE.txt) | ForEach-Object {if($_ -match '^([^=]+)=(.*)$'){$b[$matches[1]]=$matches[2]}}
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $b.HdaChild | Select-Object -First 1
if(-not $dev){throw 'HDA child missing.'}
if($dev.Service -eq 'P360HdaIrqTrigger'){
 $drv=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $dev.PNPDeviceID | Select-Object -First 1
 if(-not $drv -or $drv.InfName -notmatch '^oem\d+\.inf$'){throw 'Installed trigger INF not identifiable.'}
 & pnputil /delete-driver $drv.InfName /uninstall | Tee-Object -FilePath (Join-Path $BackupDir ROLLBACK.txt)
 if($LASTEXITCODE){throw 'Driver removal failed; keep certificate until resolved.'}
}
Start-Sleep -Seconds 2
$dev=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $b.HdaChild | Select-Object -First 1
if($dev.Service -eq 'P360HdaIrqTrigger'){throw 'Driver still loaded; reboot before certificate cleanup.'}
if($b.Cert){
 if($b.HadRoot -eq 'False'){Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $b.Cert | Remove-Item -Force -ErrorAction SilentlyContinue}
 if($b.HadPublisher -eq 'False'){Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $b.Cert | Remove-Item -Force -ErrorAction SilentlyContinue}
}
Write-Host "HDA child restored: Service=$($dev.Service) Code=$($dev.ConfigManagerErrorCode)"
Write-Host 'SklHDAudBus and ADSP probe were not removed.'
