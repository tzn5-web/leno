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
project = read("project.yml")

all_swift = "\n".join(
    p.read_text(encoding="utf-8")
    for p in LENO.glob("*.swift")
)

require('MARKETING_VERSION: "0.4.6"' in project, "version must be 0.4.6")
require('CURRENT_PROJECT_VERSION: "13"' in project, "build must be 13")
require("UIBackgroundModes:" in project and "- audio" in project, "audio background mode missing")

for needle in [
    "AVPlayer",
    "YouTubeKit",
    "BackgroundAudioHandoff",
    "mediaCandidate",
]:
    forbid(all_swift, needle, "V6 diagnostic source")

for needle in [
    "youtubei/v1/player",
    "hlsManifestUrl",
    "reportHLSProbe",
    "inspectPlayerPayload",
    "nativeFetch",
    "hasSPC",
    "hasNChallenge",
    "hasVariants",
]:
    require(needle in bridge, f"HLS probe invariant missing: {needle}")

require(
    "window.fetch =" in bridge
    and "XMLHttpRequest" in bridge,
    "V6 must observe both fetch and XHR player responses",
)

require(
    'name: "hlsProbe"' in webview,
    "hlsProbe WKScriptMessageHandler is not registered",
)

require(
    'forName: "hlsProbe"' in webview,
    "hlsProbe handler is not removed on teardown",
)

for needle in [
    'message.name == "hlsProbe"',
    "handleHLSProbe",
    "hlsProbeSummary",
    "V6 HLS probe:",
]:
    require(needle in session, f"native HLS probe consumer missing: {needle}")

require(
    "hlsProbePill" in view
    and "session.hlsProbeSummary" in view,
    "sanitized on-device HLS diagnostic is missing",
)

for needle in [
    "manifestURL",
    "Cookie",
    "HTTPCookie",
    "poToken",
    "unsolvedN",
    "solvedN",
]:
    forbid(session, needle, "YouTubeSession probe output")

require(
    bridge.count("isReallyHidden()") == 3,
    "V4 visibility invariant drifted",
)

for needle in [
    "preserveIntent",
    "preservePosition",
    "systemInterruption",
    "restoreAfterReloadCall",
    "__youtube_vcd_pip__",
    "__youtube_vcd_fullscreen__",
]:
    require(needle in bridge, f"V4 playback invariant missing: {needle}")

out_dir = ROOT / "build" / "source-audit"
out_dir.mkdir(parents=True, exist_ok=True)

match = re.search(
    r'static let source\s*=\s*#"""(.*?)"""#',
    bridge,
    flags=re.S,
)
if not match:
    errors.append("unable to extract PlaybackBridgeScript JavaScript")
else:
    (out_dir / "PlaybackBridgeScript.js").write_text(
        match.group(1),
        encoding="utf-8",
    )

if errors:
    print("V6 DIAGNOSTIC AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V6 DIAGNOSTIC AUDIT PASSED")
print(" - foreground playback engine unchanged")
print(" - no AVPlayer/native handoff is active")
print(" - HLS player-response observation enabled")
print(" - manifest inspection stays inside WebKit")
print(" - only sanitized capability metadata reaches Swift")
print(" - V4 lifecycle/PiP/recovery invariants retained")
