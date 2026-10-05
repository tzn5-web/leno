#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "Config" / "dependencies.lock.json"
MATRIX = ROOT / "Config" / "feature_matrix.json"
STATUS = ROOT / "Config" / "implementation_status.json"

REQUIRED_FEATURES = {
    "official_youtube_base",
    "ad_block_video",
    "ad_block_feed",
    "background_playback",
    "pause_state_preservation",
    "picture_in_picture",
    "sponsorblock",
    "return_youtube_dislike",
    "quality_memory_controls",
    "speed_memory_controls",
    "ui_shorts_controls",
    "navigation_intact",
}

COMPILED_SOURCE_FILES = [
    "Sources/VancedCore.m",
    "Sources/VancedSettings.m",
    "Sources/VancedSponsorBlock.m",
    "Sources/VancedRYD.m",
    "Sources/VancedShortsUI.m",
]

EXPECTED_IMPLEMENTATION_FILES = [
    ROOT / "Makefile",
    ROOT / "Sources" / "VancedCore.m",
    ROOT / "Sources" / "VancedSettings.m",
    ROOT / "Sources" / "VancedSponsorBlock.m",
    ROOT / "Sources" / "VancedRYD.m",
    ROOT / "Sources" / "VancedShortsUI.m",
    ROOT / "Scripts" / "build.sh",
]

LEGACY_TOKENS = [
    "WKWebView",
    "m.youtube.com",
    "BackgroundAudioHandoff",
    "PlaybackBridgeScript",
    "NativePlaybackController",
    "MPRemoteCommandCenter",
    "applicationWillResignActive",
    "applicationDidEnterBackground",
    "AVPlayer",
]

CODE_SUFFIXES = {".m", ".mm", ".xm", ".x", ".swift", ".sh", ".py"}

RESTRICTED_SERVICE_TOKENS = [
    "isPlayableInBackground",
    "playableInBackground",
    "isMonetized",
    "YTAdsInnerTubeContextDecorator",
    "YTAccountScopedAdsInnerTubeContextDecorator",
    "disableAfma",
    "Premium",
]

SETTINGS_BINARY_EVIDENCE = [
    ["YTAppSettingsPresentationData"],
    ["YTSettingsSectionItemManager"],
    ["YTSettingsSectionItem"],
    ["settingsCategoryOrder"],
    ["updateSectionForCategory:withEntry:"],
    ["switchItemWithTitle:titleDescription:accessibilityIdentifier:switchOn:switchBlock:settingItemId:"],
]

SETTINGS_SOURCE_EVIDENCE = [
    "YTAppSettingsPresentationData",
    "YTSettingsSectionItemManager",
    "settingsCategoryOrder",
    "updateSectionForCategory:withEntry:",
    "switchItemWithTitle:titleDescription:accessibilityIdentifier:switchOn:switchBlock:settingItemId:",
]

BINARY_EVIDENCE = {
    "speed_memory_controls": [
        ["YTPlayerViewController"],
        ["YTMainAppVideoPlayerOverlayViewController"],
        ["setPlaybackRate:"],
        ["loadWithPlayerTransition:playbackConfig:"],
    ],
    "quality_memory_controls": [
        ["YTVideoQualitySwitchOriginalController", "YTVideoQualitySwitchRedesignedController"],
        ["MLQuickMenuVideoQualitySettingFormatConstraint"],
        ["setVideoFormatConstraint:"],
        ["qualityLabel"],
    ],
    "ui_shorts_controls": [
        ["YTIElementRenderer"],
        ["elementData"],
        ["YTPivotBarView"],
        ["setRenderer:"],
        ["pivotIdentifier"],
    ],
    "sponsorblock": [
        ["YTPlayerViewController"],
        ["playbackController:didActivateVideo:withPlaybackData:"],
        ["singleVideo:currentVideoTimeDidChange:", "potentiallyMutatedSingleVideo:currentVideoTimeDidChange:"],
        ["seekToTime:", "scrubToTime:"],
        ["currentVideoID", "contentVideoID"],
    ],
    "return_youtube_dislike": [
        ["YTQTMButton"],
        ["YTReelWatchLikesController"],
        ["updateLikeButtonWithRenderer:"],
        ["playbackController:didActivateVideo:withPlaybackData:"],
        ["currentVideoID", "contentVideoID"],
    ],
}

FEATURE_SOURCE_EVIDENCE = {
    "speed_memory_controls": [
        "YTMainAppVideoPlayerOverlayViewController",
        "setPlaybackRate:",
        "YTPlayerViewController",
        "loadWithPlayerTransition:playbackConfig:",
        "VancedLastPlaybackRate",
    ],
    "quality_memory_controls": [
        "YTVideoQualitySwitchOriginalController",
        "YTVideoQualitySwitchRedesignedController",
        "singleVideo:didSelectVideoFormat:",
        "MLQuickMenuVideoQualitySettingFormatConstraint",
        "setVideoFormatConstraint:",
        "VancedLastVideoQualityLabel",
    ],
    "ui_shorts_controls": [
        "YTIElementRenderer",
        "elementData",
        "VancedHideShortsInFeeds",
    ],
    "sponsorblock": [
        "sponsor.ajay.app/api/skipSegments/",
        "CC_SHA256",
        "playbackController:didActivateVideo:withPlaybackData:",
        "currentVideoTimeDidChange:",
        "seekToTime:",
        "VancedSponsorBlockEnabled",
    ],
    "return_youtube_dislike": [
        "returnyoutubedislikeapi.com/votes",
        "YTQTMButton",
        "YTReelWatchLikesController",
        "updateLikeButtonWithRenderer:",
        "VancedReturnYouTubeDislikeEnabled",
    ],
}


class Audit:
    def __init__(self):
        self.errors: list[str] = []
        self.incomplete: list[str] = []
        self.warnings: list[str] = []
        self.info: dict[str, object] = {}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.error(message)

    def result(self) -> dict[str, object]:
        if self.errors:
            status = "FAIL"
        elif self.incomplete:
            status = "NEEDS_REVIEW"
        else:
            status = "PASS"
        return {
            "status": status,
            "errors": self.errors,
            "incomplete": self.incomplete,
            "warnings": self.warnings,
            "info": self.info,
        }


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def is_sha40(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value or ""))


def audit_source(audit: Audit) -> None:
    audit.check(LOCK.exists(), "missing dependency lock")
    audit.check(MATRIX.exists(), "missing feature matrix")
    audit.check(STATUS.exists(), "missing implementation status")
    if audit.errors:
        return

    lock = load_json(LOCK)
    matrix = load_json(MATRIX)
    status = load_json(STATUS)

    audit.check(lock.get("schema") == 1, "dependency lock schema must be 1")
    audit.check(matrix.get("schema") == 1, "feature matrix schema must be 1")
    audit.check(status.get("schema") == 1, "implementation status schema must be 1")

    refs = [lock.get("theos", {}).get("ref", "")]
    refs.extend(item.get("ref", "") for item in lock.get("headers", []))
    refs.extend(item.get("ref", "") for item in lock.get("modules", []))
    for ref in refs:
        audit.check(is_sha40(ref), f"dependency is not pinned to an exact 40-character commit: {ref!r}")

    names = []
    names.extend(item.get("name", "") for item in lock.get("headers", []))
    names.extend(item.get("name", "") for item in lock.get("modules", []))
    audit.check(len(names) == len(set(names)), "dependency names are not unique")

    feature_ids = {item.get("id") for item in matrix.get("required", [])}
    missing = sorted(REQUIRED_FEATURES - feature_ids)
    extra = sorted(feature_ids - REQUIRED_FEATURES)
    audit.check(not missing and not extra, f"feature matrix mismatch missing={missing} extra={extra}")

    implementation = status.get("features", {})
    status_missing = sorted(REQUIRED_FEATURES - set(implementation))
    status_extra = sorted(set(implementation) - REQUIRED_FEATURES)
    audit.check(not status_missing and not status_extra,
                f"implementation status mismatch missing={status_missing} extra={status_extra}")

    accepted_states = {"implemented", "validated_static", "validated_device"}
    incomplete = {
        feature: implementation.get(feature, {}).get("state", "missing")
        for feature in sorted(REQUIRED_FEATURES)
        if implementation.get(feature, {}).get("state") not in accepted_states
    }
    if incomplete:
        audit.incomplete.append(f"required features are not yet implemented/validated: {incomplete}")

    compiled_source_text = ""
    for relative in COMPILED_SOURCE_FILES:
        source_path = ROOT / relative
        if source_path.exists():
            compiled_source_text += "\n" + source_path.read_text(encoding="utf-8", errors="ignore")

    settings_text = (ROOT / "Sources" / "VancedSettings.m").read_text(encoding="utf-8", errors="ignore") if (ROOT / "Sources" / "VancedSettings.m").exists() else ""
    absent_settings = [token for token in SETTINGS_SOURCE_EVIDENCE if token not in settings_text]
    audit.check(not absent_settings, f"source evidence missing for settings UI: {absent_settings}")

    shorts_ui_text = (ROOT / "Sources" / "VancedShortsUI.m").read_text(encoding="utf-8", errors="ignore") if (ROOT / "Sources" / "VancedShortsUI.m").exists() else ""
    shorts_ui_tokens = ["YTPivotBarView", "setRenderer:", "FEshorts", "VancedHideShortsTab"]
    absent_shorts_ui = [token for token in shorts_ui_tokens if token not in shorts_ui_text]
    audit.check(not absent_shorts_ui, f"source evidence missing for Shorts tab UI: {absent_shorts_ui}")

    for feature, tokens in FEATURE_SOURCE_EVIDENCE.items():
        state = implementation.get(feature, {}).get("state", "missing")
        if state != "not_implemented":
            absent = [token for token in tokens if token not in compiled_source_text]
            audit.check(not absent, f"source evidence missing for {feature}: {absent}")

    missing_impl = [str(path.relative_to(ROOT)) for path in EXPECTED_IMPLEMENTATION_FILES if not path.exists()]
    if missing_impl:
        audit.error(f"implementation stage incomplete; missing files: {missing_impl}")

    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8", errors="ignore") if (ROOT / "Makefile").exists() else ""
    missing_compiled_sources = [source for source in COMPILED_SOURCE_FILES if source not in makefile_text]
    audit.check(not missing_compiled_sources,
                f"implementation source exists but is not compiled by Makefile: {missing_compiled_sources}")

    sponsor_path = ROOT / "Sources" / "VancedSponsorBlock.m"
    sponsor_text = sponsor_path.read_text(encoding="utf-8", errors="ignore") if sponsor_path.exists() else ""
    audit.check("VSBSHA256Prefix" in sponsor_text and "substringToIndex" in sponsor_text,
                "SponsorBlock privacy gate missing SHA-256 prefix construction")
    audit.check('queryItemWithName:@"videoID"' not in sponsor_text and
                'queryItemWithName:@"videoId"' not in sponsor_text,
                "SponsorBlock must not send the full video ID as a query parameter")

    ryd_path = ROOT / "Sources" / "VancedRYD.m"
    ryd_text = ryd_path.read_text(encoding="utf-8", errors="ignore") if ryd_path.exists() else ""
    audit.check('hasPrefix:@"id.video.dislike."' in ryd_text,
                "RYD generic UI gate must be restricted to video dislike controls")
    audit.check('containsString:@"dislike"' not in ryd_text,
                "RYD must not use an unrestricted generic dislike-button matcher")

    scanned = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "README.md" or path == MATRIX or path == Path(__file__).resolve():
            continue
        if path.suffix not in CODE_SUFFIXES and path.name != "Makefile":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        scanned.append(str(path.relative_to(ROOT)))
        for token in LEGACY_TOKENS:
            if token in text:
                audit.error(f"legacy architecture token {token!r} leaked into {path.relative_to(ROOT)}")
        for token in RESTRICTED_SERVICE_TOKENS:
            if token in text:
                audit.error(f"restricted service-bypass token {token!r} leaked into {path.relative_to(ROOT)}")

    audit.info["scanned_code_files"] = scanned
    audit.info["locked_dependencies"] = 1 + len(lock.get("headers", [])) + len(lock.get("modules", []))
    audit.info["required_features"] = sorted(feature_ids)
    audit.info["implementation_states"] = {k: v.get("state") for k, v in sorted(implementation.items())}
    audit.info["runtime_device_gates"] = matrix.get("runtime_device_gates", [])


def locate_app(path: Path):
    if path.is_dir() and path.suffix == ".app":
        return path, None
    if not path.is_file():
        raise ValueError(f"not an IPA/app path: {path}")
    temp = tempfile.TemporaryDirectory(prefix="vanced-ios-audit-")
    try:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temp.name)
    except Exception:
        temp.cleanup()
        raise
    apps = list((Path(temp.name) / "Payload").glob("*.app"))
    if len(apps) != 1:
        temp.cleanup()
        raise ValueError(f"expected exactly one .app under Payload, found {len(apps)}")
    return apps[0], temp


def audit_ipa(audit: Audit, raw_path: str, built: bool = False) -> None:
    path = Path(raw_path).expanduser().resolve()
    try:
        app, temp = locate_app(path)
    except Exception as exc:
        audit.error(str(exc))
        return

    try:
        plist_path = app / "Info.plist"
        audit.check(plist_path.exists(), "Info.plist missing from app")
        if not plist_path.exists():
            return

        with plist_path.open("rb") as handle:
            info = plistlib.load(handle)

        bundle_id = str(info.get("CFBundleIdentifier", ""))
        version = str(info.get("CFBundleShortVersionString", ""))
        build = str(info.get("CFBundleVersion", ""))
        executable_name = str(info.get("CFBundleExecutable", "YouTube"))
        executable = app / executable_name

        if built:
            audit.check("youtube" in bundle_id.lower(), f"built app no longer identifies as YouTube: {bundle_id}")
        else:
            audit.check(bundle_id == "com.google.ios.youtube", f"unexpected input bundle id: {bundle_id}")
        audit.check(bool(version), "CFBundleShortVersionString is missing")
        audit.check(executable.exists(), f"main executable missing: {executable_name}")

        arch = None
        file_cmd = shutil.which("file")
        if executable.exists() and file_cmd:
            arch = subprocess.check_output([file_cmd, str(executable)], text=True, errors="ignore").strip()
            audit.check("arm64" in arch, "main executable does not advertise arm64")
        elif executable.exists():
            audit.warn("file utility unavailable; architecture could not be verified")

        compatibility = {}
        if executable.exists():
            strings_cmd = shutil.which("strings")
            if not strings_cmd:
                audit.error("strings utility unavailable; implemented hook compatibility cannot be verified")
            else:
                try:
                    binary_text = subprocess.check_output(
                        [strings_cmd, str(executable)],
                        text=True,
                        errors="ignore",
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as exc:
                    binary_text = ""
                    audit.error(f"strings probe failed: {exc}")

                status = load_json(STATUS).get("features", {})
                for feature, groups in BINARY_EVIDENCE.items():
                    state = status.get(feature, {}).get("state", "not_implemented")
                    if state == "not_implemented":
                        continue
                    group_results = []
                    for alternatives in groups:
                        found = [token for token in alternatives if token in binary_text]
                        group_results.append({"alternatives": alternatives, "found": found})
                        if not found:
                            audit.error(
                                f"IPA compatibility missing for {feature}: none of {alternatives}"
                            )
                    compatibility[feature] = group_results

                settings_results = []
                for alternatives in SETTINGS_BINARY_EVIDENCE:
                    found = [token for token in alternatives if token in binary_text]
                    settings_results.append({"alternatives": alternatives, "found": found})
                    if not found:
                        audit.error(
                            f"IPA compatibility missing for settings UI: none of {alternatives}"
                        )
                compatibility["settings_ui"] = settings_results

            otool = shutil.which("otool")
            if otool:
                try:
                    load_commands = subprocess.check_output(
                        [otool, "-l", str(executable)],
                        text=True,
                        errors="ignore",
                        stderr=subprocess.DEVNULL,
                    )
                    cryptids = re.findall(r"\bcryptid\s+(\d+)", load_commands)
                    if cryptids:
                        audit.info["cryptids"] = cryptids
                        audit.check(all(value == "0" for value in cryptids),
                                    f"input appears encrypted; cryptid values={cryptids}")
                    else:
                        audit.warn("otool found no cryptid field; decryption state not proven")
                except Exception as exc:
                    audit.warn(f"otool encryption probe failed: {exc}")
            else:
                audit.warn("otool unavailable; decryption state not proven on this host")

        audit.info["binary_compatibility"] = compatibility

        built_details = {}
        if built:
            frameworks = app / "Frameworks"
            core_dylib = frameworks / "VancedCore.dylib"
            audit.check(core_dylib.exists() and core_dylib.stat().st_size > 0,
                        "built IPA is missing Frameworks/VancedCore.dylib")
            built_details["core_dylib"] = str(core_dylib) if core_dylib.exists() else None

            otool = shutil.which("otool")
            if executable.exists() and otool:
                try:
                    linked = subprocess.check_output(
                        [otool, "-L", str(executable)],
                        text=True,
                        errors="ignore",
                        stderr=subprocess.DEVNULL,
                    )
                    audit.check("VancedCore.dylib" in linked,
                                "main executable does not contain a load command for VancedCore.dylib")
                    built_details["linked_vanced_core"] = "VancedCore.dylib" in linked
                except Exception as exc:
                    audit.error(f"built IPA linkage probe failed: {exc}")
            elif executable.exists():
                audit.warn("otool unavailable; built IPA dylib linkage cannot be proven")

        audit.info["ipa"] = {
            "path": str(path),
            "bundle_id": bundle_id,
            "version": version,
            "build": build,
            "executable": executable_name,
            "architecture_probe": arch,
            "background_modes": info.get("UIBackgroundModes", []),
            "built_output": built,
            "built_details": built_details,
        }
    finally:
        if temp is not None:
            temp.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Vanced iOS stage audit")
    parser.add_argument("--ipa", help="optional decrypted YouTube .ipa or .app to inspect")
    parser.add_argument("--built-ipa", help="optional packaged IPA to verify after injection")
    parser.add_argument("--ipa-only", action="store_true",
                        help="inspect only IPA compatibility; skip full product stage gate")
    parser.add_argument("--structural-only", action="store_true",
                        help="return success when structural/source checks pass even if product completeness is still NEEDS_REVIEW")
    parser.add_argument("--json-out", help="optional path for a JSON report")
    args = parser.parse_args()

    audit = Audit()
    if not args.ipa_only:
        audit_source(audit)
    if args.ipa:
        audit_ipa(audit, args.ipa, built=False)
    if args.built_ipa:
        audit_ipa(audit, args.built_ipa, built=True)
    if args.ipa_only and not args.ipa and not args.built_ipa:
        audit.error("--ipa-only requires --ipa or --built-ipa")

    result = audit.result()
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")

    if audit.errors:
        return 1
    if audit.incomplete and not args.structural_only:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
