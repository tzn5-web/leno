#requires -version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

function Require-Admin {
  $p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){ throw 'Administrator required.' }
}
Require-Admin

if (-not ('P360.NewDevProbe' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
  public static class NewDevProbe {
    [DllImport("newdev.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool UpdateDriverForPlugAndPlayDevices(
      IntPtr hwndParent, string HardwareId, string FullInfPath,
      uint InstallFlags, out bool RebootRequired);
  }
}
'@
}

$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$inf=(Resolve-Path (Join-Path $root 'P360AdspProbe.inf')).Path
$sys=(Resolve-Path (Join-Path $root 'P360AdspProbe.sys')).Path
$cat=(Resolve-Path (Join-Path $root 'P360AdspProbe.cat')).Path
$cer=(Resolve-Path (Join-Path $root 'P360_ADSP_PROBE_TEST.cer')).Path
$hardwareId='CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198'

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
  throw 'The working SklHDAudBus parent is not healthy. No changes.'
}
$child=Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -like "$hardwareId*" } | Select-Object -First 1
if(-not $child){throw 'Canonical CSAUDIO DSP child not enumerated.'}
if($child.Service -and $child.Service -ne 'P360AdspProbe'){
  throw "DSP child has unexpected service '$($child.Service)'; refusing replacement."
}
if(-not $child.Service -and $child.ConfigManagerErrorCode -ne 28){
  throw "Unexpected unbound DSP state Code $($child.ConfigManagerErrorCode)."
}

$signer=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
foreach($file in @($sys,$cat)){
  $sig=Get-AuthenticodeSignature $file
  if(-not $sig.SignerCertificate -or $sig.SignerCertificate.Thumbprint -ne $signer.Thumbprint) {
    throw "Test signature/certificate mismatch in $file"
  }
}

$beforeDriver=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $child.PNPDeviceID | Select-Object -First 1
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$backup=Join-Path 'C:\P360_AUDIO_SAFE' ("P360_ADSP_IRQ_PROBE_BACKUP_"+$stamp)
New-Item -ItemType Directory -Force $backup | Out-Null
$thumb=$signer.Thumbprint
$hadRoot=[bool](Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)
$hadPublisher=[bool](Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)

@(
 "Parent=$($parent.PNPDeviceID)"
 "Child=$($child.PNPDeviceID)"
 "BeforeService=$($child.Service)"
 "BeforeCode=$($child.ConfigManagerErrorCode)"
 "BeforeInf=$($beforeDriver.InfName)"
 "BeforeVersion=$($beforeDriver.DriverVersion)"
 "Cert=$thumb"
 "HadRoot=$hadRoot"
 "HadPublisher=$hadPublisher"
) | Set-Content (Join-Path $backup 'BASELINE.txt') -Encoding UTF8

if($beforeDriver -and $beforeDriver.InfName){
  $export=Join-Path $backup 'PREVIOUS_DRIVER'
  New-Item -ItemType Directory -Force $export | Out-Null
  & pnputil.exe /export-driver $beforeDriver.InfName $export | Tee-Object -FilePath (Join-Path $backup 'EXPORT_PREVIOUS.txt')
  if($LASTEXITCODE){throw "Could not export previous probe package. No bind attempted. Backup=$backup"}
}

Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
foreach($file in @($sys,$cat)){
  $sig=Get-AuthenticodeSignature $file
  if($sig.Status -ne 'Valid'){throw "Package signature validation failed: $file Status=$($sig.Status). Backup=$backup"}
}

& pnputil.exe /add-driver $inf | Tee-Object -FilePath (Join-Path $backup 'STAGE.txt')
if($LASTEXITCODE){throw "PnPUtil staging failed. Backup=$backup"}

[bool]$reboot=$false
$ok=[P360.NewDevProbe]::UpdateDriverForPlugAndPlayDevices(
  [IntPtr]::Zero,$hardwareId,$inf,[uint32]1,[ref]$reboot)
if(-not $ok){
  $err=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
  throw "Forced probe update failed Win32=$err. Backup=$backup"
}

Start-Sleep -Seconds 2

# Important: v1 and v2 intentionally use the same service name. Windows may
# update the package but keep the old loaded image until the DSP child is
# restarted. Restart ONLY the CSAUDIO DSP child; never restart the parent bus.
if(-not $reboot){
  Write-Host 'Reloading the CSAUDIO DSP child so the v2 binary is actually loaded...'
  & pnputil.exe /restart-device "$($child.PNPDeviceID)" |
    Tee-Object -FilePath (Join-Path $backup 'RESTART_CHILD.txt')
  $restartRc=$LASTEXITCODE
  if($restartRc -ne 0){
    Write-Host "Child restart returned $restartRc; a reboot is required."
    $reboot=$true
  } else {
    Start-Sleep -Seconds 3
  }
}

$after=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $child.PNPDeviceID | Select-Object -First 1
$afterDriver=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $child.PNPDeviceID | Select-Object -First 1
@(
 "AfterService=$($after.Service)"
 "AfterCode=$($after.ConfigManagerErrorCode)"
 "AfterInf=$($afterDriver.InfName)"
 "AfterVersion=$($afterDriver.DriverVersion)"
 "RebootRequired=$reboot"
) | Set-Content (Join-Path $backup 'AFTER.txt') -Encoding UTF8

Write-Host "Backup=$backup"
Write-Host "AfterService=$($after.Service); AfterProblem=$($after.ConfigManagerErrorCode); Version=$($afterDriver.DriverVersion)"
Write-Host "RebootRequired=$reboot"
Write-Host 'This v2 probe registers only a passive callback with the parent ISR.'
Write-Host 'DSP_BOOT=NO; MMIO=NO; IPC=NO; AUDIO=NO'
if($reboot){Write-Host 'REBOOT ONCE before START_QUERY.cmd / START_PASSIVE_IRQ_TEST.cmd.'}
else{Write-Host 'Child reloaded. Run START_QUERY.cmd, then START_PASSIVE_IRQ_TEST.cmd.'}
