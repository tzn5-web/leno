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
browser_script = read("Leno/BrowserRoutingScript.swift")
session = read("Leno/YouTubeSession.swift")
player_view = read("Leno/YouTubeWebView.swift")
browser_view = read("Leno/YouTubeBrowserWebView.swift")
root_view = read("Leno/YouTubeView.swift")
adblock = read("Leno/AdBlockScript.swift")
project = read("project.yml")

all_swift = "\n".join(
    p.read_text(encoding="utf-8")
    for p in LENO.glob("*.swift")
)

require('MARKETING_VERSION: "0.4.8"' in project, "version must be 0.4.8")
require('CURRENT_PROJECT_VERSION: "16"' in project, "build must be 16")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")

for needle in [
    "AVPlayer",
    "YouTubeKit",
    "BackgroundAudioHandoff",
    "mediaCandidate",
    "hlsProbe",
    "hlsManifestUrl",
]:
    forbid(all_swift, needle, "V8 transition-recovery source")

# V7 persistent player architecture must remain intact.
for needle in [
    "YouTubeWebView(",
    "YouTubeBrowserWebView(",
    "session.isPlayerPresented",
    "0.001",
]:
    require(needle in root_view, f"persistent-player invariant missing: {needle}")

require(
    root_view.count("YouTubeWebView(") == 1
    and root_view.count("YouTubeBrowserWebView(") == 1,
    "player/browser must retain one stable SwiftUI identity each",
)

require(
    "allowsPictureInPictureMediaPlayback = true" in player_view,
    "persistent player PiP capability missing",
)
require(
    "allowsPictureInPictureMediaPlayback =\n            false" in browser_view,
    "browser must not own PiP",
)
forbid(player_view, "session.loadHome()", "persistent player WebView")

for needle in [
    "currentPlayerURL",
    "showBrowser()",
    "browserWebView",
    "shouldRoutePlayerNavigationToBrowser",
]:
    require(needle in session, f"V7 routing invariant missing: {needle}")

# Build-14 explicit Pause ownership remains absolute.
for needle in [
    "explicitPauseActive",
    "Number.POSITIVE_INFINITY",
    "shieldPageMediaActions",
    "__youtubeVcdActionShield",
]:
    require(
        needle in session or needle in bridge,
        f"explicit-pause/media ownership invariant missing: {needle}"
    )

require(
    re.search(r"setAllMediaPlaybackSuspended\(\s*true", session)
    and re.search(r"setAllMediaPlaybackSuspended\(\s*false", session),
    "native explicit Pause suspend gate missing",
)

# Native desiredPlayback is the transition-state authority.
for needle in [
    "desiredPlayback",
    "shouldRecoverDesiredPlayback",
    "transitionRecoveryGeneration",
    "transitionRecoveryDeadline",
    "transitionRecoveryWorkItems",
    "systemInterruptionActive",
    "beginTransitionRecovery",
    "attemptTransitionRecovery",
    "isTransitionRecoveryActive",
]:
    require(needle in session, f"V8 state-machine invariant missing: {needle}")

require(
    re.search(
        r"func pause\(\).*?desiredPlayback = false.*?cancelTransitionRecovery\(\)",
        session,
        flags=re.S,
    ) is not None,
    "explicit Pause does not cancel native transition recovery",
)

require(
    re.search(
        r"case \.began:.*?systemInterruptionActive = true.*?cancelTransitionRecovery\(\)",
        session,
        flags=re.S,
    ) is not None,
    "AVAudioSession interruption does not block transition recovery",
)

# Lifecycle and PiP all use the same transition machine.
for reason in [
    "inactive",
    "background",
    "foreground",
    "pip-request",
    "pip-enter",
    "pip-exit",
]:
    require(
        f'"{reason}"' in session or f'"{reason}"' in bridge,
        f"transition reason missing: {reason}",
    )

require(
    re.search(
        r"applicationWillResignActive\(\).*?beginTransitionRecovery\(.*?\"inactive\"",
        session,
        flags=re.S,
    ) is not None,
    "inactive lifecycle does not arm transition recovery",
)
require(
    re.search(
        r"applicationDidEnterBackground\(\).*?beginTransitionRecovery\(.*?\"background\"",
        session,
        flags=re.S,
    ) is not None,
    "background lifecycle does not arm transition recovery",
)
require(
    re.search(
        r"applicationDidBecomeActive\(\).*?beginTransitionRecovery\(.*?\"foreground\"",
        session,
        flags=re.S,
    ) is not None,
    "foreground lifecycle does not arm transition recovery",
)

# PiP notifies native before WebKit changes presentation mode.
require(
    re.search(
        r"const requestPiP = \(\) => \{.*?postTransitionEvent\(.*?\"pip-request\"",
        bridge,
        flags=re.S,
    ) is not None,
    "PiP request does not notify native before transition",
)
require(
    '"pip-enter"' in bridge and '"pip-exit"' in bridge,
    "PiP presentation enter/exit events missing",
)
require(
    'name: "transitionEvent"' in player_view
    and 'forName: "transitionEvent"' in player_view
    and 'message.name == "transitionEvent"' in session,
    "PiP transition bridge lifecycle incomplete",
)

# Native state is probed and paused/suspended media is reasserted to Play.
for needle in [
    "requestMediaPlaybackState",
    "setAllMediaPlaybackSuspended(",
    "PlaybackBridgeScript\n                                        .playCall",
    "PlaybackBridgeScript\n                                        .keepAliveCall",
]:
    require(needle in session, f"native transition recovery action missing: {needle}")

for delay in [
    "0.08",
    "0.20",
    "0.45",
    "0.90",
    "1.60",
    "2.80",
]:
    require(delay in session, f"bounded transition retry missing: {delay}")

# Native desired playback may be confirmed by JS but must not be erased by a
# transient pause during system transition.
require(
    "self.desiredPlayback ||\n                        bridgeWantsPlayback" in session,
    "native desired playback is not authoritative in media-state merge",
)

# Transition suspension is not a freeze; destructive reload is a fallback only
# after the bounded transition window.
require(
    session.count("!self.isTransitionRecoveryActive") >= 1,
    "media-state freeze detection ignores transition recovery window",
)
require(
    "!isTransitionRecoveryActive" in session,
    "frozen repair can run during native transition recovery",
)
require(
    "nativeMediaPlaybackState ==\n                        .paused" in session
    and "nativeMediaPlaybackState ==\n                        .suspended" in session,
    "post-transition paused/suspended fallback missing",
)

# Natural end must not be repaired as a freeze.
require(
    "ended: !!video.ended" in bridge,
    "ended state telemetry missing",
)
require(
    'let ended = body["ended"] as? Bool ?? false' in session
    and "mediaExists &&\n                !ended" in session,
    "natural media end is not excluded from freeze repair",
)

# Existing lock-screen/system ownership.
for needle in [
    "MPRemoteCommandCenter.shared()",
    "MPNowPlayingInfoCenter.default()",
]:
    require(needle in session, f"native remote media owner missing: {needle}")

# Open-in-YouTube blocking stays active.
for needle in [
    "removeOpenInYouTubePromos",
    "mweb_to_native_app",
    "redirect_app_store_ios=1",
]:
    require(needle in adblock, f"Open-in-YouTube cleanup missing: {needle}")

# Extract JS for parser validation.
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

for name, source in [
    ("PlaybackBridgeScript.js", bridge),
    ("BrowserRoutingScript.js", browser_script),
    ("AdBlockScript.js", adblock),
]:
    (out_dir / name).write_text(
        extract(source, name),
        encoding="utf-8",
    )

if errors:
    print("V8 TRANSITION RECOVERY AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V8 TRANSITION RECOVERY AUDIT PASSED")
print(" - V7 persistent player/browser separation retained")
print(" - native desiredPlayback owns transition intent")
print(" - explicit Pause and AVAudioSession interruption cancel recovery")
print(" - inactive/background/foreground use one native recovery machine")
print(" - PiP request/enter/exit notify native transition recovery")
print(" - paused/suspended WebKit media is unsuspended and reasserted")
print(" - transition recovery is bounded before reload fallback")
print(" - natural video end is excluded from freeze repair")
