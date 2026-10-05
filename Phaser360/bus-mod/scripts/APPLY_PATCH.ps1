$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RepoRoot = Resolve-Path (Join-Path $Root "..\..")
$Upstream = Join-Path $RepoRoot "_upstream\sklhdaudbus"
$Patch = Join-Path $Root "patches\0001-phaser360-gemini-lake-bridge.patch"
$Commit = "5477b93a3b68c474819abf2094a49d0e2d8d9799"

if (Test-Path $Upstream) {
    Remove-Item -Recurse -Force $Upstream
}
New-Item -ItemType Directory -Force -Path (Split-Path $Upstream) | Out-Null

git clone https://github.com/coolstar/sklhdaudbus.git $Upstream
git -C $Upstream checkout --detach $Commit
git -C $Upstream apply --check $Patch
git -C $Upstream apply $Patch

Write-Host "PHASER360 patch applied to pinned CoolStar commit $Commit"
git -C $Upstream diff --check
git -C $Upstream diff -- sklhdaudbus/sklhdaudbus.inf sklhdaudbus/buspdo.cpp
