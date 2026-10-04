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

require('MARKETING_VERSION: "0.4.7"' in project, "version must be 0.4.7")
require('CURRENT_PROJECT_VERSION: "15"' in project, "build must be 15")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")

for needle in [
    "AVPlayer",
    "YouTubeKit",
    "BackgroundAudioHandoff",
    "mediaCandidate",
    "hlsProbe",
    "hlsManifestUrl",
]:
    forbid(all_swift, needle, "V7 persistent-player source")

# Build 14 control ownership must remain intact.
for needle in [
    "explicitPause: false",
    "Number.POSITIVE_INFINITY",
    "shieldPageMediaActions",
    "__youtubeVcdActionShield",
    "recoverPlayback",
    "prepareForBackground",
    "enterBackground",
    "restoreAfterReloadCall",
]:
    require(needle in bridge, f"V6 playback invariant missing: {needle}")

require(
    "explicitPauseActive" in session
    and re.search(r"setAllMediaPlaybackSuspended\(\s*true", session)
    and re.search(r"setAllMediaPlaybackSuspended\(\s*false", session),
    "native explicit Pause gate drifted",
)

for needle in [
    "MPRemoteCommandCenter.shared()",
    "MPNowPlayingInfoCenter.default()",
]:
    require(needle in session, f"native media owner missing: {needle}")

# Two persistent web surfaces.
for needle in [
    "YouTubeWebView(",
    "YouTubeBrowserWebView(",
    "session.isPlayerPresented",
    "0.001",
    ".allowsHitTesting(",
]:
    require(needle in root_view, f"dual persistent view invariant missing: {needle}")

require(
    root_view.count("YouTubeWebView(") == 1
    and root_view.count("YouTubeBrowserWebView(") == 1,
    "player/browser WebViews must each have one stable SwiftUI identity",
)

forbid(
    root_view,
    "if session.isPlayerPresented {\n                YouTubeWebView",
    "YouTubeView persistent player",
)

# Browser is browsing-only: shared data store, no PiP/AirPlay, gesture required,
# and no remote MediaSession handlers.
for needle in [
    "websiteDataStore =\n            .default()",
    "allowsPictureInPictureMediaPlayback =\n            false",
    "allowsAirPlayForMediaPlayback =\n            false",
    "mediaTypesRequiringUserActionForPlayback =\n            [.all]",
    'name:\n                "browserOpenVideo"',
]:
    require(needle in browser_view, f"browser isolation missing: {needle}")

for needle in [
    "__YOUTUBE_VCD_BROWSER_V7__",
    "browserOpenVideo",
    "isPlaybackURL",
    "history.pushState",
    "history.replaceState",
    "setActionHandler",
    "nativePause.call(media)",
]:
    require(needle in browser_script, f"browser routing/media isolation missing: {needle}")

# Player remains the only media/PiP surface and never initializes/navigates Home.
require(
    "allowsPictureInPictureMediaPlayback = true" in player_view,
    "persistent player PiP capability missing",
)
forbid(player_view, "session.loadHome()", "persistent player WebView")
require(
    "session.playerDidBecomeReady()" in player_view,
    "persistent player readiness gate missing",
)
require(
    'name: "browseRequest"' in player_view
    and 'forName: "browseRequest"' in player_view,
    "player browseRequest bridge lifecycle incomplete",
)

# Native state separates browser and player.
for needle in [
    "weak var browserWebView",
    "isPlayerPresented",
    "playerAvailable",
    "playerDidBecomeReady",
    "openVideo(",
    "showBrowser(",
    "showPlayer()",
    "shouldOpenInPlayer",
    "shouldRoutePlayerNavigationToBrowser",
    "loadPlayer(",
    "currentPlayerURL",
]:
    require(needle in session, f"persistent-player session invariant missing: {needle}")

require(
    re.search(
        r"func goBack\(\) \{\s*if isPlayerPresented \{\s*showBrowser\(\)",
        session,
        flags=re.S,
    ) is not None,
    "Back while player is visible must reveal browser, not navigate player history",
)

require(
    re.search(
        r"setAllMediaPlaybackSuspended\(\s*false\s*\).*?webView\.load",
        session,
        flags=re.S,
    ) is not None,
    "new player video must release old explicit suspension before load",
)

# Player routing invariant: every non-playback web destination leaves the
# persistent player untouched and goes to browser.
for needle in [
    "isPlaybackNavigationURL",
    "routeBrowseLink",
    "routeBrowseURL",
    "browseRequest",
    "history.pushState",
    "history.replaceState",
]:
    require(needle in bridge, f"player routing guard missing: {needle}")

require(
    "return !isPlaybackURL(url)" in session,
    "native player routing does not enforce playback-only URLs",
)

# App-promotion cleanup from build 14 stays active on both surfaces.
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
    print("V7 PERSISTENT PLAYER AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V7 PERSISTENT PLAYER AUDIT PASSED")
print(" - player and browser are separate persistent WKWebViews")
print(" - player remains mounted while browsing")
print(" - browser cannot own PiP/AirPlay/remote media")
print(" - browser video selections route to persistent player")
print(" - player non-video navigation routes to browser")
print(" - player SPA routing cannot replace video page with Home")
print(" - build 14 explicit-Pause/lock-screen fixes retained")
