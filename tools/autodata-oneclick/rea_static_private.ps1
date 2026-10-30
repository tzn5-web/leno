# Read-only REA static analysis of an authorized local PE image.
# No target execution, no license utilities, no driver installation, no cloud upload.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$SourceExe,
  [Parameter(Mandatory=$true)][string]$ExpectedSha256,
  [Parameter(Mandatory=$true)][string]$OutputDir,
  [string]$ReaCli = "rea",
  [switch]$SkipDesktop
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$source = (Resolve-Path -LiteralPath $SourceExe).Path
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "PE_SOURCE_MISSING" }
if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "EXPECTED_SHA256_INVALID" }
$actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
  throw "SOURCE_SHA256_MISMATCH expected=$ExpectedSha256 actual=$actual"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "NODE_MISSING" }
$nodeText = (& node --version).Trim().TrimStart('v')
$nodeVer = [version]$nodeText
$compatible = ($nodeVer.Major -eq 22 -and $nodeVer -ge [version]"22.23.4") -or
              ($nodeVer.Major -eq 24 -and $nodeVer -ge [version]"24.22.1") -or
              ($nodeVer -ge [version]"26.12.1")
if (-not $compatible) { throw "REA_NODE_UNSUPPORTED: $nodeText" }
if (-not (Get-Command $ReaCli -ErrorAction SilentlyContinue)) { throw "REA_CLI_MISSING" }

# Refuse report output within this public repository checkout.
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$dest = (Resolve-Path -LiteralPath $OutputDir).Path
if ($dest.TrimEnd('\').StartsWith($repoRoot.TrimEnd('\') + '\',[StringComparison]::OrdinalIgnoreCase) -or
    $dest.TrimEnd('\') -eq $repoRoot.TrimEnd('\')) {
  throw "PRIVATE_REPORTS_MUST_BE_OUTSIDE_REPOSITORY"
}
$checks = @(
  @{ name="pe-imports"; args=@("inspect-pe-imports",$source,"--json","--full-output") },
  @{ name="pe-certificates"; args=@("inspect-pe-certificates",$source,"--json","--full-output") }
)
if (-not $SkipDesktop) {
  $checks += @{ name="desktop-application"; args=@("inspect-desktop-application",(Split-Path -Parent $source),"--json","--full-output") }
}
foreach ($check in $checks) {
  $out = Join-Path $dest ("rea_" + $check.name + ".json")
  $err = Join-Path $dest ("rea_" + $check.name + ".stderr.txt")
  $commandArgs = [string[]]$check.args
  & $ReaCli @commandArgs 1> $out 2> $err
  if ($LASTEXITCODE -ne 0) { throw "REA_COMMAND_FAILED:$($check.name) code=$LASTEXITCODE" }
  try { $null = Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json -Depth 100 }
  catch { throw "REA_INVALID_JSON:$($check.name):$($_.Exception.Message)" }
  if ($check.name -eq "pe-imports") {
    $text = Get-Content -LiteralPath $out -Raw -Encoding UTF8
    if (-not $text.Contains($actual)) { throw "REA_PE_EVIDENCE_HASH_MISSING" }
  }
  Write-Host "REA_$($check.name.ToUpperInvariant())=PASS"
}
$receipt = @{
  mode = "read_only_static"
  target_name = [IO.Path]::GetFileName($source)
  target_sha256 = $actual
  rea_version = (& $ReaCli --version | Out-String).Trim()
  node_version = $nodeText
  checks = @($checks | ForEach-Object {$_.name})
  scope = "local_private_no_upload_no_target_execution"
  limitations = "Static imports and directory inventory do not prove license, vendor authenticity, runtime compatibility, or absence of malware."
}
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $dest "rea_receipt.json") -Encoding UTF8
Write-Host "REA_PRIVATE_STATIC_AUDIT=PASS target_sha256=$actual reports=$dest"
