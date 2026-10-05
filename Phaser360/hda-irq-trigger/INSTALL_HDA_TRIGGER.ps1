#requires -version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}

$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$inf=(Resolve-Path (Join-Path $root 'P360HdaIrqTrigger.inf')).Path
$sys=(Resolve-Path (Join-Path $root 'P360HdaIrqTrigger.sys')).Path
$cat=(Resolve-Path (Join-Path $root 'P360HdaIrqTrigger.cat')).Path
$cer=(Resolve-Path (Join-Path $root 'P360_HDA_TRIGGER_TEST.cer')).Path

$cs=Get-CimInstance Win32_ComputerSystem
$bb=Get-CimInstance Win32_BaseBoard
$id="$($cs.Manufacturer) $($cs.Model) $($bb.Product)"
if($id -notmatch '(?i)Google' -or $id -notmatch '(?i)(Phaser360|Octopus)'){throw "Wrong machine: $id"}

$parent=Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*'} | Select-Object -First 1
if(-not $parent -or $parent.Service -ne 'SklHDAudBus' -or $parent.ConfigManagerErrorCode -ne 0){
 throw 'SklHDAudBus parent not healthy.'
}

$adsp=Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -like 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198*'} | Select-Object -First 1
if(-not $adsp -or $adsp.Service -ne 'P360AdspProbe' -or $adsp.ConfigManagerErrorCode -ne 0){
 throw 'Passive ADSP IRQ probe v2 must already be loaded and healthy.'
}

$hda=Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -like 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D*'} | Select-Object -First 1
if(-not $hda){throw 'Intel 280D HDA codec child not found.'}
if($hda.Service -and $hda.Service -ne 'P360HdaIrqTrigger'){throw "HDA child already has service $($hda.Service); refusing replacement."}
if(-not $hda.Service -and $hda.ConfigManagerErrorCode -ne 28){throw "Unexpected HDA child state Code $($hda.ConfigManagerErrorCode)."}

$bcd=(& bcdedit /enum "{current}" 2>&1 | Out-String)
if($bcd -notmatch '(?im)^\s*testsigning\s+(Yes|Da|On)\s*$'){throw 'TestSigning not enabled.'}

$cert=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
foreach($file in @($sys,$cat)){
 $sig=Get-AuthenticodeSignature $file
 if(-not $sig.SignerCertificate -or $sig.SignerCertificate.Thumbprint -ne $cert.Thumbprint){throw "Signer mismatch: $file"}
}

$stamp=Get-Date -Format yyyyMMdd_HHmmss
$backup=Join-Path C:\P360_AUDIO_SAFE ("P360_HDA_TRIGGER_BACKUP_"+$stamp)
New-Item -ItemType Directory -Force $backup | Out-Null
$thumb=$cert.Thumbprint
$hadRoot=[bool](Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)
$hadPub=[bool](Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $thumb | Select-Object -First 1)
@(
 "HdaChild=$($hda.PNPDeviceID)"
 "BeforeService=$($hda.Service)"
 "BeforeCode=$($hda.ConfigManagerErrorCode)"
 "Cert=$thumb"
 "HadRoot=$hadRoot"
 "HadPublisher=$hadPub"
) | Set-Content (Join-Path $backup BASELINE.txt) -Encoding UTF8

Import-Certificate $cer Cert:\LocalMachine\Root | Out-Null
Import-Certificate $cer Cert:\LocalMachine\TrustedPublisher | Out-Null
foreach($file in @($sys,$cat)){
 if((Get-AuthenticodeSignature $file).Status -ne 'Valid'){throw "Signature validation failed: $file; Backup=$backup"}
}

& pnputil /add-driver $inf /install | Tee-Object -FilePath (Join-Path $backup INSTALL.txt)
if($LASTEXITCODE){throw "PnPUtil failed $LASTEXITCODE; Backup=$backup"}

Start-Sleep -Seconds 2
$after=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $hda.PNPDeviceID | Select-Object -First 1
Write-Host "HDA_SERVICE=$($after.Service)"
Write-Host "HDA_CODE=$($after.ConfigManagerErrorCode)"
Write-Host "BACKUP=$backup"
Write-Host 'Operation boundary: fixed read-only HDA GET_PARAMETER only; no playback/DSP firmware/IPC.'
