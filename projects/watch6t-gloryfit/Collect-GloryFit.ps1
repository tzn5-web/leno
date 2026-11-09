# Extract installed GloryFit APK splits + accessible dial cache, without modifying the phone or watch.
[CmdletBinding()] param([string]$Adb='', [string]$OutputDir='')
$ErrorActionPreference='Stop'
$desk=[Environment]::GetFolderPath('Desktop')
if(-not $Adb){
  $options=@((Join-Path $desk 'platform-tools\adb.exe'),'D:\dre\XIAOMI 11T\platform-tools\adb.exe','E:\tableta lenovo\platform-tools\adb.exe')
  $Adb=$options | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if(-not $Adb){$cmd=Get-Command adb.exe -ErrorAction SilentlyContinue;if($cmd){$Adb=$cmd.Source}}
}
if(-not $Adb -or -not (Test-Path -LiteralPath $Adb)){throw 'ADB absent: install platform-tools on Desktop or specify -Adb'}
$dev=@(& $Adb devices | Where-Object {$_ -match '^\S+\s+device\s*$'})
if($dev.Count -ne 1){& $Adb devices;throw 'Connect exactly one authorized USB-debugging phone'}
if(-not $OutputDir){$OutputDir=Join-Path $desk ('GloryFit_APK_'+(Get-Date -Format yyyyMMdd_HHmmss))}
$apkDir=Join-Path $OutputDir 'apks'
$cacheDir=Join-Path $OutputDir 'watchfaces'
New-Item -ItemType Directory -Force -Path $apkDir,$cacheDir | Out-Null
$paths=@(& $Adb shell pm path com.yc.gloryfit | ForEach-Object {$_.Trim()} | Where-Object {$_ -match '^package:/' } | ForEach-Object {$_.Substring(8)})
if($paths.Count -lt 1){throw 'No installed com.yc.gloryfit APK found'}
$report=[ordered]@{package='com.yc.gloryfit';date=(Get-Date).ToString('o');files=@();cache=@()}
foreach($remote in $paths) {
  $name=[IO.Path]::GetFileName($remote)
  $dest=Join-Path $apkDir $name
  Write-Host "Extracting $name"
  $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
  try { & $Adb pull $remote $dest 2>&1 | Out-Null;$status=$LASTEXITCODE }
  finally {$ErrorActionPreference=$old}
  if($status -ne 0 -or !(Test-Path -LiteralPath $dest)){throw "Failed to pull $remote"}
  $f=Get-Item -LiteralPath $dest
  $report.files+=@{filename=$name;bytes=$f.Length;sha256=(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash}
}
$dirs=@('/sdcard/Android/data/com.yc.gloryfit/files/DialCustom','/sdcard/Android/data/com.yc.gloryfit/files','/sdcard/Android/media/com.yc.gloryfit')
foreach($remote in $dirs) {
  $safe=$remote -replace '[^a-zA-Z0-9]','_'
  $dest=Join-Path $cacheDir $safe
  $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
  try{ & $Adb pull $remote $dest 2>&1 | Out-Null;$status=$LASTEXITCODE }
  finally{$ErrorActionPreference=$old}
  if($status -eq 0){$report.cache+=$remote}
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDir 'report.json') -Encoding UTF8
$zip=$OutputDir+'.zip'
Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $zip -Force -CompressionLevel Optimal
Write-Host "COMPLETE: $zip"
Write-Host 'PRIVATE APK: do not publish this archive to a public GitHub repository.'
