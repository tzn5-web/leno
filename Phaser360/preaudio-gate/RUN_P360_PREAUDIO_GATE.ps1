#requires -version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

function Admin {
  $p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function W([string]$s){Write-Host $s; Add-Content -LiteralPath $script:Log -Value $s -Encoding UTF8}
function KV([string]$k,[object]$v){$script:Report.Add("$k=$v")|Out-Null}
function Safe([scriptblock]$b){try{& $b}catch{return $null}}
function FindDev([string]$prefix){
  Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
   Where-Object {$_.PNPDeviceID -like "$prefix*"} | Select-Object -First 1
}

if(-not (Admin)){throw 'Administrator required.'}

if(-not ('P360.Native' -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
 public static class Native {
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
  public static extern IntPtr CreateFile(string name,uint access,uint share,IntPtr sec,uint disposition,uint flags,IntPtr template);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool DeviceIoControl(IntPtr h,uint ctl,IntPtr input,uint inlen,[Out] byte[] output,uint outlen,out uint written,IntPtr overlapped);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool CloseHandle(IntPtr h);
 }
 public static class NewDev {
  [DllImport("newdev.dll",SetLastError=true,CharSet=CharSet.Unicode)]
  public static extern bool UpdateDriverForPlugAndPlayDevices(IntPtr hwnd,string hardwareId,string inf,uint flags,out bool reboot);
 }
}
'@
}

function Ioctl([string]$path,[uint32]$code,[int]$size){
  $h=[P360.Native]::CreateFile($path,[uint32]2147483648,0,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
  if($h -eq [IntPtr](-1)){throw "CreateFile $path failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
  try{
    $b=New-Object byte[] $size
    [uint32]$n=0
    $ok=[P360.Native]::DeviceIoControl($h,$code,[IntPtr]::Zero,0,$b,[uint32]$size,[ref]$n,[IntPtr]::Zero)
    if(-not $ok){throw "DeviceIoControl 0x$('{0:X8}' -f $code) failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
    [pscustomobject]@{Bytes=$b;Written=$n}
  } finally {[void][P360.Native]::CloseHandle($h)}
}

function Read-DspProbe {
  $r=Ioctl '\\.\P360AdspProbe' ([uint32]0x226004) 48
  if($r.Written -ne 48){throw "DSP probe response is $($r.Written) bytes, expected v2=48"}
  $b=$r.Bytes
  if([BitConverter]::ToUInt32($b,0) -ne 0x50333630){throw 'DSP probe magic mismatch'}
  [pscustomobject]@{
   Version=[BitConverter]::ToUInt32($b,4)
   Query=[BitConverter]::ToUInt32($b,8)
   Register=[BitConverter]::ToUInt32($b,12)
   Flags=[BitConverter]::ToUInt32($b,16)
   Controller=[BitConverter]::ToUInt16($b,20)
   InterfaceVersion=[BitConverter]::ToUInt16($b,22)
   InterfaceSize=[BitConverter]::ToUInt32($b,24)
   Irq=[BitConverter]::ToInt64($b,32)
  }
}

function Read-Hda([bool]$trigger){
  $code=if($trigger){[uint32]0x22E088}else{[uint32]0x226084}
  $r=Ioctl '\\.\P360HdaReadProbe' $code 56
  if($r.Written -ne 56){throw "HDA probe response is $($r.Written) bytes, expected 56"}
  $b=$r.Bytes
  if([BitConverter]::ToUInt32($b,0) -ne 0x48333630){throw 'HDA probe magic mismatch'}
  [pscustomobject]@{
    Version=[BitConverter]::ToUInt32($b,4)
    Query=[BitConverter]::ToUInt32($b,8)
    Transfer=[BitConverter]::ToUInt32($b,12)
    Flags=[BitConverter]::ToUInt32($b,16)
    CodecAddress=$b[20]
    FunctionGroup=$b[21]
    InterfaceVersion=[BitConverter]::ToUInt16($b,22)
    InterfaceSize=[BitConverter]::ToUInt32($b,24)
    Command=[BitConverter]::ToUInt32($b,28)
    CompleteResponse=[BitConverter]::ToUInt64($b,32)
    Response=[BitConverter]::ToUInt32($b,40)
    Valid=[BitConverter]::ToUInt32($b,44)
    Overrun=[BitConverter]::ToUInt32($b,48)
  }
}

$stamp=Get-Date -Format yyyyMMdd_HHmmss
$root='C:\P360_AUDIO_SAFE'
$script:Out=Join-Path $root ("P360_PREAUDIO_GATE_"+$stamp)
New-Item -ItemType Directory -Force -Path $script:Out | Out-Null
$script:Log=Join-Path $script:Out 'RUN.log'
$script:Report=New-Object 'System.Collections.Generic.List[string]'
$script:CleanupNeeded=$false
$script:HdaInfName=$null
$script:CertThumb=$null
$script:HadRoot=$false
$script:HadPublisher=$false
$script:HdaChildId=$null

W '=== PHASER360 PRE-AUDIO GATE ==='
W 'NO SOF BOOT / NO DSP MMIO / NO IPC / NO STREAM / NO CODEC WRITE / NO AUDIO'

$package=Split-Path -Parent $MyInvocation.MyCommand.Path
$inf=(Resolve-Path (Join-Path $package 'P360HdaReadProbe.inf')).Path
$sys=(Resolve-Path (Join-Path $package 'P360HdaReadProbe.sys')).Path
$cat=(Resolve-Path (Join-Path $package 'P360HdaReadProbe.cat')).Path
$cer=(Resolve-Path (Join-Path $package 'P360_PREAUDIO_TEST.cer')).Path

try {
  # G0 target / boot policy
  $cs=Get-CimInstance Win32_ComputerSystem
  $bb=Get-CimInstance Win32_BaseBoard
  $identity="$($cs.Manufacturer) $($cs.Model) $($bb.Product)"
  KV 'IDENTITY' $identity
  if($identity -notmatch '(?i)Google' -or $identity -notmatch '(?i)(Phaser360|Octopus)'){
    throw "G0_TARGET_FAIL: unexpected machine '$identity'"
  }
  $bcd=(& bcdedit /enum "{current}" 2>&1 | Out-String)
  $testSigning=[bool]($bcd -match '(?im)^\s*testsigning\s+(Yes|Da|On)\s*$')
  KV 'TESTSIGNING' $testSigning
  if(-not $testSigning){throw 'G0_TESTSIGNING_FAIL'}
  W '[OK] G0 target + TestSigning'

  # G1 parent bus
  $parent=FindDev 'PCI\VEN_8086&DEV_3198'
  if(-not $parent){throw 'G1_PARENT_MISSING: PCI 8086:3198'}
  KV 'PARENT_SERVICE' $parent.Service
  KV 'PARENT_STATUS' $parent.Status
  KV 'PARENT_CODE' $parent.ConfigManagerErrorCode
  if($parent.Service -ne 'SklHDAudBus' -or $parent.ConfigManagerErrorCode -ne 0){
    throw "G1_PARENT_BAD: service=$($parent.Service) code=$($parent.ConfigManagerErrorCode)"
  }
  W '[OK] G1 SklHDAudBus parent healthy'

  # G2 DSP child and passive callback probe
  $dsp=FindDev 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198'
  if(-not $dsp){throw 'G2_DSP_CHILD_MISSING'}
  KV 'DSP_SERVICE' $dsp.Service
  KV 'DSP_CODE' $dsp.ConfigManagerErrorCode
  if($dsp.Service -ne 'P360AdspProbe' -or $dsp.ConfigManagerErrorCode -ne 0){
    throw "G2_DSP_PROBE_NOT_READY: service=$($dsp.Service) code=$($dsp.ConfigManagerErrorCode)"
  }
  $ds0=Read-DspProbe
  KV 'DSP_PROBE_VERSION' $ds0.Version
  KV 'DSP_QUERY_STATUS' ('0x{0:X8}' -f $ds0.Query)
  KV 'DSP_IRQ_REGISTER_STATUS' ('0x{0:X8}' -f $ds0.Register)
  KV 'DSP_IRQ_CALLBACK_REGISTERED' ([bool]($ds0.Flags -band 8))
  KV 'DSP_IRQ_INITIAL_COUNT' $ds0.Irq
  if($ds0.Version -ne 2 -or $ds0.Query -ne 0 -or $ds0.Register -ne 0 -or (($ds0.Flags -band 8) -eq 0)){
    throw 'G2_DSP_PROBE_FAIL'
  }
  W "[OK] G2 DSP probe v2 + IRQ callback registered; idle count=$($ds0.Irq)"

  # G3 current audio topology snapshot
  $da=FindDev 'ACPI\DLGS7219'
  $mx=FindDev 'ACPI\MX98357A'
  KV 'DA7219_STATUS' $(if($da){"$($da.Status)/$($da.ConfigManagerErrorCode)/$($da.Service)"}else{'ABSENT'})
  KV 'MAX98357A_STATUS' $(if($mx){"$($mx.Status)/$($mx.ConfigManagerErrorCode)/$($mx.Service)"}else{'ABSENT'})
  $eps=@(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object {$_.ClassGuid -eq '{c166523c-fe0c-4a94-a586-f1a80cfbbf3e}' -and $_.Status -eq 'OK'})
  KV 'ACTIVE_AUDIO_ENDPOINTS_BEFORE' $eps.Count

  # G4 HDA HDMI child must be unbound; we use it as a safe read-only interrupt source.
  $hda=FindDev 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'
  if(-not $hda){throw 'G4_HDA_CHILD_MISSING'}
  $script:HdaChildId=$hda.PNPDeviceID
  KV 'HDA_BEFORE_SERVICE' $hda.Service
  KV 'HDA_BEFORE_CODE' $hda.ConfigManagerErrorCode
  if($hda.Service){
    throw "G4_HDA_CHILD_ALREADY_BOUND: service=$($hda.Service). Refusing replacement."
  }
  if($hda.ConfigManagerErrorCode -ne 28){
    throw "G4_HDA_UNEXPECTED_STATE: code=$($hda.ConfigManagerErrorCode)"
  }

  # Signer/certificate validation
  $signer=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
  $script:CertThumb=$signer.Thumbprint
  foreach($file in @($sys,$cat)){
    $sig=Get-AuthenticodeSignature $file
    if(-not $sig.SignerCertificate -or $sig.SignerCertificate.Thumbprint -ne $signer.Thumbprint){
      throw "G4_PACKAGE_SIGNER_MISMATCH: $file"
    }
  }
  $script:HadRoot=[bool](Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $script:CertThumb | Select-Object -First 1)
  $script:HadPublisher=[bool](Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $script:CertThumb | Select-Object -First 1)
  Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
  Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
  foreach($file in @($sys,$cat)){
    $sig=Get-AuthenticodeSignature $file
    if($sig.Status -ne 'Valid'){throw "G4_SIGNATURE_NOT_VALID_AFTER_TRUST: $file -> $($sig.Status)"}
  }

  & pnputil.exe /add-driver $inf | Tee-Object -FilePath (Join-Path $script:Out 'HDA_STAGE.txt')
  if($LASTEXITCODE){throw "G4_STAGE_FAIL rc=$LASTEXITCODE"}

  [bool]$reboot=$false
  $ok=[P360.NewDev]::UpdateDriverForPlugAndPlayDevices([IntPtr]::Zero,'HDAUDIO\FUNC_01&VEN_8086&DEV_280D',$inf,[uint32]1,[ref]$reboot)
  if(-not $ok){throw "G4_BIND_FAIL Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
  if($reboot){throw 'G4_BIND_REQUESTED_REBOOT: refusing to continue active test before reboot'}

  Start-Sleep -Seconds 2
  $hda=Get-CimInstance Win32_PnPEntity | Where-Object PNPDeviceID -eq $script:HdaChildId | Select-Object -First 1
  $bound=Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceID -eq $script:HdaChildId | Select-Object -First 1
  $script:HdaInfName=$bound.InfName
  $script:CleanupNeeded=$true
  KV 'HDA_PROBE_INF' $script:HdaInfName
  KV 'HDA_PROBE_SERVICE' $hda.Service
  KV 'HDA_PROBE_CODE' $hda.ConfigManagerErrorCode
  if($hda.Service -ne 'P360HdaReadProbe' -or $hda.ConfigManagerErrorCode -ne 0){
    throw "G4_HDA_PROBE_START_FAIL: service=$($hda.Service) code=$($hda.ConfigManagerErrorCode)"
  }
  W '[OK] G4 temporary HDA read-only probe bound'

  # G5 HDA bus interface
  $hs=Read-Hda $false
  KV 'HDA_QUERY_STATUS' ('0x{0:X8}' -f $hs.Query)
  KV 'HDA_CODEC_ADDRESS' $hs.CodecAddress
  KV 'HDA_FUNCTION_GROUP' $hs.FunctionGroup
  KV 'HDA_INTERFACE_VERSION' ('0x{0:X4}' -f $hs.InterfaceVersion)
  KV 'HDA_INTERFACE_SIZE' $hs.InterfaceSize
  if($hs.Query -ne 0 -or (($hs.Flags -band 1) -eq 0)){
    throw 'G5_HDA_BUS_INTERFACE_FAIL'
  }
  W "[OK] G5 HDA bus interface addr=$($hs.CodecAddress) fg=$($hs.FunctionGroup)"

  # G6 Active IRQ proof using exactly three read-only GET_PARAMETER(VENDOR_ID) verbs.
  $totalDelta=[int64]0
  $validReads=0
  $vendorExpected=0x8086280D
  for($i=1;$i -le 3;$i++){
    $before=Read-DspProbe
    $hr=Read-Hda $true
    Start-Sleep -Milliseconds 100
    $after=Read-DspProbe
    $delta=$after.Irq-$before.Irq
    $totalDelta+=$delta
    if($hr.Transfer -eq 0 -and $hr.Valid -eq 1){$validReads++}

    W ("[G6.{0}] transfer=0x{1:X8} response=0x{2:X8} valid={3} overrun={4} IRQ {5}->{6} delta={7}" -f
      $i,$hr.Transfer,$hr.Response,$hr.Valid,$hr.Overrun,$before.Irq,$after.Irq,$delta)

    [pscustomobject]@{
      Iteration=$i
      TransferStatus=('0x{0:X8}' -f $hr.Transfer)
      Command=('0x{0:X8}' -f $hr.Command)
      Response=('0x{0:X8}' -f $hr.Response)
      Valid=$hr.Valid
      FifoOverrun=$hr.Overrun
      IrqBefore=$before.Irq
      IrqAfter=$after.Irq
      IrqDelta=$delta
    } | Export-Csv -LiteralPath (Join-Path $script:Out 'ACTIVE_IRQ_READS.csv') -NoTypeInformation -Append -Encoding UTF8
  }
  KV 'HDA_VALID_READS' $validReads
  KV 'ACTIVE_IRQ_DELTA_TOTAL' $totalDelta
  KV 'ACTIVE_IRQ_PROVED' ($validReads -ge 1 -and $totalDelta -gt 0)
  KV 'HDA_EXPECTED_VENDOR_DEVICE' ('0x{0:X8}' -f $vendorExpected)
  KV 'HDA_LAST_VENDOR_DEVICE' ('0x{0:X8}' -f $hr.Response)

  if($validReads -lt 1){
    throw 'G6_HDA_READ_FAILED: no valid RIRB response'
  }
  if($totalDelta -le 0){
    throw 'G6_IRQ_CALLBACK_NOT_OBSERVED_DURING_CONFIRMED_HDA_TRANSFER'
  }
  W "[OK] G6 ACTIVE IRQ PROVED: validReads=$validReads totalDelta=$totalDelta"

  # G7 collect next-stage prerequisites; no writes.
  $sofFiles=@()
  foreach($base in @('D:\PHASER360_WORK','C:\Windows\System32\drivers')){
    if(Test-Path $base){
      $sofFiles+=Get-ChildItem $base -Recurse -File -ErrorAction SilentlyContinue |
       Where-Object {$_.Name -match '(?i)sof.*\.(ri|tplg)$|.*\.tplg$'} |
       Select-Object FullName,Length,LastWriteTime
    }
  }
  $sofFiles | Export-Csv -LiteralPath (Join-Path $script:Out 'SOF_FIRMWARE_TOPOLOGY_FILES.csv') -NoTypeInformation -Encoding UTF8
  KV 'SOF_FIRMWARE_TOPOLOGY_FILES' $sofFiles.Count

  $sofSvc=@(Get-CimInstance Win32_SystemDriver -ErrorAction SilentlyContinue |
    Where-Object {$_.Name -match '(?i)^(csaudiointcsof|P360Sof|P360.*Sof)$'})
  KV 'SOF_HOST_SERVICES' $sofSvc.Count

  $da2=FindDev 'ACPI\DLGS7219'
  $mx2=FindDev 'ACPI\MX98357A'
  KV 'DA7219_DRIVER_BOUND' ([bool]($da2 -and $da2.Service -and $da2.ConfigManagerErrorCode -eq 0))
  KV 'MAX98357A_DRIVER_BOUND' ([bool]($mx2 -and $mx2.Service -and $mx2.ConfigManagerErrorCode -eq 0))

  $eps2=@(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object {$_.ClassGuid -eq '{c166523c-fe0c-4a94-a586-f1a80cfbbf3e}' -and $_.Status -eq 'OK'})
  KV 'ACTIVE_AUDIO_ENDPOINTS_AFTER' $eps2.Count

  # It is deliberately impossible to PASS audio readiness without SOF/codec/endpoints.
  $audioReady=($sofSvc.Count -gt 0 -and $da2 -and $da2.Service -and $da2.ConfigManagerErrorCode -eq 0 -and
               $mx2 -and $mx2.Service -and $mx2.ConfigManagerErrorCode -eq 0 -and $eps2.Count -gt 0)
  KV 'AUDIO_READY' $audioReady
  if($audioReady){
    KV 'FINAL_GATE' 'AUDIO_STACK_PRESENT__VOLUME_GUARD_REQUIRED_BEFORE_PLAYBACK'
  } else {
    KV 'FINAL_GATE' 'IRQ_PROVED__AUDIO_BLOCKED_BY_MISSING_SOF_CODEC_ENDPOINT_STACK'
  }

} catch {
  KV 'FINAL_GATE' 'FAIL'
  KV 'FAILURE' $_.Exception.Message
  W "[FAIL] $($_.Exception.Message)"
} finally {
  # Always remove our temporary HDA probe; never touch SklHDAudBus or DSP probe.
  if($script:CleanupNeeded -and $script:HdaInfName -match '^oem\d+\.inf$'){
    W "[CLEANUP] removing temporary HDA probe $script:HdaInfName"
    & pnputil.exe /delete-driver $script:HdaInfName /uninstall /force |
      Tee-Object -FilePath (Join-Path $script:Out 'HDA_CLEANUP.txt')
    KV 'HDA_CLEANUP_RC' $LASTEXITCODE
    Start-Sleep -Seconds 2
  }
  if($script:CertThumb){
    if(-not $script:HadRoot){
      Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $script:CertThumb | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    if(-not $script:HadPublisher){
      Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object Thumbprint -eq $script:CertThumb | Remove-Item -Force -ErrorAction SilentlyContinue
    }
  }

  $p2=FindDev 'PCI\VEN_8086&DEV_3198'
  $h2=FindDev 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'
  $d2=FindDev 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198'
  KV 'POST_PARENT' $(if($p2){"$($p2.Status)/$($p2.ConfigManagerErrorCode)/$($p2.Service)"}else{'ABSENT'})
  KV 'POST_HDA' $(if($h2){"$($h2.Status)/$($h2.ConfigManagerErrorCode)/$($h2.Service)"}else{'ABSENT'})
  KV 'POST_DSP' $(if($d2){"$($d2.Status)/$($d2.ConfigManagerErrorCode)/$($d2.Service)"}else{'ABSENT'})

  $report=Join-Path $script:Out 'REPORT.txt'
  $script:Report | Set-Content -LiteralPath $report -Encoding UTF8
  Write-Host ''
  Write-Host '================ REPORT ================'
  Get-Content $report | ForEach-Object {Write-Host $_}

  $desktop=[Environment]::GetFolderPath('Desktop')
  $zip=Join-Path $desktop ("P360_PREAUDIO_GATE_"+$stamp+".zip")
  Compress-Archive -Path (Join-Path $script:Out '*') -DestinationPath $zip -Force
  Write-Host "ZIP=$zip"
  Write-Host 'AUDIO_PLAYBACK=NO'
}
