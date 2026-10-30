# Build a single Windows setup EXE from a trusted, properly licensed ADCDA2 directory.
# This never runs application executables or changes activation/registry settings.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PayloadRoot,
    [string]$OutputDir = (Join-Path $PSScriptRoot 'dist'),
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$iss = Join-Path $PSScriptRoot 'installer.iss'
$stager = Join-Path $PSScriptRoot 'prepare_payload.py'
$manifest = Join-Path $PSScriptRoot 'payload-allowlist.json'
$stage = Join-Path ([IO.Path]::GetTempPath()) ('autodata-stage-' + [guid]::NewGuid().ToString('N'))
$compiler = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $found = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
    if ($null -eq $found) {
        throw 'Inno Setup 6 (ISCC.exe) is required to compile the installer.'
    }
    $compiler = $found.Source
}

New-Item -ItemType Directory -Path $stage -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
try {
    & $Python $stager --source $PayloadRoot --staging $stage --allowlist $manifest
    if ($LASTEXITCODE -ne 0) { throw 'Payload validation failed; installer not built.' }

    $env:AUTODATA_STAGED = $stage
    $env:AUTODATA_OUTPUT_DIR = (Resolve-Path -LiteralPath $OutputDir).Path
    & $compiler $iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

    $exe = Join-Path $env:AUTODATA_OUTPUT_DIR 'Autodata_3_45_Licensed_Setup.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw 'Compiled setup EXE was not found.' }
    $digest = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    Write-Host ('SETUP_CREATED=' + $exe)
    Write-Host ('SETUP_SHA256=' + $digest)
    Write-Host 'LICENSE_ACTIVATION=REQUIRES_GENUINE_VENDOR_METHOD'
}
finally {
    Remove-Item Env:AUTODATA_STAGED -ErrorAction SilentlyContinue
    Remove-Item Env:AUTODATA_OUTPUT_DIR -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
