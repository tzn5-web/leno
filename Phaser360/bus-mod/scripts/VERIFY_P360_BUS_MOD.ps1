#requires -version 5.1
$ErrorActionPreference = 'Stop'

$parent = Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -like 'PCI\VEN_8086&DEV_3198*' } |
    Select-Object -First 1

if (-not $parent) { throw '8086:3198 missing.' }

Write-Host "PARENT: $($parent.Name)"
Write-Host "  ID:      $($parent.PNPDeviceID)"
Write-Host "  SERVICE: $($parent.Service)"
Write-Host "  STATUS:  $($parent.Status) / $($parent.ConfigManagerErrorCode)"

$all = Get-CimInstance Win32_PnPEntity
$dsp = $all | Where-Object {
    $_.PNPDeviceID -like 'CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198*' -or
    $_.PNPDeviceID -like 'P360AUDIO\ADSP_GEMINILAKE*'
}

Write-Host ''
if ($dsp) {
    Write-Host 'DSP CHILD FOUND:'
    $dsp | Format-List Name,PNPDeviceID,Status,ConfigManagerErrorCode,Service
} else {
    Write-Host 'DSP child not found under expected CSAUDIO/P360 identity.'
}

Write-Host ''
Write-Host 'RELATIONS:'
& pnputil.exe /enum-devices /instanceid "$($parent.PNPDeviceID)" /relations
Write-Host ''
Write-Host 'No DSP firmware boot and no audio playback were attempted.'
