# Cache swap with backup and verification. NOT a firmware upgrade.
# Applies only if the downloaded GloryFit cache file exactly matches this package's original.
[CmdletBinding()]
param([switch]$Restore)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$folder=$PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $folder 'MANIFEST_V6.json') -Raw | ConvertFrom-Json
$desktop=[Environment]::GetFolderPath('Desktop')
$adbCandidates=@(
  (Join-Path $desktop 'platform-tools\adb.exe'),
  'D:\dre\XIAOMI 11T\platform-tools\adb.exe',
  'E:\tableta lenovo\platform-tools\adb.exe'
)
$adbPath=$adbCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if(-not $adbPath){$cmd=Get-Command adb.exe -ErrorAction SilentlyContinue;if($cmd){$adbPath=$cmd.Source}}
if(-not $adbPath){throw 'ADB nu a fost gasit pe Desktop sau in PATH.'}
function Run-Adb([string[]]$A){
  # adb prints successful pull/push progress to stderr: do not throw for that alone.
  $old=$ErrorActionPreference; $ErrorActionPreference='Continue'
  try { $lines=@(& $adbPath @A 2>&1 | ForEach-Object { [string]$_ });$rc=$LASTEXITCODE }
  finally { $ErrorActionPreference=$old }
  if($rc -ne 0){throw ('ADB a esuat (cod '+$rc+'): '+($lines -join ' '))}
  return ($lines -join "`n")
}
$devices=Run-Adb -A @('devices')
if(@($devices -split "`n" | Where-Object {$_ -match '^\S+\s+device\s*$'}).Count -ne 1){throw "Conecteaza exact un telefon autorizat ADB:`n$devices"}
if((Run-Adb -A @('shell','pm','path','com.yc.gloryfit')) -notmatch 'package:'){throw 'GloryFit nu este instalat pe telefon.'}
$localOriginal=Join-Path $folder 'D1898001_ORIGINAL_DO_NOT_EDIT.bin'
$localNew=Join-Path $folder 'D1898001_HOLO_V6_BETA_UNTESTED.bin'
if(-not (Test-Path -LiteralPath $localOriginal) -or -not (Test-Path -LiteralPath $localNew)){throw 'Lipsesc fisierele BIN din folder.'}
$hashOriginal=(Get-FileHash -LiteralPath $localOriginal -Algorithm SHA256).Hash.ToLowerInvariant()
$hashNew=(Get-FileHash -LiteralPath $localNew -Algorithm SHA256).Hash.ToLowerInvariant()
if($hashOriginal -ne $manifest.source_sha256 -or $hashNew -ne $manifest.output_sha256){throw 'SHA256 invalid pentru fisierele din pachet. Nu scriu nimic.'}
$remote='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin'
$temp='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.holo_tmp'
function RemoteSha([string]$path){
  $v=Run-Adb -A @('shell','sha256sum',$path)
  $m=[regex]::Match($v,'([0-9a-fA-F]{64})\s')
  if(-not $m.Success){throw "Nu am putut verifica SHA256 de pe telefon pentru $path"}
  return $m.Groups[1].Value.ToLowerInvariant()
}
$before=RemoteSha $remote
$expectedBefore=if($Restore){$hashNew}else{$hashOriginal}
$expectedAfter=if($Restore){$hashOriginal}else{$hashNew}
$localFile=if($Restore){$localOriginal}else{$localNew}
if($before -eq $expectedAfter){Write-Host 'Versiunea ceruta este deja in cache.';exit 0}
if($before -ne $expectedBefore){
 throw ('Cache-ul actual a fost schimbat de GloryFit. SHA256='+$before+'. Refuz suprascrierea unui fisier necunoscut.')
}
$backupDir=Join-Path $desktop 'Watch6T_BACKUP'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backup=Join-Path $backupDir ('D1898001_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.bin')
Run-Adb -A @('pull',$remote,$backup) | Out-Null
if((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before){throw 'Backup corupt. Nu modific cache-ul.'}
Run-Adb -A @('push',$localFile,$temp) | Out-Null
if((RemoteSha $temp) -ne $expectedAfter){
  try {Run-Adb -A @('shell','rm','-f',$temp) | Out-Null}catch{}
  throw 'Copiere temporara invalida. Originalul ramane nemodificat.'
}
Run-Adb -A @('shell','mv','-f',$temp,$remote) | Out-Null
if((RemoteSha $remote) -ne $expectedAfter){throw 'Verificare finala SHA esuata. Nu sincroniza cadranul.'}
Write-Host "Backup creat: $backup"
if($Restore){Write-Host 'Originalul este restaurat in cache. Resincronizeaza cadranul original in GloryFit.'}
else {
 Write-Host 'HOLO V6 este pregatit in cache, NU pe ceas.'
 Write-Host 'In GloryFit: Dispozitiv > Cadrane > Cadranele mele > resyncronizeaza exact cadranul D1898001.'
 Write-Host 'Nu folosi Upgrade de firmware! Compatibilitatea cu firmware-ul Watch6T este inca neverificata.'
}
