#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: audit_patches.py <build-workdir>")

work = Path(sys.argv[1])
errors: list[str] = []


def read(rel: str) -> str:
    path = work / rel
    if not path.is_file():
        errors.append(f"missing dependency source: {rel}")
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def require(haystack: str, needles: list[str], label: str) -> None:
    for needle in needles:
        if needle not in haystack:
            errors.append(f"{label} missing invariant: {needle}")


ads = read("YouMod/Files/Ads.x")
background = read("YouMod/Files/Others.x")
sponsor = read("YouMod/Files/SponsorBlock.x")
sideload = read("YouMod/Files/Sideloading.x")
pip_header = read("YouPiP/Header.h")
pip_tweak = read("YouPiP/Tweak.x")
ryd_makefile = read("Return-YouTube-Dislikes/Makefile")

require(
    ads,
    [
        "playerAdsArray",
        "adSlotsArray",
        "createAdsPlaybackCoordinator",
        "YTAdsInnerTubeContextDecorator",
        "isAdRenderer",
    ],
    "YouMod ad layer",
)
require(
    background,
    [
        "playableInBackground",
        "isPlayableInBackground",
        "YTPlaybackData",
        "YTIPlayerResponse",
    ],
    "YouMod background layer",
)
require(
    sponsor,
    [
        "fetchSegmentsForVideoID",
        "sbPerformSkip",
        "sbCheckSegmentsAtCurrentTime",
    ],
    "YouMod SponsorBlock layer",
)
require(
    sideload,
    [
        "SSOKeychainHelper",
        "GULKeychainStorage",
        "accessGroupID",
        "bundleIdentifier",
        "containerURLForSecurityApplicationGroupIdentifier",
        "SSOConfiguration",
    ],
    "YouMod sideload/account compatibility layer",
)
require(
    pip_header + pip_tweak,
    [
        "YouPiPEnabled",
        "AVPictureInPicture",
    ],
    "YouPiP layer",
)
require(
    ryd_makefile,
    ["YouTubeDislikesReturn"],
    "Return YouTube Dislikes layer",
)

if errors:
    print("VANCEDIOS DEPENDENCY CONTRACT AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("VANCEDIOS DEPENDENCY CONTRACT AUDIT PASSED")
print(" - ad response/feed/player hooks present")
print(" - background playback hooks present")
print(" - SponsorBlock runtime hooks present")
print(" - sideload Google/keychain compatibility hooks present")
print(" - native PiP patch present")
print(" - dislike module present")
