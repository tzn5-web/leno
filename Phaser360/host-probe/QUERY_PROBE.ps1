#requires -version 5.1
$ErrorActionPreference='Stop'
if (-not ("P360.IO" -as [type])) {
Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace P360 {
 public static class IO {
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
function Get-P360ProbeStatus {
  $h=[P360.IO]::CreateFile('\\.\P360AdspProbe',[uint32]2147483648,0,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
  if($h -eq [IntPtr](-1)){
    throw "Probe not accessible; Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())."
  }
  try {
    $buffer=New-Object byte[] 48
    [uint32]$written=0
    $ok=[P360.IO]::DeviceIoControl($h,0x226004,[IntPtr]::Zero,0,$buffer,48,[ref]$written,[IntPtr]::Zero)
    if(-not $ok){throw "DeviceIoControl failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
    if($written -ne 48){throw "Unexpected response size $written (need v2=48). Reinstall/upgrade the probe."}
    $magic=[BitConverter]::ToUInt32($buffer,0)
    if($magic -ne 0x50333630){throw "Invalid response magic: $magic"}
    [pscustomobject]@{
      Version=[BitConverter]::ToUInt32($buffer,4)
      QueryStatus=[BitConverter]::ToUInt32($buffer,8)
      RegisterStatus=[BitConverter]::ToUInt32($buffer,12)
      Flags=[BitConverter]::ToUInt32($buffer,16)
      ControllerDeviceId=[BitConverter]::ToUInt16($buffer,20)
      InterfaceVersion=[BitConverter]::ToUInt16($buffer,22)
      InterfaceSize=[BitConverter]::ToUInt32($buffer,24)
      IrqCount=[BitConverter]::ToInt64($buffer,32)
    }
  }
  finally {[void][P360.IO]::CloseHandle($h)}
}
$s=Get-P360ProbeStatus
Write-Host "PROBE_VERSION=$($s.Version)"
Write-Host ("QUERY_STATUS=0x{0:X8}" -f $s.QueryStatus)
Write-Host ("IRQ_REGISTER_STATUS=0x{0:X8}" -f $s.RegisterStatus)
Write-Host ("CTLR_DEVICE_ID=0x{0:X4}" -f $s.ControllerDeviceId)
Write-Host "INTERFACE_VERSION=$($s.InterfaceVersion)"
Write-Host "INTERFACE_SIZE=$($s.InterfaceSize)"
Write-Host ("FLAGS=0x{0:X8}" -f $s.Flags)
Write-Host "BUS_INTERFACE_OK=$([bool]($s.Flags -band 1))"
Write-Host "GET_RESOURCES_EXPORT_PRESENT=$([bool]($s.Flags -band 2))"
Write-Host "IRQ_REGISTER_EXPORT_PRESENT=$([bool]($s.Flags -band 4))"
Write-Host "IRQ_CALLBACK_REGISTERED=$([bool]($s.Flags -band 8))"
Write-Host "IRQ_TRAFFIC_SEEN=$([bool]($s.Flags -band 16))"
Write-Host "IRQ_COUNT=$($s.IrqCount)"
Write-Host "DSP_BOOT=NO; MMIO=NO; IPC=NO; AUDIO=NO"
