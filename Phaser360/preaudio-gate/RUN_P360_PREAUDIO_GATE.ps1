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
function KV([string]$k,[object]$v){$script:ReportLines.Add("$k=$v")|Out-Null}
function FindDev([string]$prefix){
  Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
    Where-Object {$_.PNPDeviceID -like "$prefix*"} | Select-Object -First 1
}
function FindSignedDriver([string]$instanceId){
  Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue |
    Where-Object {$_.DeviceID -eq $instanceId} | Select-Object -First 1
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
  } finally {
    [void][P360.Native]::CloseHandle($h)
  }
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
  if($trigger){$code=[uint32]0x22E088}else{$code=[uint32]0x226084}
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

function Get-HardwareId([string]$instanceId){
  try {
    $ids=@((Get-PnpDeviceProperty -InstanceId $instanceId -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction Stop).Data)
    $id=$ids | Where-Object {$_ -ieq 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'} | Select-Object -First 1
    if(-not $id){
      $id=$ids | Where-Object {$_ -like 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D*'} | Select-Object -First 1
    }
    if($id){return [string]$id}
  } catch {}
  return 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'
}

function Restore-HdaBaseline {
  $restoreOk=$false
  $restoreReason=''
  try {
    if(-not $script:HdaChildId){
      return [pscustomobject]@{Ok=$true;Reason='No HDA child was modified'}
    }

    $cur=Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
      Where-Object {$_.PNPDeviceID -eq $script:HdaChildId} | Select-Object -First 1

    if($script:OriginalHdaService -eq 'IntcDAud'){
      if($cur -and $cur.Service -eq 'IntcDAud' -and $cur.ConfigManagerErrorCode -eq 0){
        $restoreOk=$true
        $restoreReason='IntcDAud already active'
      } else {
        if(-not $script:OriginalExportDir -or !(Test-Path $script:OriginalExportDir)){
          throw 'Original IntcDAud export directory missing'
        }
        $origInf=Get-ChildItem $script:OriginalExportDir -Recurse -Filter '*.inf' -File |
          Select-Object -First 1
        if(-not $origInf){throw 'Exported original IntcDAud INF not found'}

        W "[ROLLBACK] staging original Intel Display Audio INF: $($origInf.FullName)"
        & pnputil.exe /add-driver $origInf.FullName |
          Tee-Object -FilePath (Join-Path $script:Out 'HDA_RESTORE_STAGE.txt')
        if($LASTEXITCODE){throw "Original INF staging failed rc=$LASTEXITCODE"}

        [bool]$restoreReboot=$false
        $ok=[P360.NewDev]::UpdateDriverForPlugAndPlayDevices(
          [IntPtr]::Zero,$script:HdaHardwareId,$origInf.FullName,[uint32]1,[ref]$restoreReboot)
        if(-not $ok){
          throw "Original IntcDAud force-restore failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }
        if($restoreReboot){
          throw 'Original IntcDAud restore requested reboot; do not remove trust/package before reboot'
        }

        Start-Sleep -Seconds 3
        $cur=Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
          Where-Object {$_.PNPDeviceID -eq $script:HdaChildId} | Select-Object -First 1
        if(-not $cur -or $cur.Service -ne 'IntcDAud' -or $cur.ConfigManagerErrorCode -ne 0){
          throw "Original IntcDAud did not return cleanly: service=$($cur.Service) code=$($cur.ConfigManagerErrorCode)"
        }

        $restoredSigned=FindSignedDriver $script:HdaChildId
        KV 'HDA_RESTORED_INF' $restoredSigned.InfName
        KV 'HDA_RESTORED_VERSION' $restoredSigned.DriverVersion
        $restoreOk=$true
        $restoreReason='Original IntcDAud restored'
      }
    } elseif($script:OriginalHdaService -eq ''){
      if($script:ProbeInfName -and $script:ProbeInfName -match '^oem\d+\.inf$'){
        W "[ROLLBACK] uninstalling temporary HDA probe $script:ProbeInfName"
        & pnputil.exe /delete-driver $script:ProbeInfName /uninstall /force |
          Tee-Object -FilePath (Join-Path $script:Out 'HDA_REMOVE_PROBE.txt')
        if($LASTEXITCODE){throw "Probe uninstall failed rc=$LASTEXITCODE"}
        Start-Sleep -Seconds 2
      }
      $cur=Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
        Where-Object {$_.PNPDeviceID -eq $script:HdaChildId} | Select-Object -First 1
      if($cur -and -not $cur.Service -and $cur.ConfigManagerErrorCode -eq 28){
        $restoreOk=$true
        $restoreReason='Original unbound Code 28 state restored'
      } else {
        throw "Unbound baseline not restored: service=$($cur.Service) code=$($cur.ConfigManagerErrorCode)"
      }
    } else {
      throw "Unsupported original HDA service '$($script:OriginalHdaService)'"
    }
  } catch {
    $restoreReason=$_.Exception.Message
  }
  return [pscustomobject]@{Ok=$restoreOk;Reason=$restoreReason}
}

$stamp=Get-Date -Format yyyyMMdd_HHmmss
$root='C:\P360_AUDIO_SAFE'
$script:Out=Join-Path $root ("P360_PREAUDIO_GATE_"+$stamp)
New-Item -ItemType Directory -Force -Path $script:Out | Out-Null
$script:Log=Join-Path $script:Out 'RUN.log'
$script:ReportLines=New-Object 'System.Collections.Generic.List[string]'
$script:ExitCode=0
$script:HdaChildId=$null
$script:HdaHardwareId=$null
$script:OriginalHdaService=$null
$script:OriginalHdaInfName=$null
$script:OriginalHdaVersion=$null
$script:OriginalHdaProvider=$null
$script:OriginalExportDir=$null
$script:ProbeInfName=$null
$script:ProbeBindAttempted=$false
$script:CertThumb=$null
$script:HadRoot=$false
$script:HadPublisher=$false
$script:RestoreSucceeded=$true

W '=== PHASER360 PRE-AUDIO GATE V2 ==='
W 'NO SOF BOOT / NO DSP MMIO / NO IPC / NO STREAM / NO CODEC WRITE / NO AUDIO'
W 'HDA child may be temporarily switched from IntcDAud to a read-only probe, then restored.'

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

  # G2 DSP child / passive callback probe
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

  # G3 topology snapshot
  $da=FindDev 'ACPI\DLGS7219'
  $mx=FindDev 'ACPI\MX98357A'
  if($da){KV 'DA7219_STATUS' "$($da.Status)/$($da.ConfigManagerErrorCode)/$($da.Service)"}else{KV 'DA7219_STATUS' 'ABSENT'}
  if($mx){KV 'MAX98357A_STATUS' "$($mx.Status)/$($mx.ConfigManagerErrorCode)/$($mx.Service)"}else{KV 'MAX98357A_STATUS' 'ABSENT'}
  $eps=@(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
    Where-Object {$_.ClassGuid -eq '{c166523c-fe0c-4a94-a586-f1a80cfbbf3e}' -and $_.Status -eq 'OK'})
  KV 'ACTIVE_AUDIO_ENDPOINTS_BEFORE' $eps.Count

  # G4 HDA graphics child. IntcDAud is an allowed baseline and is preserved.
  $hda=FindDev 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'
  if(-not $hda){throw 'G4_HDA_CHILD_MISSING'}
  $script:HdaChildId=$hda.PNPDeviceID
  $script:HdaHardwareId=Get-HardwareId $hda.PNPDeviceID
  $script:OriginalHdaService=[string]$hda.Service

  $origSigned=FindSignedDriver $hda.PNPDeviceID
  if($origSigned){
    $script:OriginalHdaInfName=[string]$origSigned.InfName
    $script:OriginalHdaVersion=[string]$origSigned.DriverVersion
    $script:OriginalHdaProvider=[string]$origSigned.DriverProviderName
  }

  KV 'HDA_INSTANCE' $script:HdaChildId
  KV 'HDA_HARDWARE_ID' $script:HdaHardwareId
  KV 'HDA_BEFORE_SERVICE' $script:OriginalHdaService
  KV 'HDA_BEFORE_CODE' $hda.ConfigManagerErrorCode
  KV 'HDA_BEFORE_INF' $script:OriginalHdaInfName
  KV 'HDA_BEFORE_VERSION' $script:OriginalHdaVersion
  KV 'HDA_BEFORE_PROVIDER' $script:OriginalHdaProvider

  if($script:OriginalHdaService -eq 'IntcDAud'){
    if($hda.ConfigManagerErrorCode -ne 0){throw "G4_INTCSERVICE_BAD: Code $($hda.ConfigManagerErrorCode)"}
    if(-not $script:OriginalHdaInfName){throw 'G4_INTCSERVICE_INF_UNKNOWN'}

    $script:OriginalExportDir=Join-Path $script:Out 'ORIGINAL_INTCD_AUD'
    New-Item -ItemType Directory -Force -Path $script:OriginalExportDir | Out-Null
    W "[G4] exporting current Intel Display Audio package $($script:OriginalHdaInfName)"
    & pnputil.exe /export-driver $script:OriginalHdaInfName $script:OriginalExportDir |
      Tee-Object -FilePath (Join-Path $script:Out 'HDA_EXPORT_ORIGINAL.txt')
    if($LASTEXITCODE){throw "G4_INTCD_EXPORT_FAIL rc=$LASTEXITCODE"}
    if(-not (Get-ChildItem $script:OriginalExportDir -Recurse -Filter '*.inf' -File | Select-Object -First 1)){
      throw 'G4_INTCD_EXPORT_EMPTY'
    }
    KV 'HDA_ORIGINAL_EXPORTED' $true
    W '[OK] G4 baseline IntcDAud captured for exact rollback'
  } elseif(-not $script:OriginalHdaService -and $hda.ConfigManagerErrorCode -eq 28){
    KV 'HDA_ORIGINAL_EXPORTED' $false
    W '[OK] G4 baseline is unbound Code 28'
  } else {
    throw "G4_UNSUPPORTED_HDA_BASELINE: service=$($script:OriginalHdaService) code=$($hda.ConfigManagerErrorCode)"
  }

  # Signer validation + trust
  $signer=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cer)
  $script:CertThumb=$signer.Thumbprint
  foreach($file in @($sys,$cat)){
    $sig=Get-AuthenticodeSignature $file
    if(-not $sig.SignerCertificate -or $sig.SignerCertificate.Thumbprint -ne $signer.Thumbprint){
      throw "G4_PACKAGE_SIGNER_MISMATCH: $file"
    }
  }

  $script:HadRoot=[bool](Get-ChildItem Cert:\LocalMachine\Root |
    Where-Object Thumbprint -eq $script:CertThumb | Select-Object -First 1)
  $script:HadPublisher=[bool](Get-ChildItem Cert:\LocalMachine\TrustedPublisher |
    Where-Object Thumbprint -eq $script:CertThumb | Select-Object -First 1)

  Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
  Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null
  foreach($file in @($sys,$cat)){
    $sig=Get-AuthenticodeSignature $file
    if($sig.Status -ne 'Valid'){throw "G4_SIGNATURE_NOT_VALID_AFTER_TRUST: $file -> $($sig.Status)"}
  }

  # Stage and temporarily force-bind the read-only probe.
  $stageOutput=@(& pnputil.exe /add-driver $inf 2>&1)
  $stageRc=$LASTEXITCODE
  $stageOutput | Tee-Object -FilePath (Join-Path $script:Out 'HDA_STAGE_PROBE.txt') | ForEach-Object {Write-Host $_}
  if($stageRc){throw "G4_STAGE_FAIL rc=$stageRc"}

  # Capture the published package name directly from PnPUtil. Win32_PnPSignedDriver
  # can temporarily report stale metadata immediately after a forced live rebind.
  $publishedProbeInf=$null
  foreach($line in $stageOutput){
    if([string]$line -match '(?i)Published Name:\s*(oem\d+\.inf)'){
      $publishedProbeInf=$matches[1]
      break
    }
  }
  if($publishedProbeInf){
    $script:ProbeInfName=$publishedProbeInf
    KV 'HDA_PROBE_PUBLISHED_INF' $script:ProbeInfName
  } else {
    KV 'HDA_PROBE_PUBLISHED_INF' 'UNKNOWN_FROM_STAGE_OUTPUT'
  }

  [bool]$probeReboot=$false
  $script:ProbeBindAttempted=$true
  $ok=[P360.NewDev]::UpdateDriverForPlugAndPlayDevices(
    [IntPtr]::Zero,$script:HdaHardwareId,$inf,[uint32]1,[ref]$probeReboot)
  if(-not $ok){throw "G4_BIND_FAIL Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
  if($probeReboot){throw 'G4_BIND_REQUESTED_REBOOT: rollback will be attempted immediately'}

  Start-Sleep -Seconds 3
  $hda=Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPDeviceID -eq $script:HdaChildId} | Select-Object -First 1
  $bound=FindSignedDriver $script:HdaChildId
  $wmiBoundInf=[string]$bound.InfName
  $wmiBoundVersion=[string]$bound.DriverVersion

  # Keep the PnPUtil-published probe INF as authoritative for cleanup.
  # Record WMI values separately because they may lag behind the live bind.
  if(-not $script:ProbeInfName){$script:ProbeInfName=$wmiBoundInf}

  KV 'HDA_PROBE_INF' $script:ProbeInfName
  KV 'HDA_PROBE_WMI_INF' $wmiBoundInf
  KV 'HDA_PROBE_SERVICE' $hda.Service
  KV 'HDA_PROBE_CODE' $hda.ConfigManagerErrorCode
  KV 'HDA_PROBE_WMI_VERSION' $wmiBoundVersion

  if($hda.Service -ne 'P360HdaReadProbe' -or $hda.ConfigManagerErrorCode -ne 0){
    throw "G4_HDA_PROBE_START_FAIL: service=$($hda.Service) code=$($hda.ConfigManagerErrorCode)"
  }
  W '[OK] G4 temporary HDA read-only probe bound; original package remains exported'

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

  # G6: three read-only GET_PARAMETER(VENDOR_ID) transfers.
  $totalDelta=[int64]0
  $validReads=0
  $vendorMatches=0
  [uint32]$vendorExpected=[Convert]::ToUInt32('8086280D',16)

  for($i=1;$i -le 3;$i++){
    $before=Read-DspProbe
    $hr=Read-Hda $true
    Start-Sleep -Milliseconds 100
    $after=Read-DspProbe
    $delta=$after.Irq-$before.Irq
    $totalDelta+=$delta

    if($hr.Transfer -eq 0 -and $hr.Valid -eq 1){$validReads++}
    if($hr.Response -eq $vendorExpected){$vendorMatches++}

    W ("[G6.{0}] transfer=0x{1:X8} command=0x{2:X8} response=0x{3:X8} valid={4} overrun={5} IRQ {6}->{7} delta={8}" -f
      $i,$hr.Transfer,$hr.Command,$hr.Response,$hr.Valid,$hr.Overrun,$before.Irq,$after.Irq,$delta)

    [pscustomobject]@{
      Iteration=$i
      TransferStatus=('0x{0:X8}' -f $hr.Transfer)
      Command=('0x{0:X8}' -f $hr.Command)
      Response=('0x{0:X8}' -f $hr.Response)
      ExpectedResponse=('0x{0:X8}' -f $vendorExpected)
      Valid=$hr.Valid
      FifoOverrun=$hr.Overrun
      IrqBefore=$before.Irq
      IrqAfter=$after.Irq
      IrqDelta=$delta
    } | Export-Csv -LiteralPath (Join-Path $script:Out 'ACTIVE_IRQ_READS.csv') -NoTypeInformation -Append -Encoding UTF8
  }

  KV 'HDA_VALID_READS' $validReads
  KV 'HDA_VENDOR_MATCHES' $vendorMatches
  KV 'ACTIVE_IRQ_DELTA_TOTAL' $totalDelta
  KV 'ACTIVE_IRQ_PROVED' ($validReads -ge 1 -and $totalDelta -gt 0)
  KV 'HDA_EXPECTED_VENDOR_DEVICE' ('0x{0:X8}' -f $vendorExpected)
  KV 'HDA_LAST_VENDOR_DEVICE' ('0x{0:X8}' -f $hr.Response)

  if($validReads -lt 1){throw 'G6_HDA_READ_FAILED: no valid RIRB response'}
  if($totalDelta -le 0){throw 'G6_IRQ_CALLBACK_NOT_OBSERVED_DURING_CONFIRMED_HDA_TRANSFER'}

  W "[OK] G6 ACTIVE IRQ PROVED: validReads=$validReads vendorMatches=$vendorMatches totalDelta=$totalDelta"

  # G7: collect remaining blockers. Still no writes to DSP/codecs.
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

  $eps2=@(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
    Where-Object {$_.ClassGuid -eq '{c166523c-fe0c-4a94-a586-f1a80cfbbf3e}' -and $_.Status -eq 'OK'})
  KV 'ACTIVE_AUDIO_ENDPOINTS_AFTER' $eps2.Count

  $audioReady=($sofSvc.Count -gt 0 -and
    $da2 -and $da2.Service -and $da2.ConfigManagerErrorCode -eq 0 -and
    $mx2 -and $mx2.Service -and $mx2.ConfigManagerErrorCode -eq 0 -and
    $eps2.Count -gt 0)

  KV 'AUDIO_READY' $audioReady
  if($audioReady){
    KV 'FINAL_GATE' 'AUDIO_STACK_PRESENT__VOLUME_GUARD_REQUIRED_BEFORE_PLAYBACK'
  } else {
    KV 'FINAL_GATE' 'IRQ_PROVED__AUDIO_BLOCKED_BY_MISSING_SOF_CODEC_ENDPOINT_STACK'
  }

} catch {
  $script:ExitCode=2
  KV 'FINAL_GATE' 'FAIL'
  KV 'FAILURE' $_.Exception.Message
  W "[FAIL] $($_.Exception.Message)"
} finally {
  # Always restore the exact HDA baseline before removing the temporary probe/trust.
  if($script:ProbeBindAttempted){
    W '[ROLLBACK] restoring HDA child baseline...'
    $restore=Restore-HdaBaseline
    $script:RestoreSucceeded=[bool]$restore.Ok
    KV 'HDA_BASELINE_RESTORED' $script:RestoreSucceeded
    KV 'HDA_RESTORE_REASON' $restore.Reason
    W "[ROLLBACK] $($restore.Reason)"

    if(-not $script:RestoreSucceeded){
      $script:ExitCode=3
      KV 'ROLLBACK_FAILURE' $restore.Reason
    }
  } else {
    KV 'HDA_BASELINE_RESTORED' $true
    KV 'HDA_RESTORE_REASON' 'No temporary HDA bind was attempted'
  }

  # Remove temporary probe package only after baseline restore succeeds.
  if($script:RestoreSucceeded -and $script:ProbeInfName -and
     $script:ProbeInfName -match '^oem\d+\.inf$' -and
     $script:ProbeInfName -ne $script:OriginalHdaInfName){
    W "[CLEANUP] deleting temporary probe package $script:ProbeInfName"
    & pnputil.exe /delete-driver $script:ProbeInfName /force 2>&1 |
      Tee-Object -FilePath (Join-Path $script:Out 'HDA_DELETE_PROBE_PACKAGE.txt')
    KV 'HDA_PROBE_DELETE_RC' $LASTEXITCODE
  }

  # Do not remove trust if rollback failed; keep the current test driver loadable.
  if($script:RestoreSucceeded -and $script:CertThumb){
    if(-not $script:HadRoot){
      Get-ChildItem Cert:\LocalMachine\Root |
        Where-Object Thumbprint -eq $script:CertThumb |
        Remove-Item -Force -ErrorAction SilentlyContinue
    }
    if(-not $script:HadPublisher){
      Get-ChildItem Cert:\LocalMachine\TrustedPublisher |
        Where-Object Thumbprint -eq $script:CertThumb |
        Remove-Item -Force -ErrorAction SilentlyContinue
    }
  }

  $p2=FindDev 'PCI\VEN_8086&DEV_3198'
  $h2=FindDev 'HDAUDIO\FUNC_01&VEN_8086&DEV_280D'
  $d2=FindDev 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198'

  if($p2){KV 'POST_PARENT' "$($p2.Status)/$($p2.ConfigManagerErrorCode)/$($p2.Service)"}else{KV 'POST_PARENT' 'ABSENT'}
  if($h2){KV 'POST_HDA' "$($h2.Status)/$($h2.ConfigManagerErrorCode)/$($h2.Service)"}else{KV 'POST_HDA' 'ABSENT'}
  if($d2){KV 'POST_DSP' "$($d2.Status)/$($d2.ConfigManagerErrorCode)/$($d2.Service)"}else{KV 'POST_DSP' 'ABSENT'}

  if($script:OriginalHdaService -eq 'IntcDAud' -and $h2){
    $postHdaOk=($h2.Service -eq 'IntcDAud' -and $h2.ConfigManagerErrorCode -eq 0)
    KV 'POST_HDA_BASELINE_OK' $postHdaOk
    if(-not $postHdaOk){$script:ExitCode=3}
  }

  KV 'AUDIO_PLAYBACK' 'NO'
  KV 'RUNNER_EXIT_CODE' $script:ExitCode

  $reportPath=Join-Path $script:Out 'REPORT.txt'
  $script:ReportLines | Set-Content -LiteralPath $reportPath -Encoding UTF8

  Write-Host ''
  Write-Host '================ REPORT ================'
  Get-Content $reportPath | ForEach-Object {Write-Host $_}

  $desktop=[Environment]::GetFolderPath('Desktop')
  $zipPath=Join-Path $desktop ("P360_PREAUDIO_GATE_V2_"+$stamp+".zip")
  Compress-Archive -Path (Join-Path $script:Out '*') -DestinationPath $zipPath -Force
  Write-Host "ZIP=$zipPath"
  Write-Host 'AUDIO_PLAYBACK=NO'
}

exit $script:ExitCode
