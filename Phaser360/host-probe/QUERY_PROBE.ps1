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
$h=[P360.IO]::CreateFile('\\.\P360AdspProbe',0x80000000,0,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
if($h -eq [IntPtr](-1)){
  throw "Probe not accessible; Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error()). Install the diagnostic function driver first."
}
try {
  $buffer=New-Object byte[] 32
  [uint32]$written=0
  $ok=[P360.IO]::DeviceIoControl($h,0x226004,[IntPtr]::Zero,0,$buffer,32,[ref]$written,[IntPtr]::Zero)
  if(-not $ok){throw "DeviceIoControl failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"}
  if($written -ne 32){throw "Unexpected response size $written"}
  $magic=[BitConverter]::ToUInt32($buffer,0)
  if($magic -ne 0x50333630){throw "Invalid response magic: $magic"}
  $code=[BitConverter]::ToUInt32($buffer,8)
  $flags=[BitConverter]::ToUInt32($buffer,12)
  $ctlr=[BitConverter]::ToUInt16($buffer,16)
  $ver=[BitConverter]::ToUInt16($buffer,18)
  $size=[BitConverter]::ToUInt32($buffer,20)
  Write-Host ("QUERY_STATUS=0x{0:X8}" -f $code)
  Write-Host ("CTLR_DEVICE_ID=0x{0:X4}" -f $ctlr)
  Write-Host "INTERFACE_VERSION=$ver"
  Write-Host "INTERFACE_SIZE=$size"
  Write-Host ("FLAGS=0x{0:X8}" -f $flags)
  Write-Host "BUS_INTERFACE_OK=$([bool]($flags -band 1))"
  Write-Host "GET_RESOURCES_EXPORT_PRESENT=$([bool]($flags -band 2))"
  Write-Host "IRQ_REGISTER_EXPORT_PRESENT=$([bool]($flags -band 4))"
  Write-Host "IRQ_TRAFFIC_TESTED=FALSE"
  Write-Host "DSP_BOOT=NO; IPC=NO; AUDIO=NO"
}
finally {[void][P360.IO]::CloseHandle($h)}
