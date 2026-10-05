#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VANCED = ROOT / "VancedIOS"
WORKFLOWS = ROOT / ".github" / "workflows"
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def read(path: Path) -> str:
    require(path.is_file(), f"required file missing: {path.relative_to(ROOT)}")
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


manifest = json.loads(read(VANCED / "manifest.json") or "{}")
core = read(VANCED / "Core" / "VancedIOSCore.xm")
core_makefile = read(VANCED / "Core" / "Makefile")
core_control = read(VANCED / "Core" / "control")
core_filter = read(VANCED / "Core" / "VancedIOSCore.plist")
readme = read(VANCED / "README.md")
build_script = read(VANCED / "Scripts" / "build_patches.sh")
inject_script = read(VANCED / "Scripts" / "inject.sh")
validator = read(VANCED / "Scripts" / "validate_ipa.py")
runner = read(VANCED / "Scripts" / "stage_runner.py")

target = manifest.get("target", {})
validation = manifest.get("host_validation", {})
payload = manifest.get("payload", {})
deps = manifest.get("dependencies", {})

require(
    manifest.get("architecture") == "youtube-official-plus-injected-modular-tweaks",
    "architecture must remain official YouTube host + injected modular patches",
)
require(
    target.get("bundle_id") == "com.google.ios.youtube",
    "official YouTube bundle id must remain pinned",
)
require(target.get("minimum_ios") == "15.0", "minimum iOS must be 15.0")
require(
    bool(re.fullmatch(r"\d+\.\d+\.\d+", str(target.get("tested_youtube_version") or ""))),
    "tested YouTube host version must be an explicit semantic version",
)
require(validation.get("strict_version") is True, "strict tested-version validation must be enabled")
require(validation.get("require_decrypted") is True, "host must be required to be decrypted")
require("arm64" in validation.get("required_arches", []), "host arm64 validation missing")
require(
    "audio" in validation.get("required_background_modes", []),
    "UIBackgroundModes audio validation missing",
)

expected_dylibs = {
    "YouMod.dylib",
    "YTVideoOverlay.dylib",
    "YouPiP.dylib",
    "YTUHD.dylib",
    "YouTubeDislikesReturn.dylib",
    "VancedIOSCore.dylib",
}
require(
    set(payload.get("required_dylibs", [])) == expected_dylibs,
    "required injected dylib contract is incomplete or changed",
)

required_dependencies = {
    "YouMod",
    "YTVideoOverlay",
    "YouPiP",
    "YTUHD",
    "ReturnYouTubeDislikes",
    "YouTubeHeader",
    "PSHeader",
    "Theos",
    "iOSSDKs",
    "Cyan",
}
require(
    required_dependencies.issubset(deps),
    "required dependency missing: "
    + ", ".join(sorted(required_dependencies - set(deps))),
)

sha40 = re.compile(r"^[0-9a-f]{40}$")
for name, dep in deps.items():
    commit = dep.get("commit")
    require(
        isinstance(commit, str) and bool(sha40.fullmatch(commit)),
        f"{name} is not pinned to an immutable 40-char commit",
    )
    require(
        isinstance(dep.get("repo"), str) and dep.get("repo", "").startswith("https://github.com/"),
        f"{name} repository must be an explicit GitHub HTTPS URL",
    )

for key in [
    "YouModEnablesBackgroundPlayback",
    "YouModFixPlaybackIssues",
    "YouModSBEnabled",
    "YouModSBShowButton",
    "YouModSBSegmentsInPlayer",
    "YouPiPEnabled",
    "YouModWifiQualityIndex",
    "YouModCellQualityIndex",
    "YouModLowPowerQualityIndex",
    "YouModAutoSpeedIndex",
    "YouModTapToSeek",
    "YouModAddExtraSpeed",
    "YouModHidePaidPromoOverlay",
]:
    require(key in core, f"Vanced default/integration key missing: {key}")

for forbidden in [
    "MPRemoteCommandCenter",
    "AVAudioSession",
    "applicationDidEnterBackground",
    "applicationWillEnterForeground",
    "applicationWillResignActive",
    "applicationDidBecomeActive",
]:
    require(
        forbidden not in core,
        f"VancedIOSCore must not become a competing media/lifecycle authority: {forbidden}",
    )

require("TARGET := iphone:clang:latest:15.0" in core_makefile, "core build target must be iOS 15.0")
require("ARCHS = arm64" in core_makefile, "core must build arm64")
require("firmware (>= 15.0)" in core_control, "core control minimum firmware must be 15.0")
require("com.google.ios.youtube" in core_filter, "core substrate filter must target official YouTube")

for phrase in [
    "user-supplied",
    "official YouTube UI",
    "ad filtering",
    "background",
    "SponsorBlock",
    "Picture in Picture",
]:
    require(phrase.lower() in readme.lower(), f"architecture README missing: {phrase}")

for path in ROOT.rglob("*"):
    if ".git" in path.parts:
        continue
    lower = path.name.lower()
    if path.is_file() and lower.endswith(".ipa"):
        errors.append(f"proprietary/binary host artifact present in repo: {path.relative_to(ROOT)}")
    if path.is_dir() and lower == "youtube.app":
        errors.append(f"proprietary host app present in repo: {path.relative_to(ROOT)}")

for token in [
    "head_matches",
    "clone_at",
    "clone_sdk_at",
    "YouMod",
    "YTVideoOverlay",
    "YouPiP",
    "YTUHD",
    "ReturnYouTubeDislikes",
    "YouTubeHeader",
    "PSHeader",
    "THEOS_PACKAGE_SCHEME=rootless",
]:
    require(token in build_script, f"deterministic patch build invariant missing: {token}")

for token in [
    "validate_ipa.py",
    'host "$BASE_IPA"',
    'output "$OUTPUT"',
    "youmod.deb",
    "ytvideooverlay.deb",
    "youpip.deb",
    "ytuhd.deb",
    "return-youtube-dislikes.deb",
    "vancedios-core.deb",
]:
    require(token in inject_script, f"injector invariant missing: {token}")

for token in [
    "cryptid",
    "LC_LOAD_DYLIB",
    "tested_youtube_version",
    "UIBackgroundModes",
    "arm64",
    "com.google.ios.youtube",
]:
    require(token in validator, f"strict IPA validator missing invariant: {token}")

for token in [
    "workflow.pinned-actions",
    "core.single-media-authority",
    "packages.complete",
    '"YouTubeHeader": "theos/include/YouTubeHeader"',
    '"PSHeader": "theos/include/PSHeader"',
]:
    require(token in runner, f"stage runner missing audit dimension: {token}")

workflow_paths = sorted(WORKFLOWS.glob("vanced-ios-*.yml"))
require(bool(workflow_paths), "no VancedIOS GitHub Actions workflows found")
for workflow in workflow_paths:
    text = read(workflow)
    lower = text.lower()
    require(
        "apps.apple.com" not in lower,
        f"{workflow.name} must not download an App Store host",
    )
    require(
        re.search(
            r"(?m)^permissions:\s*\n(?:[ \t].*\n)*?[ \t]+contents:\s*read\s*$",
            text,
        )
        is not None,
        f"{workflow.name} must declare least-privilege contents: read",
    )
    for match in re.finditer(r"uses:\s*([^\s@]+)@([^\s#]+)", text):
        require(
            bool(sha40.fullmatch(match.group(2))),
            f"{workflow.name} has mutable action ref: {match.group(1)}@{match.group(2)}",
        )

inject_workflow = read(WORKFLOWS / "vanced-ios-inject.yml")
cyan_pin = deps.get("Cyan", {}).get("commit", "")
require(
    bool(cyan_pin) and f"pyzule-rw.git@{cyan_pin}" in inject_workflow,
    "injection workflow Cyan/pyzule pin must match manifest",
)

if errors:
    print("VANCEDIOS ARCHITECTURE AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("VANCEDIOS ARCHITECTURE AUDIT PASSED")
print(" - official YouTube remains the host application")
print(" - minimum iOS and arm64/rootless build contract are aligned")
print(" - every external dependency is pinned to an immutable commit")
print(" - Core does not compete with YouTube for media/lifecycle authority")
print(" - background/PiP/SponsorBlock/quality/speed defaults are wired")
print(" - injector requires an exact tested decrypted YouTube host")
print(" - output IPA validation covers dylibs and Mach-O load commands")
print(" - workflows use least privilege and immutable action revisions")
print(" - repository contains no YouTube IPA/app binary")
