#requires -version 5.1
$ErrorActionPreference='Stop'
if(-not ('P360.HdaIrqTestIO' -as [type])){
Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
 public static class HdaIrqTestIO {
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
  public static extern IntPtr CreateFile(string n,uint a,uint s,IntPtr sec,uint d,uint f,IntPtr t);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool DeviceIoControl(IntPtr h,uint c,IntPtr i,uint il,[Out]byte[] o,uint ol,out uint n,IntPtr ov);
  [DllImport("kernel32.dll",SetLastError=true)]
  [return:MarshalAs(UnmanagedType.Bool)]
  public static extern bool CloseHandle(IntPtr h);
 }
}
'@
}
function Open-Dev([string]$name){
 $h=[P360.HdaIrqTestIO]::CreateFile($name,[uint32]2147483648,0,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
 if($h -eq [IntPtr](-1)){throw "Open $name failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
 return $h
}
function Read-Irq {
 $h=Open-Dev '\\.\P360AdspProbe'
 try{
  $b=New-Object byte[] 48; [uint32]$n=0
  if(-not [P360.HdaIrqTestIO]::DeviceIoControl($h,0x226004,[IntPtr]::Zero,0,$b,48,[ref]$n,[IntPtr]::Zero)){throw 'ADSP status IOCTL failed'}
  if($n -ne 48){throw "ADSP probe is not v2 (bytes=$n)"}
  [pscustomobject]@{Version=[BitConverter]::ToUInt32($b,4);Status=[BitConverter]::ToUInt32($b,12);Flags=[BitConverter]::ToUInt32($b,16);Count=[BitConverter]::ToInt64($b,32)}
 } finally {[void][P360.HdaIrqTestIO]::CloseHandle($h)}
}
$before=Read-Irq
if($before.Version -ne 2 -or ($before.Flags -band 8) -eq 0){throw 'ADSP passive callback probe v2 is not registered.'}

$h=Open-Dev '\\.\P360HdaTrigger'
try{
 $b=New-Object byte[] 40; [uint32]$n=0
 if(-not [P360.HdaIrqTestIO]::DeviceIoControl($h,0x226044,[IntPtr]::Zero,0,$b,40,[ref]$n,[IntPtr]::Zero)){
   throw "HDA trigger IOCTL failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
 }
 if($n -ne 40){throw "Wrong HDA trigger response size $n"}
} finally {[void][P360.HdaIrqTestIO]::CloseHandle($h)}

$after=Read-Irq
$magic=[BitConverter]::ToUInt32($b,0)
if($magic -ne 0x48333630){throw ("Bad HDA result magic 0x{0:X8}" -f $magic)}
$q=[BitConverter]::ToUInt32($b,8)
$t=[BitConverter]::ToUInt32($b,12)
$cmd=[BitConverter]::ToUInt32($b,16)
$resp=[BitConverter]::ToUInt32($b,20)
$flags=[BitConverter]::ToUInt32($b,24)
$addr=$b[28]
$fg=$b[29]
$complete=[BitConverter]::ToUInt64($b,32)
$delta=$after.Count-$before.Count

Write-Host ("HDA_QUERY_STATUS=0x{0:X8}" -f $q)
Write-Host ("HDA_TRANSFER_STATUS=0x{0:X8}" -f $t)
Write-Host ("HDA_COMMAND=0x{0:X8}" -f $cmd)
Write-Host "HDA_CODEC_ADDRESS=$addr"
Write-Host "HDA_FUNCTION_GROUP_START_NODE=$fg"
Write-Host "HDA_RESPONSE_VALID=$([bool]($flags -band 2))"
Write-Host ("HDA_VENDOR_RESPONSE=0x{0:X8}" -f $resp)
Write-Host ("HDA_COMPLETE_RESPONSE=0x{0:X16}" -f $complete)
Write-Host "IRQ_BEFORE=$($before.Count)"
Write-Host "IRQ_AFTER=$($after.Count)"
Write-Host "IRQ_DELTA=$delta"
Write-Host 'DSP_BOOT=NO; DSP_MMIO=NO; IPC=NO; STREAM=NO; AUDIO=NO'

if($t -eq 0 -and ($flags -band 2) -ne 0 -and $delta -gt 0){
 Write-Host 'ACTIVE_IRQ_RESULT=PROVED'
 Write-Host 'MEANING=CORB/RIRB completion traversed the parent ISR and reached the registered ADSP callback.'
} elseif($t -eq 0xC000009D) {
 Write-Host 'ACTIVE_IRQ_RESULT=INCONCLUSIVE_GRAPHICS_CODEC_DISCONNECTED'
 Write-Host 'MEANING=The parent refused the read-only verb because the graphics codec is not connected.'
} elseif($t -eq 0xC00000B5) {
 Write-Host 'ACTIVE_IRQ_RESULT=RIRB_TIMEOUT'
 Write-Host 'MEANING=The read verb was queued but completion timed out; inspect IRQ/RIRB path next.'
} elseif($t -eq 0 -and ($flags -band 2) -ne 0 -and $delta -eq 0) {
 Write-Host 'ACTIVE_IRQ_RESULT=CONTRADICTION'
 Write-Host 'MEANING=HDA response completed but ADSP callback counter did not move; audit ISR callback lifetime/order.'
} else {
 Write-Host 'ACTIVE_IRQ_RESULT=INCONCLUSIVE'
}
