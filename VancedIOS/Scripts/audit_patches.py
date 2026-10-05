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


def require_all(haystack: str, needles: list[str], label: str) -> None:
    for needle in needles:
        if needle not in haystack:
            errors.append(f"{label} missing invariant: {needle}")


ads = read("YouMod/Files/Ads.x")
background = read("YouMod/Files/Others.x")
sponsor = read("YouMod/Files/SponsorBlock.x")
sideload = read("YouMod/Files/Sideloading.x")
headers = read("YouMod/Files/Headers.h")
settings = read("YouMod/Files/Settings.x")
player = read("YouMod/Files/Player.x")
shorts = read("YouMod/Files/Shorts.x")
pip_header = read("YouPiP/Header.h")
pip_tweak = read("YouPiP/Tweak.x")
overlay_makefile = read("YTVideoOverlay/Makefile")
overlay_tweak = read("YTVideoOverlay/Tweak.x")
uhd_makefile = read("YTUHD/Makefile")
uhd_tweak = read("YTUHD/Tweak.xm")
ryd_makefile = read("Return-YouTube-Dislikes/Makefile")

require_all(
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
require_all(
    background,
    [
        "playableInBackground",
        "isPlayableInBackground",
        "YTPlaybackData",
        "YTIPlayerResponse",
    ],
    "YouMod background layer",
)
require_all(
    sponsor,
    [
        "fetchSegmentsForVideoID",
        "sbPerformSkip",
        "sbCheckSegmentsAtCurrentTime",
    ],
    "YouMod SponsorBlock layer",
)
require_all(
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
require_all(
    headers,
    [
        '#define BackgroundPlayback @"YouModEnablesBackgroundPlayback"',
        '#define SBEnabled @"YouModSBEnabled"',
        '#define SBShowButton @"YouModSBShowButton"',
        '#define WifiQualityIndex @"YouModWifiQualityIndex"',
        '#define CellQualityIndex @"YouModCellQualityIndex"',
        '#define LowPowerQualityIndex @"YouModLowPowerQualityIndex"',
        '#define AutoSpeedIndex @"YouModAutoSpeedIndex"',
        '#define FixPlaybackIssues @"YouModFixPlaybackIssues"',
    ],
    "YouMod preference ABI",
)
require_all(
    settings + player,
    [
        "WifiQualityIndex",
        "CellQualityIndex",
        "LowPowerQualityIndex",
        "YouModAutoQuality",
        "AutoSpeedIndex",
        "YouModSetAutoSpeed",
    ],
    "YouMod persistent quality/speed layer",
)
require_all(
    shorts,
    [
        "enableShortsVideoQualityPicker",
        "AutoSpeedIndex",
        "YouModSetAutoSpeed",
    ],
    "YouMod Shorts quality/speed layer",
)
require_all(
    pip_header + pip_tweak,
    [
        '#define EnabledKey @"YouPiPEnabled"',
        "AVPictureInPicture",
        "registerDefaults",
    ],
    "YouPiP layer",
)
require_all(
    overlay_makefile + overlay_tweak,
    [
        "YTVideoOverlay",
        "TWEAK_NAME",
    ],
    "YTVideoOverlay layer",
)
require_all(
    uhd_makefile + uhd_tweak,
    [
        "TWEAK_NAME = YTUHD",
        "MLInnerTubePlayerConfig",
        "MLABRPolicy",
        "maxArea",
        "maxFps",
    ],
    "YTUHD quality layer",
)
require_all(
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
print(" - preference ABI matches VancedIOSCore defaults")
print(" - persistent quality/speed and Shorts hooks present")
print(" - native PiP patch present and enabled by the expected key")
print(" - shared YouTube player overlay layer present")
print(" - 2K/4K YTUHD quality layer present")
print(" - dislike module present")
