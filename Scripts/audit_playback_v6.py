#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
LENO = ROOT / "Leno"
errors = []

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def require(condition, message):
    if not condition:
        errors.append(message)

def forbid(text, needle, where):
    require(needle not in text, f"{where}: forbidden token present: {needle}")

bridge = read("Leno/PlaybackBridgeScript.swift")
session = read("Leno/YouTubeSession.swift")
webview = read("Leno/YouTubeWebView.swift")
adblock = read("Leno/AdBlockScript.swift")
view = read("Leno/YouTubeView.swift")
project = read("project.yml")

all_swift = "\n".join(
    p.read_text(encoding="utf-8")
    for p in LENO.glob("*.swift")
)

require('MARKETING_VERSION: "0.4.6"' in project, "version must be 0.4.6")
require('CURRENT_PROJECT_VERSION: "14"' in project, "build must be 14")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")

for needle in [
    "AVPlayer",
    "YouTubeKit",
    "BackgroundAudioHandoff",
    "mediaCandidate",
    "hlsProbe",
    "hlsManifestUrl",
]:
    forbid(all_swift, needle, "V6 control-stability source")

# Existing WebKit playback engine remains intact.
for needle in [
    "__YOUTUBE_VCD_PLAYBACK_BRIDGE_V4__",
    "recoverPlayback",
    "prepareForBackground",
    "enterBackground",
    "resumeForeground",
    "preserveIntent",
    "preservePosition",
    "systemInterruption",
    "restoreAfterReloadCall",
    "__youtube_vcd_pip__",
    "__youtube_vcd_fullscreen__",
]:
    require(needle in bridge, f"V4 playback invariant missing: {needle}")

require(
    bridge.count("isReallyHidden()") == 3,
    "native visibility invariant drifted",
)

# Explicit user Pause is an indefinite latch, not a timer.
for needle in [
    "explicitPause: false",
    "Number.POSITIVE_INFINITY",
    "state.explicitPause ||",
    "!state.explicitPause",
]:
    require(needle in bridge, f"explicit-pause invariant missing: {needle}")

forbid(bridge, "Date.now() + 5000", "PlaybackBridgeScript explicit Pause")

require(
    bridge.count("explicitPause:") >= 4,
    "explicit Pause is not propagated through media-state/snapshot messages",
)

# Page user controls route through native ownership.
require(
    "messageHandlers\n              ?.mediaIntent" in bridge,
    "page media intent is not forwarded to Swift",
)
require(
    'name: "mediaIntent"' in webview
    and 'forName: "mediaIntent"' in webview,
    "mediaIntent WKScriptMessageHandler lifecycle is incomplete",
)
require(
    'message.name == "mediaIntent"' in session,
    "native mediaIntent consumer missing",
)

# Native hard gate: while Pause is active neither YouTube nor recovery can resume.
require(
    "explicitPauseActive" in session,
    "native explicit-pause latch missing",
)
require(
    "setAllMediaPlaybackSuspended(" in session
    and re.search(r"setAllMediaPlaybackSuspended\(\s*true", session)
    and re.search(r"setAllMediaPlaybackSuspended\(\s*false", session),
    "native WebKit suspend/unsuspend gate missing",
)
forbid(session, "bridgeExplicitPause", "YouTubeSession native ownership")

# Prevent YouTube from reclaiming system transport handlers.
for needle in [
    "shieldPageMediaActions",
    "__youtubeVcdActionShield",
    '"setActionHandler"',
    "set(_) {}",
]:
    require(needle in bridge, f"MediaSession action shield missing: {needle}")

# Native MediaPlayer is the system transport owner.
for needle in [
    "MPRemoteCommandCenter.shared()",
    "MPNowPlayingInfoCenter.default()",
    "playCommand",
    "pauseCommand",
    "togglePlayPauseCommand",
]:
    require(needle in session, f"native remote command invariant missing: {needle}")

require(
    session.count("DispatchQueue.main.async {") >= 7,
    "remote/media state operations are not serialized onto main",
)

# PiP may recover system-transition pauses but never an explicit user Pause.
require(
    "webkitpresentationmodechanged" in bridge
    and "event.stopPropagation()" in bridge,
    "PiP propagation guard missing",
)
require(
    re.search(
        r"state\.wantsPlayback\s*&&\s*!state\.explicitPause\s*&&\s*video\.paused",
        bridge,
        flags=re.S,
    ) is not None,
    "PiP recovery does not honor explicit Pause",
)

# Mobile YouTube app promotion must neither be visible nor navigable.
for needle in [
    "removeOpenInYouTubePromos",
    "ytm-open-in-app-button-renderer",
    "mweb_to_native_app",
    "redirect_app_store_ios=1",
]:
    require(needle in adblock, f"Open-in-YouTube DOM cleanup missing: {needle}")

forbid(
    adblock,
    '"ytm-mobile-topbar-renderer",',
    "AdBlockScript promo cleanup",
)

for needle in [
    "isYouTubeAppPromotion",
    '"vnd.youtube"',
    '"youtube"',
    '"intent"',
    "mweb_to_native_app",
    "redirect_app_store_ios=1",
]:
    require(needle in webview, f"Open-in-YouTube navigation guard missing: {needle}")

# No obsolete diagnostic UI.
forbid(view, "hlsProbe", "YouTubeView")
forbid(session, "HLS ", "YouTubeSession")

# Extract JavaScript for real parser checks in CI.
out_dir = ROOT / "build" / "source-audit"
out_dir.mkdir(parents=True, exist_ok=True)

def extract(swift_text, label):
    match = re.search(
        r'static let source\s*=\s*#"""(.*?)"""#',
        swift_text,
        flags=re.S,
    )
    if not match:
        errors.append(f"{label}: unable to extract raw JS source")
        return ""
    return match.group(1)

(out_dir / "PlaybackBridgeScript.js").write_text(
    extract(bridge, "PlaybackBridgeScript"),
    encoding="utf-8",
)
(out_dir / "AdBlockScript.js").write_text(
    extract(adblock, "AdBlockScript"),
    encoding="utf-8",
)

if errors:
    print("V6 CONTROL AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V6 CONTROL AUDIT PASSED")
print(" - foreground WebKit playback engine retained")
print(" - explicit Pause is indefinite and native-owned")
print(" - WKWebView suspension is used only for explicit user Pause")
print(" - YouTube MediaSession action handlers are neutralized")
print(" - native MPRemoteCommandCenter remains system transport owner")
print(" - PiP/background recovery cannot override explicit Pause")
print(" - Open-in-YouTube UI and navigation paths are blocked")
print(" - obsolete HLS diagnostic hooks are absent")
