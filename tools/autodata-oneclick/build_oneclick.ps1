[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ExtractedRoot,
  [Parameter(Mandatory=$true)][string]$Manifest,
  [Parameter(Mandatory=$true)][string]$ReviewRecord,
  [string]$OutputDir = (Join-Path $env:TEMP "AutodataPrivateBuild")
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
# The review record must stay private; this is a human attestation, not an activation check.
$review=(Resolve-Path -LiteralPath $ReviewRecord).Path
$repoRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
if ($review.StartsWith($repoRoot + "\",[StringComparison]::OrdinalIgnoreCase)) {
  throw "REVIEW_RECORD_MUST_REMAIN_PRIVATE"
}
& python (Join-Path $PSScriptRoot "release_gate.py") --record $review --stage build
if ($LASTEXITCODE -ne 0) { throw "PRIVATE_REVIEW_REQUIRED" }
$root=(Resolve-Path -LiteralPath $ExtractedRoot).Path
$manifestPath=(Resolve-Path -LiteralPath $Manifest).Path
$program=Join-Path $root "ADCDA2"
& python (Join-Path $PSScriptRoot "verify_payload.py") --production --source $root --manifest $manifestPath --output (Join-Path $PSScriptRoot "payload_verification.json")
if ($LASTEXITCODE -ne 0) {throw "PAYLOAD_VERIFICATION_FAILED"}
if (-not (Get-Command Start-MpScan -ErrorAction SilentlyContinue)) {
    throw "DEFENDER_UNAVAILABLE: source cannot be approved automatically"
}
try {Start-MpScan -ScanType CustomScan -ScanPath $program -ErrorAction Stop | Out-Null}
catch {throw "DEFENDER_SCAN_FAILED: $($_.Exception.Message)"}
$threats=@(Get-MpThreatDetection -ErrorAction Stop)
foreach ($threat in $threats) {
    foreach ($resource in @($threat.Resources)) {
        if (([string]$resource).StartsWith($program,[StringComparison]::OrdinalIgnoreCase)) {
            throw "DEFENDER_DETECTION: $resource"
        }
    }
}
Write-Host "DEFENDER_SCAN=PASS (no path-matching detection reported)"
$compiler=$null
$dirs=@($env:ProgramFiles,[Environment]::GetEnvironmentVariable("ProgramFiles(x86)")) | Where-Object {$_}
foreach ($dir in $dirs) {
    foreach ($version in @("Inno Setup 7","Inno Setup 6")) {
        $candidate=Join-Path $dir "$version\ISCC.exe"
        if (Test-Path -LiteralPath $candidate) {$compiler=$candidate;break}
    }
    if ($compiler) {break}
}
if (-not $compiler) {throw "ISCC_NOT_FOUND: install Inno Setup 6.5.2+ or 7"}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$privateOutput=(Resolve-Path -LiteralPath $OutputDir).Path
if ($privateOutput.StartsWith($repoRoot + "\",[StringComparison]::OrdinalIgnoreCase)) {
  throw "PROPRIETARY_OUTPUT_MUST_REMAIN_OUTSIDE_PUBLIC_REPO"
}
$env:AUTODATA_SOURCE=$program
$env:AUTODATA_OUTPUT=(Resolve-Path -LiteralPath $OutputDir).Path
& $compiler (Join-Path $PSScriptRoot "oneclick.iss")
if ($LASTEXITCODE -ne 0) {throw "ISCC_COMPILE_FAILED: $LASTEXITCODE"}
$exe=Join-Path $env:AUTODATA_OUTPUT "Autodata_3_45_OneClick_Setup.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {throw "EXE_NOT_CREATED"}
if ((Get-Item $exe).Length -ge 4GB) {throw "EXE_EXCEEDS_4GB"}
$hash=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host "ONE_EXE_BUILD=PASS path=$exe sha256=$hash"
Write-Warning "No vendor activation bypass; a valid license may still be required."
