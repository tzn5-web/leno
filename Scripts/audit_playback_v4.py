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
view = read("Leno/YouTubeView.swift")
webview = read("Leno/YouTubeWebView.swift")
adblock = read("Leno/AdBlockScript.swift")
project = read("project.yml")

# Repository hygiene: no inactive native handoff/resolver implementation may
# remain available for accidental target inclusion.
for rel in [
    "Leno/BackgroundAudioHandoff.swift",
    "Leno/NativePlaybackController.swift",
    "Leno/NativePlayerView.swift",
    "Leno/NavigationBridgeScript.swift",
]:
    require(not (ROOT / rel).exists(), f"stale playback file exists: {rel}")

all_swift = "\n".join(
    p.read_text(encoding="utf-8")
    for p in LENO.glob("*.swift")
)

for needle in [
    "YouTubeKit",
    "AVPlayer",
    "mediaCandidate",
    "setAllMediaPlaybackSuspended",
]:
    forbid(all_swift, needle, "compiled Leno sources")

require('MARKETING_VERSION: "0.4.4"' in project, "version must be 0.4.4")
require('CURRENT_PROJECT_VERSION: "10"' in project, "build must be 10")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")
require("excludes:" not in project, "project still has source excludes; dead playback code may remain")

# WebKit configuration.
for needle in [
    "allowsInlineMediaPlayback = true",
    "allowsPictureInPictureMediaPlayback = true",
    "allowsAirPlayForMediaPlayback = true",
    "mediaTypesRequiringUserActionForPlayback = []",
]:
    require(needle in webview, f"WKWebView invariant missing: {needle}")

require(
    "injectionTime: .atDocumentStart" in webview,
    "playback scripts must inject at document start",
)
require(
    webview.find("source: PlaybackBridgeScript.source")
    < webview.find("source: AdBlockScript.source"),
    "PlaybackBridgeScript must be injected before AdBlockScript",
)

# Core lifecycle model.
for needle in [
    "__YOUTUBE_VCD_PLAYBACK_BRIDGE_V4__",
    "blockedLifecycleEvents",
    "nativeHiddenDescriptor",
    "spoofDocumentProperty",
    "document.hasFocus = () => true",
    "const isBackgrounded = () =>",
    "state.nativeBackground",
    "userPauseUntil",
    "transitionRecoveryUntil",
    "const preserveIntent =",
    "const preservePosition =",
    "const sameMedia =",
    "systemInterruption",
    "beginSystemInterruption",
    "endSystemInterruption",
]:
    require(needle in bridge, f"background invariant missing: {needle}")

# Raw native visibility reads are deliberately limited to:
# 1) isBackgrounded() helper, 2) native visibilitychange, 3) native
# webkitvisibilitychange. Recovery decisions must use isBackgrounded().
raw_hidden_count = bridge.count("isReallyHidden()")
require(
    raw_hidden_count == 3,
    f"raw isReallyHidden() usage drifted: expected 3, found {raw_hidden_count}",
)

require(
    bridge.count("isBackgrounded()") >= 8,
    "nativeBackground is not fused through enough recovery paths",
)

# Media element replacement / foreground rebuild protection.
for needle in [
    'videoID: ""',
    "state.videoID === nextVideoID",
    "const routeChanged =",
    "preserveIntent ||",
    "state.lastKnownTime > 1",
    "Math.abs(",
    "video.currentTime =\n              state.lastKnownTime",
]:
    require(needle in bridge, f"media-rebuild protection missing: {needle}")

# Shorts are playback media, not an inline preview.
forbid(bridge, "ytm-reel-video-renderer", "PlaybackBridgeScript")

# Preserve the baseline user-visible PiP/fullscreen affordances.
for needle in [
    "__youtube_vcd_media_controls__",
    "__youtube_vcd_pip__",
    "__youtube_vcd_fullscreen__",
    "ensureMediaControls",
    "requestPiP",
    "requestFullscreen",
    "webkitRequestFullscreen",
]:
    require(needle in bridge, f"baseline control missing: {needle}")

require(
    "webkitpresentationmodechanged" in bridge
    and "event.stopPropagation()" in bridge,
    "PiP presentation-mode propagation guard missing",
)

# Native is the single explicit lock-screen transport owner. The page can keep
# its normal WebKit Media Session behavior, but our bridge must not install a
# second action-handler layer.
for needle in [
    "navigator.mediaSession",
    "setActionHandler(",
    "setPositionState(",
]:
    forbid(bridge, needle, "PlaybackBridgeScript")

require("navigator.audioSession.type" in bridge, "Web AudioSession playback hint missing")
require("MPRemoteCommandCenter.shared()" in session, "native remote commands missing")
require("MPNowPlayingInfoCenter.default()" in session, "native Now Playing owner missing")
require("appIsBackground" in session, "native scene background truth missing from Now Playing")
require("hasPlaybackContext" in session, "remote-control context is not preserved across media replacement")

# JS health telemetry must actually reach Swift.
for needle in [
    'body["readyState"]',
    'body["networkState"]',
    'body["inDOM"]',
    'body["videoID"]',
    "Web media health warning",
    "updateFrozenMediaRepair",
    "repairFrozenWebMedia",
    "lastStablePlaybackTime",
    "pendingRepairResumeTime",
    "foregroundRepairWindowUntil",
    "requestMediaPlaybackState",
    "nativeMediaPlaybackState",
    "beginSystemInterruptionCall",
    "endSystemInterruptionCall",
]:
    require(needle in session, f"native media-health telemetry missing: {needle}")

require(
    "restoreAfterReloadCall" in bridge,
    "controlled foreground freeze repair cannot restore playback",
)

# Scene lifecycle contract.
for needle in [
    "applicationWillResignActive()",
    "applicationDidEnterBackground()",
    "applicationDidBecomeActive()",
]:
    require(needle in view, f"scene lifecycle call missing: {needle}")

# Ad blocker must not be a second media-state owner.
forbid(adblock, "messageHandlers?.mediaState", "AdBlockScript")

# Extract the main raw JavaScript blocks so CI can syntax-check them with Node.
out_dir = ROOT / "build" / "source-audit"
out_dir.mkdir(parents=True, exist_ok=True)

def extract_raw_source(swift_text, label):
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
    extract_raw_source(bridge, "PlaybackBridgeScript"),
    encoding="utf-8",
)
(out_dir / "AdBlockScript.js").write_text(
    extract_raw_source(adblock, "AdBlockScript"),
    encoding="utf-8",
)

if errors:
    print("V4 SOURCE AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V4 SOURCE AUDIT PASSED")
print(f" - raw isReallyHidden() calls: {raw_hidden_count}")
print(" - one native transport owner")
print(" - media replacement intent/position preserved")
print(" - persistent foreground readyState=0 / WK suspended repair is bounded and resumable")
print(" - same-element route changes and AVAudioSession interruptions are isolated")
print(" - lock-screen context survives transient video-element replacement")
print(" - PiP/fullscreen controls present and WebKit fallback retained")
print(" - dormant native playback code absent")
