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
desktop = read("Leno/DesktopBackendScript.swift")
session = read("Leno/YouTubeSession.swift")
view = read("Leno/YouTubeView.swift")
webview = read("Leno/YouTubeWebView.swift")
adblock = read("Leno/AdBlockScript.swift")
project = read("project.yml")

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

require('MARKETING_VERSION: "0.4.5"' in project, "version must be 0.4.5")
require('CURRENT_PROJECT_VERSION: "12"' in project, "build must be 12")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")
require("excludes:" not in project, "source excludes remain")

for needle in [
    "allowsInlineMediaPlayback = true",
    "allowsPictureInPictureMediaPlayback = true",
    "allowsAirPlayForMediaPlayback = true",
    "mediaTypesRequiringUserActionForPlayback = []",
]:
    require(needle in webview, f"WKWebView invariant missing: {needle}")

require(
    'webView.customUserAgent =' in webview
    and 'Macintosh; Intel Mac OS X' in webview,
    "desktop Safari user agent missing",
)

for needle in [
    '.name: "SOCS"',
    '.value: "CAI"',
    '.domain: ".youtube.com"',
    '.httpCookieStore',
    '.setCookie(cookie)',
]:
    require(needle in webview, f"EU consent bootstrap missing: {needle}")

require(
    webview.find(".setCookie(cookie)")
    < webview.find("session.loadHome()", webview.find(".setCookie(cookie)")),
    "YouTube must not load before the SOCS cookie completion path",
)

require(
    '"Accept-Language"' in session
    and '"en-US,en;q=0.9"' in session,
    "stable initial YouTube Accept-Language header missing",
)

bridge_index = webview.find("source: PlaybackBridgeScript.source")
desktop_index = webview.find("source: DesktopBackendScript.source")
ad_index = webview.find("source: AdBlockScript.source")

require(
    -1 not in [bridge_index, desktop_index, ad_index]
    and bridge_index < desktop_index < ad_index,
    "script injection order must be PlaybackBridge -> DesktopBackend -> AdBlock",
)

for needle in [
    "__YOUTUBE_VCD_PLAYBACK_BRIDGE_V4__",
    "blockedLifecycleEvents",
    "nativeHiddenDescriptor",
    "spoofDocumentProperty",
    "const isBackgrounded = () =>",
    "state.nativeBackground",
    "userPauseUntil",
    "transitionRecoveryUntil",
    "const preserveIntent =",
    "const preservePosition =",
    "systemInterruption",
    "beginSystemInterruption",
    "endSystemInterruption",
]:
    require(needle in bridge, f"V4 lifecycle invariant missing: {needle}")

raw_hidden_count = bridge.count("isReallyHidden()")
require(
    raw_hidden_count == 3,
    f"raw isReallyHidden() usage drifted: expected 3, found {raw_hidden_count}",
)
require(
    bridge.count("isBackgrounded()") >= 8,
    "native background state is not fused through recovery paths",
)

for needle in [
    "__youtube_vcd_media_controls__",
    "__youtube_vcd_pip__",
    "__youtube_vcd_fullscreen__",
    "webkitpresentationmodechanged",
    "event.stopPropagation()",
    "webkitRequestFullscreen",
    "restoreAfterReloadCall",
]:
    require(needle in bridge, f"playback control invariant missing: {needle}")

for needle in [
    "__YOUTUBE_VCD_DESKTOP_BACKEND_V5__",
    'DESKTOP_HOST =\n        "www.youtube.com"',
    "normalizeCurrentURL",
    '"app"',
    '"desktop"',
    '"persist_app"',
    '"1"',
    "ensureViewport",
    "__youtube_vcd_desktop_shell_v5__",
    "scheduleReconcile",
    "yt-navigate-finish",
    "mediaSessionShielded",
    "disablePageMediaSession",
    "setActionHandler",
    "setPositionState",
]:
    require(needle in desktop, f"desktop backend invariant missing: {needle}")

forbid(desktop, "m.youtube.com/feed", "DesktopBackendScript")
require(
    "ytd-mini-guide-renderer" in desktop
    and "ytd-guide-renderer,#guide,#guide-button" not in desktop,
    "desktop guide drawer must remain available while mini-guide is hidden",
)

for needle in [
    "youtube",
    "vnd.youtube",
    "itms-apps",
    "itms-services",
]:
    require(needle in webview, f"blocked app scheme missing: {needle}")

require(
    "normalizeYouTubeURL" in webview
    and '"www.youtube.com"' in webview
    and '"m.youtube.com"' in webview
    and '"youtu.be"' in webview,
    "native desktop URL normalization missing",
)

for needle in [
    'host == "consent.youtube.com"',
    'host == "consent.google.com"',
    "let contentRoute =",
    'path == "/watch"',
    'path.hasPrefix("/shorts/")',
    'path.hasPrefix("/feed/")',
]:
    require(needle in webview, f"native consent-safe routing missing: {needle}")

for needle in [
    "const contentRoute =",
    'path === "/watch"',
    'path.startsWith(\n              "/shorts/"',
    'path.startsWith(\n              "/feed/"',
]:
    require(needle in desktop, f"JS consent-safe routing missing: {needle}")

require(
    "https://m.youtube.com" not in all_swift,
    "mobile YouTube URL remains in compiled source",
)

for needle in [
    "MPRemoteCommandCenter.shared()",
    "MPNowPlayingInfoCenter.default()",
    "hasPlaybackContext",
    "preserveNativeIntent",
    "appIsBackground",
    "requestMediaPlaybackState",
    "nativeMediaPlaybackState",
    "pendingWebProcessRecovery",
    "desktopBackendActive",
    "mediaSessionShielded",
    "backendHost",
]:
    require(needle in session, f"native ownership/telemetry missing: {needle}")

for needle in [
    'body["desktopBackend"]',
    'body["mediaSessionShielded"]',
    'body["backendHost"]',
]:
    require(needle in session, f"V5 telemetry parser missing: {needle}")

for needle in [
    "desktopBackend:",
    "mediaSessionShielded:",
    "backendHost:",
]:
    require(needle in bridge, f"V5 bridge telemetry missing: {needle}")

require(
    "removeOpenInYouTubePromos" in adblock,
    "Open-in-YouTube promo cleanup missing",
)
forbid(adblock, "messageHandlers?.mediaState", "AdBlockScript")

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

for name, source in [
    ("PlaybackBridgeScript.js", bridge),
    ("DesktopBackendScript.js", desktop),
    ("AdBlockScript.js", adblock),
]:
    (out_dir / name).write_text(
        extract_raw_source(source, name),
        encoding="utf-8",
    )

if errors:
    print("V5 SOURCE AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V5 SOURCE AUDIT PASSED")
print(f" - raw isReallyHidden() calls: {raw_hidden_count}")
print(" - desktop www.youtube.com backend enforced")
print(" - desktop Safari UA enabled")
print(" - page Media Session transport neutralized")
print(" - native MPRemoteCommandCenter remains transport owner")
print(" - mobile guide drawer preserved; mini-guide hidden")
print(" - app/universal-link promotion paths blocked")
print(" - V4 background and freeze recovery retained")
print(" - V5 backend telemetry connected to Swift")
print(" - EU consent cookie is seeded before first YouTube load")
print(" - desktop query parameters are limited to content routes")
