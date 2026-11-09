# iHunt Watch6T: GloryFit dial cache stage + reversible backup.
# Run locally from private HOLO V3 ZIP. NEVER use the firmware-upgrade menu.
[CmdletBinding()] param([switch]$Restore)
Set-StrictMode -Version 2
$ErrorActionPreference='Stop'
$desktop=[Environment]::GetFolderPath('Desktop')
$adb=@((Join-Path $desktop 'platform-tools\adb.exe'),'E:\tableta lenovo\platform-tools\adb.exe') |
     Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
if(-not $adb){$cmd=Get-Command adb.exe -ErrorAction SilentlyContinue;if($cmd){$adb=$cmd.Source}}
if(-not $adb){throw 'ADB missing; install Android Platform Tools.'}
function ADB([string[]]$Arguments) {
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue'
    try { $out=@(& $adb @Arguments 2>&1 | ForEach-Object { [string]$_ }); $code=$LASTEXITCODE }
    finally { $ErrorActionPreference=$old }
    if($code -ne 0){throw "ADB error ($code): $($out -join ' ')"}
    return ($out -join [Environment]::NewLine)
}
$list=ADB -Arguments @('devices')
if(@($list -split [char]10 | Where-Object {$_ -match '^\S+\s+device\s*$'}).Count -ne 1){throw "Connect exactly one authorized phone: $list"}
if((ADB -Arguments @('shell','pm','path','com.yc.gloryfit')) -notmatch 'package:'){throw 'GloryFit not installed'}
$m=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$original=Join-Path $PSScriptRoot 'D1898001_ORIGINAL.bin'
$modified=Join-Path $PSScriptRoot 'D1898001_HOLO_V3.bin'
$sourceHash=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLower()
if($sourceHash -ne $m.input_sha256){throw 'Source SHA256 mismatch'}
$upload=if($Restore){$original}else{$modified}
$want=if($Restore){$m.input_sha256}else{$m.output_sha256}
if((Get-FileHash -LiteralPath $upload -Algorithm SHA256).Hash.ToLower() -ne $want){throw 'Payload SHA256 mismatch'}
$remote='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin'
$tempRemote='/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin.holo_temp'
function RemoteHash([string]$path) {
    $line=ADB -Arguments @('shell','sha256sum',$path)
    $match=[regex]::Match($line,'^([0-9a-fA-F]{64})\s+')
    if(-not $match.Success){throw "Cannot verify remote SHA256: $line"}
    return $match.Groups[1].Value.ToLower()
}
$current=RemoteHash $remote
if($current -eq $want){Write-Host 'Desired cache file is already present.';exit 0}
$allowed=if($Restore){$m.output_sha256}else{$m.input_sha256}
if($current -ne $allowed){throw 'Unexpected cache content; refusing to overwrite.'}
$dir=Join-Path $desktop 'Watch6T_BACKUP'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$backup=Join-Path $dir ('D1898001_'+(Get-Date -Format yyyyMMdd_HHmmss)+'.bin')
ADB -Arguments @('pull',$remote,$backup) | Out-Null
if((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLower() -ne $current){throw 'Backup hash mismatch'}
ADB -Arguments @('push',$upload,$tempRemote) | Out-Null
if((RemoteHash $tempRemote) -ne $want) {
    try{ADB -Arguments @('shell','rm','-f',$tempRemote) | Out-Null}catch{}
    throw 'Uploaded temp mismatch: original left unchanged'
}
ADB -Arguments @('shell','mv','-f',$tempRemote,$remote) | Out-Null
if((RemoteHash $remote) -ne $want){throw 'Final hash mismatch: do not synchronize'}
Write-Host ('Cache staged. Backup: '+$backup)
if($Restore){Write-Host 'Now sync the original face in GloryFit.'}
else{
 Write-Host 'GloryFit -> Device -> Watch face settings -> My faces -> resync the SAME downloaded face.'
 Write-Host 'Do not use Firmware upgrade. Watch compatibility remains untested.'
}
