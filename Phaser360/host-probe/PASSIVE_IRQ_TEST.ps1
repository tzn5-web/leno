#requires -version 5.1
$ErrorActionPreference='Stop'
if (-not ("P360.PassiveIrqIO" -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
 public static class PassiveIrqIO {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr sec, uint disposition, uint flags, IntPtr template);
  [DllImport("kernel32.dll", SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  public static extern bool DeviceIoControl(IntPtr h, uint ctl, IntPtr input, uint inlen, [Out] byte[] output, uint outlen, out uint written, IntPtr overlapped);
  [DllImport("kernel32.dll", SetLastError=true)]
  [return: MarshalAs(UnmanagedType.Bool)]
  public static extern bool CloseHandle(IntPtr handle);
 }
}
'@
}
function Read-Count {
  $h=[P360.PassiveIrqIO]::CreateFile('\\.\P360AdspProbe',[uint32]2147483648,0,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
  if($h -eq [IntPtr](-1)){throw "Probe open failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
  try{
    $b=New-Object byte[] 48
    [uint32]$n=0
    if(-not [P360.PassiveIrqIO]::DeviceIoControl($h,0x226004,[IntPtr]::Zero,0,$b,48,[ref]$n,[IntPtr]::Zero)){
      throw "IOCTL failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    if($n -ne 48){throw "Wrong probe version/size: $n"}
    [pscustomobject]@{
      Version=[BitConverter]::ToUInt32($b,4)
      RegisterStatus=[BitConverter]::ToUInt32($b,12)
      Flags=[BitConverter]::ToUInt32($b,16)
      Count=[BitConverter]::ToInt64($b,32)
    }
  } finally {[void][P360.PassiveIrqIO]::CloseHandle($h)}
}
$before=Read-Count
if($before.Version -ne 2){throw "Need passive IRQ probe v2; found $($before.Version)"}
if(($before.Flags -band 8) -eq 0){throw ("IRQ callback is not registered; status=0x{0:X8}" -f $before.RegisterStatus)}
Write-Host "PASSIVE_IRQ_WINDOW_SECONDS=5"
Write-Host "IRQ_BEFORE=$($before.Count)"
Write-Host "Waiting without DSP boot, MMIO, IPC or audio..."
Start-Sleep -Seconds 5
$after=Read-Count
$delta=$after.Count-$before.Count
Write-Host "IRQ_AFTER=$($after.Count)"
Write-Host "IRQ_DELTA=$delta"
Write-Host "IRQ_CALLBACK_REGISTERED=$([bool]($after.Flags -band 8))"
Write-Host "IRQ_TRAFFIC_SEEN=$([bool]($after.Flags -band 16))"
Write-Host "DSP_BOOT=NO; MMIO=NO; IPC=NO; AUDIO=NO"
if($delta -gt 0){
  Write-Host "PASSIVE_IRQ_RESULT=TRAFFIC_OBSERVED"
} else {
  Write-Host "PASSIVE_IRQ_RESULT=NO_TRAFFIC_IN_IDLE_WINDOW"
  Write-Host "NOTE=This does not prove IRQ routing is broken; no DSP interrupt source was intentionally generated."
}
