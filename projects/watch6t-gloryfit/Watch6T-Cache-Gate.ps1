# iHunt Watch6T — read-only GloryFit cache inspector. Does not install faces.
[CmdletBinding()] param([string]$Adb='', [string]$OutputDir='')
$ErrorActionPreference='Stop'
$desktop=[Environment]::GetFolderPath('Desktop')
if(-not $Adb) {
  $options=@((Join-Path $desktop 'platform-tools\adb.exe'),'D:\dre\XIAOMI 11T\platform-tools\adb.exe','E:\tableta lenovo\platform-tools\adb.exe')
  $Adb=$options | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if(-not $Adb -or -not (Test-Path -LiteralPath $Adb)){throw 'ADB not found. Specify -Adb or install platform-tools on the Desktop.'}
$devices=@(& $Adb devices | Where-Object {$_ -match '^\S+\s+device\s*$'})
if($devices.Count -ne 1){ & $Adb devices;throw 'Connect exactly one USB-debugging-authorized phone.' }
if(-not $OutputDir){ $OutputDir=Join-Path $desktop ('Watch6T_CacheGate_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
New-Item -Force -ItemType Directory -Path $OutputDir | Out-Null
$report=[ordered]@{timestamp=(Get-Date).ToString('s'); package='com.yc.gloryfit'; status='read-only'; adb_path=$Adb; targets=@()}
$paths=@('/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin', '/sdcard/Android/data/com.yc.gloryfit/files/DialCustom/D1898001.bin')
foreach($path in $paths){
   $oldAction=$ErrorActionPreference;$ErrorActionPreference='Continue'
   try{ $info=@(& $Adb shell ls -l $path 2>&1 | ForEach-Object {[string]$_});$probeStatus=$LASTEXITCODE }
   finally{$ErrorActionPreference=$oldAction}
   $entry=[ordered]@{remote_path=$path;ls=($info -join ' ').Trim();pulled=$false}
   if($probeStatus -eq 0){
      $destination=Join-Path $OutputDir ([IO.Path]::GetFileName($path))
      $saveError=$ErrorActionPreference;$ErrorActionPreference='Continue'
      try{ & $Adb pull $path $destination 2>&1 | Out-Null;$status=$LASTEXITCODE }
      finally{$ErrorActionPreference=$saveError}
      if($status -eq 0 -and (Test-Path -LiteralPath $destination)){
         $entry.pulled=$true; $entry.bytes=(Get-Item -LiteralPath $destination).Length
         $entry.sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
      }
   }
   $report.targets+=$entry
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDir 'cache_gate.json') -Encoding UTF8
$archive=$OutputDir+'.zip'
Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $archive -Force
Write-Host ('Created: '+$archive)
Write-Host 'No write operations on the phone or watch were performed.'
