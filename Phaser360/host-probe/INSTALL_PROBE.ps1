#requires -version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
function Require-Admin {
  $p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){ throw 'Administrator required.' }
}
Require-Admin
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$inf=(Resolve-Path (Join-Path $root 'P360AdspProbe.inf')).Path
$sys=(Resolve-Path (Join-Path $root 'P360AdspProbe.sys')).Path
$cat=(Resolve-Path (Join-Path $root 'P360AdspProbe.cat')).Path
$cer=(Resolve-Path (Join-Path $root 'P360_ADSP_PROBE_TEST.cer')).Path
$cs=Get-CimInstance Win32_ComputerSystem
$bb=Get-CimInstance Win32_BaseBoard
$identity="$($cs.Manufacturer) $($cs.Model) $($bb.Product)"
if($identity -notmatch '(?i)Google' -or $identity -notmatch '(?i)(Phaser360|Octopus)'){
  throw "Refusing an unrelated computer: $identity"
}
$bcd=(& bcdedit /enum "{current}" 2>&1 | Out-String)
if($bcd -notmatch '(?im)^\s*testsigning\s+(Yes|Da|On)\s*$'){
  throw 'TestSigning is not enabled; nothing installed.'
}
$parent=Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*' } | Select-Object -First 1
if(-not $parent -or $parent.Service -ne 'SklHDAudBus' -or $parent.ConfigManagerErrorCode -ne 0){
  throw 'The already working SklHDAudBus parent is not healthy. No changes.'
}
$child=Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198*' } | Select-Object -First 1
if(-not $child){throw 'Canonical CSAUDIO DSP child not enumerated.'}
if($child.Service -eq 'P360AdspProbe'){Write-Host 'Probe already installed';exit 0}
if($child.ConfigManagerErrorCode -ne 28){throw "Expected Code 28 before first probe install, got $($child.ConfigManagerErrorCode)."}
$signer=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
foreach($file in @($sys,$cat)){
  $sig=Get-AuthenticodeSignature $file
  if(-not $sig.SignerCertificate -or $sig.SignerCertificate.Thumbprint -ne $signer.Thumbprint) {
    throw "Test signature/certificate mismatch in $file"
  }
}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$backup=Join-Path 'C:\P360_AUDIO_SAFE' ("P360_ADSP_PROBE_BACKUP_"+$stamp)
New-Item -ItemType Directory -Force $backup | Out-Null
$thumb=$signer.Thumbprint
$hadRoot=[bool](Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)
$hadPublisher=[bool](Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)
@("Parent=$($parent.PNPDeviceID)","Child=$($child.PNPDeviceID)","BeforeCode=$($child.ConfigManagerErrorCode)","Cert=$thumb","HadRoot=$hadRoot","HadPublisher=$hadPublisher") |
  Set-Content (Join-Path $backup 'BASELINE.txt') -Encoding UTF8
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
foreach($file in @($sys,$cat)){
  $sig=Get-AuthenticodeSignature $file
  if($sig.Status -ne 'Valid'){throw "Package signature validation failed: $file Status=$($sig.Status). Backup=$backup"}
}
& pnputil.exe /add-driver $inf /install | Tee-Object -FilePath (Join-Path $backup 'PNPUTIL_INSTALL.txt')
$rc=$LASTEXITCODE
$after=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $child.PNPDeviceID | Select-Object -First 1
@("PnPUtilExit=$rc","AfterService=$($after.Service)","AfterCode=$($after.ConfigManagerErrorCode)") | Set-Content (Join-Path $backup 'AFTER.txt')
Write-Host "Backup=$backup"
if($rc -ne 0){throw "PnPUtil returned $rc; review backup and use rollback if required."}
Write-Host "AfterService=$($after.Service); AfterProblem=$($after.ConfigManagerErrorCode)"
Write-Host 'No firmware, MMIO, IRQ registration, IPC, audio endpoint or playback is performed by this probe.'
Write-Host 'Run QUERY_PROBE.ps1 (or START_QUERY.cmd); if the new driver is pending, reboot once.'
