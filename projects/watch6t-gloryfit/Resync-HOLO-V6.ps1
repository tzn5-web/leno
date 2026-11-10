# GloryFit HOLO V6 cache stage and re-sync assistant; not a firmware update.
# Only modifies the specific known cached watchface, and only if its original hash matches.
[CmdletBinding()] param([switch]$Restore)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$desktop=[Environment]::GetFolderPath('Desktop')
$adbCandidates=@(
 (Join-Path $desktop 'platform-tools\adb.exe'),
 'D:\dre\XIAOMI 11T\platform-tools\adb.exe',
 'E:\tableta lenovo\platform-tools\adb.exe'
)
$adbPath=$adbCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if(-not $adbPath){$which=Get-Command adb.exe -ErrorAction SilentlyContinue;if($which){$adbPath=$which.Source}}
if(-not $adbPath){throw 'adb.exe negasit. Este necesar Android platform-tools.'}
function Invoke-Adb([string[]] $Arguments){
 $old=$ErrorActionPreference; $ErrorActionPreference='Continue'
 try { $lines=@(& $adbPath @Arguments 2>&1 | ForEach-Object { [string]$_ });$exitCode=$LASTEXITCODE }
 finally { $ErrorActionPreference=$old }
 if($exitCode -ne 0){throw ('ADB '+$exitCode+': '+($lines -join ' '))}
 return ($lines -join "\`n")
}
$devices=Invoke-Adb -Arguments @('devices')
if(@($devices -split "\`n" | Where-Object {$_ -match '^\S+\s+device\s*$'}).Count -ne 1){throw ('Este necesar un singur telefon autorizat ADB: '+$devices)}
$pkg='com.yc.gloryfit'
if((Invoke-Adb -Arguments @('shell','pm','path',$pkg)) -notmatch 'package:'){throw 'GloryFit nu e instalat pe telefon.'}
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'MANIFEST_V6.json') -Raw | ConvertFrom-Json
$stock=Join-Path $PSScriptRoot 'D1898001_ORIGINAL_DO_NOT_EDIT.bin'
$holo=Join-Path $PSScriptRoot 'D1898001_HOLO_V6_BETA_UNTESTED.bin'
if(!(Test-Path -LiteralPath $stock) -or !(Test-Path -LiteralPath $holo)){throw 'Lipseste fisierul BIN.'}
$expectedOriginal=$manifest.source_sha256.ToLowerInvariant()
$expectedModified=$manifest.output_sha256.ToLowerInvariant()
if((Get-FileHash -LiteralPath $stock -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedOriginal){throw 'BIN original local invalid.'}
if((Get-FileHash -LiteralPath $holo -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedModified){throw 'BIN HOLO local invalid.'}
$remote='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin'
$temp='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.holo_tmp'
function Remote-Sha([string]$Path){
 $raw=Invoke-Adb -Arguments @('shell','sha256sum',$Path)
 $m=[regex]::Match($raw,'([a-fA-F0-9]{64})\s')
 if(!$m.Success){throw ('Nu pot calcula hash pentru '+$Path)}
 return $m.Groups[1].Value.ToLowerInvariant()
}
# Stop the app before replacing cached bytes. No BLE command is sent here.
Invoke-Adb -Arguments @('shell','am','force-stop',$pkg) | Out-Null
$before=Remote-Sha $remote
$desired=if($Restore){$expectedOriginal}else{$expectedModified}
$allowed=if($Restore){$expectedModified}else{$expectedOriginal}
$local=if($Restore){$stock}else{$holo}
if($before -ne $desired){
 if($before -ne $allowed){throw ('Cache necunoscut: '+$before+'. Nu suprascriu alte fisiere GloryFit.')}
 $backupFolder=Join-Path $desktop 'Watch6T_BACKUP'
 New-Item -ItemType Directory -Force -Path $backupFolder | Out-Null
 $backup=Join-Path $backupFolder ('D1898001_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.bin')
 Invoke-Adb -Arguments @('pull',$remote,$backup) | Out-Null
 if((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before){throw 'Backup esuat. Nu modific nimic.'}
 Invoke-Adb -Arguments @('push',$local,$temp) | Out-Null
 if((Remote-Sha $temp) -ne $desired){throw 'Copiere temporara invalida, cache-ul original este neatins.'}
 Invoke-Adb -Arguments @('shell','mv','-f',$temp,$remote) | Out-Null
 if((Remote-Sha $remote) -ne $desired){throw 'Checksum dupa inlocuire invalid.'}
 Write-Host ('Backup: '+$backup)
} else { Write-Host 'BIN-ul dorit era deja prezent in cache. Problema este sincronizarea BLE.' }
Write-Host 'CACHE_SHA256:' (Remote-Sha $remote)
Invoke-Adb -Arguments @('shell','monkey','-p',$pkg,'-c','android.intent.category.LAUNCHER','1') | Out-Null
$after=Remote-Sha $remote
if($after -ne $desired){throw 'GloryFit a rescris fisierul din cache dupa deschidere. Nu sincroniza.'}
Write-Host 'CACHE_STAGE_OK: fisierul modificat este in cache, NU pe ceas.'
if($Restore){Write-Host 'In GloryFit, sincronizeaza cadranul portocaliu original daca este necesar.'}
else{
 Write-Host 'ACUM in GloryFit: Device -> Watch faces -> selecteaza cadranul ORIGINAL portocaliu/rosu cu 02:08 -> Sync.'
 Write-Host 'Daca acel cadran era activ inainte, sincronizeaza MAI INTAI un ALT cadran din aplicatie, apoi revino la cel portocaliu si apasa Sync.'
 Write-Host 'Nu folosi Upgrade de firmware. Un BIN de 421 KB poate fi respins de firmware.'
}
