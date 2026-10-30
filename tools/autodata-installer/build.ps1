# Build a Windows file installer only from an authorized, complete source tree.
# No vendor executables are run; no licensing/registry modifications are made.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PayloadRoot,
    [Parameter(Mandatory = $true)][string]$Inventory,
    [Parameter(Mandatory = $true)][switch]$AuthorizedUseConfirmed,
    [string]$OutputDir = (Join-Path $PSScriptRoot 'dist'),
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$iss = Join-Path $PSScriptRoot 'installer.iss'
$stager = Join-Path $PSScriptRoot 'prepare_payload.py'
$verifier = Join-Path $PSScriptRoot 'verify_original_manifest.py'
$allowlist = Join-Path $PSScriptRoot 'payload-allowlist.json'
$stage = Join-Path ([IO.Path]::GetTempPath()) ('autodata-stage-' + [guid]::NewGuid().ToString('N'))
if (-not $AuthorizedUseConfirmed) {
    throw 'AuthorizedUseConfirmed is required: only package files you are legally entitled to use.'
}
$root = (Resolve-Path -LiteralPath $PayloadRoot -ErrorAction Stop).Path
if ([IO.Path]::GetFileName($root).Equals('ADCDA2', [StringComparison]::OrdinalIgnoreCase)) {
    $root = Split-Path -Parent $root
}
$program = Join-Path $root 'ADCDA2'
if (-not (Test-Path -LiteralPath $program -PathType Container)) {
    throw 'ADCDA2 folder missing from supplied source.'
}
$manifest = (Resolve-Path -LiteralPath $Inventory -ErrorAction Stop).Path

New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
# Hash-verify ALL 105 original files, in exact original 64 MiB fragment order.
# INVENTAR.json stays local/private; it is never uploaded to GitHub.
& $Python $verifier --source $root --manifest $manifest --output (Join-Path $stage 'verified.json')
if ($LASTEXITCODE -ne 0) {
    throw 'PRIVATE_INVENTORY_SHA256_VERIFICATION_FAILED: refusing to package.'
}
Write-Host 'ORIGINAL_INVENTORY_SHA256=PASS'
Remove-Item -LiteralPath (Join-Path $stage 'verified.json') -Force -ErrorAction Stop

# Windows Defender is a necessary check, not a guarantee that a file is safe.
if (-not (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue) -or
    -not (Get-Command Start-MpScan -ErrorAction SilentlyContinue) -or
    -not (Get-Command Get-MpThreatDetection -ErrorAction SilentlyContinue)) {
    throw 'DEFENDER_UNAVAILABLE: cannot approve source for packaging.'
}
$status = Get-MpComputerStatus -ErrorAction Stop
if (-not $status.AntivirusEnabled -or -not $status.AMServiceEnabled) {
    throw 'DEFENDER_DISABLED: cannot approve source for packaging.'
}
try {
    Start-MpScan -ScanType CustomScan -ScanPath $program -ErrorAction Stop | Out-Null
}
catch {
    throw ('DEFENDER_SCAN_FAILED: ' + $_.Exception.Message)
}
$detections = @(Get-MpThreatDetection -ErrorAction Stop)
foreach ($detection in $detections) {
    if ($null -eq $detection) { continue }
    foreach ($resource in @($detection.Resources)) {
        if ($null -ne $resource -and
            ([string]$resource).IndexOf($program, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw ('DEFENDER_DETECTION: ' + [string]$resource)
        }
    }
}
Write-Host 'DEFENDER_CUSTOM_SCAN=PASS (no source-path detection reported)'

$compiler = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $found = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
    if ($null -eq $found) {
        throw 'Inno Setup 6 (ISCC.exe) is required to compile the installer.'
    }
    $compiler = $found.Source
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    & $Python $stager --source $root --staging $stage --allowlist $allowlist
    if ($LASTEXITCODE -ne 0) { throw 'Payload staging failed; installer not built.' }

    $env:AUTODATA_STAGED = $stage
    $env:AUTODATA_OUTPUT_DIR = (Resolve-Path -LiteralPath $OutputDir).Path
    & $compiler $iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

    $exe = Join-Path $env:AUTODATA_OUTPUT_DIR 'Autodata_3_45_Licensed_Setup.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw 'Compiled setup EXE was not found.'
    }
    $digest = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    Write-Host ('SETUP_CREATED=' + $exe)
    Write-Host ('SETUP_SHA256=' + $digest)
    Write-Host 'APP_RUNTIME_AND_GENUINE_LICENSE=NOT_VERIFIED_BY_BUILD'
}
finally {
    Remove-Item Env:AUTODATA_STAGED -ErrorAction SilentlyContinue
    Remove-Item Env:AUTODATA_OUTPUT_DIR -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
