#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VANCED = ROOT / "VancedIOS"
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


manifest = json.loads((VANCED / "manifest.json").read_text(encoding="utf-8"))
core = (VANCED / "Core" / "VancedIOSCore.xm").read_text(encoding="utf-8")
readme = (VANCED / "README.md").read_text(encoding="utf-8")

require(
    manifest.get("architecture") == "youtube-official-plus-injected-modular-tweaks",
    "architecture must remain host-app + injected modular patches",
)
require(
    manifest.get("target", {}).get("bundle_id") == "com.google.ios.youtube",
    "default host bundle id changed",
)
require(
    manifest.get("target", {}).get("tested_youtube_version") == "21.18.4",
    "tested YouTube host version must remain explicitly pinned",
)

sha40 = re.compile(r"^[0-9a-f]{40}$")
for required_dep in [
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
]:
    require(
        required_dep in manifest.get("dependencies", {}),
        f"required dependency missing from manifest: {required_dep}",
    )

for name, dep in manifest.get("dependencies", {}).items():
    commit = dep.get("commit")
    require(
        isinstance(commit, str) and bool(sha40.fullmatch(commit)),
        f"{name} is not pinned to an exact 40-char commit",
    )

for key in [
    "YouModEnablesBackgroundPlayback",
    "YouModSBEnabled",
    "YouModSBShowButton",
    "YouModSBSegmentsInPlayer",
    "YouPiPEnabled",
    "YouModBlockUpgradeDialogs",
    "YouModHideAreYouThereDialog",
    "YouModFixPlaybackIssues",
    "YouModTapToSeek",
    "YouModAddExtraSpeed",
    "YouModHidePaidPromoOverlay",
]:
    require(key in core, f"Vanced default missing: {key}")

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

build_script = (VANCED / "Scripts" / "build_patches.sh").read_text(encoding="utf-8")
inject_script = (VANCED / "Scripts" / "inject.sh").read_text(encoding="utf-8")

for token in [
    "YTVideoOverlay",
    "YTUHD",
    "ytvideooverlay.deb",
    "ytuhd.deb",
]:
    require(token in build_script, f"patch build is incomplete: missing {token}")
    require(token in inject_script, f"IPA injection is incomplete: missing {token}")

for token in [
    "tested_youtube_version",
    "cryptid",
    "com.google.ios.youtube",
]:
    require(token in inject_script, f"host validation missing from injector: {token}")

workflow_dir = ROOT / ".github" / "workflows"
for workflow in workflow_dir.glob("vanced-ios-*.yml"):
    text = workflow.read_text(encoding="utf-8").lower()
    require(
        "apps.apple.com" not in text,
        f"{workflow.name} contains a fixed App Store host download reference",
    )

if errors:
    print("VANCEDIOS ARCHITECTURE AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("VANCEDIOS ARCHITECTURE AUDIT PASSED")
print(" - official YouTube remains the host application")
print(" - patch layers are modular and dependency commits are pinned")
print(" - Vanced defaults cover background/SponsorBlock/player resilience")
print(" - PiP/UHD helper dependencies are mandatory and audited")
print(" - injector validates the official decrypted host and tested version")
print(" - repository contains no YouTube IPA/app binary")
