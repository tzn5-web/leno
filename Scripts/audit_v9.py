#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
V9 = ROOT / "V9"
errors = []

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def require(condition, message):
    if not condition:
        errors.append(message)

project = read("project.yml")
player = read("V9/V9PlayerService.swift")
view = read("V9/V9MediaLabView.swift")
resolver = read("Resolver/app/main.py")
dockerfile = read("Resolver/Dockerfile")
requirements = read("Resolver/requirements.txt")

all_v9 = "\n".join(
    p.read_text(encoding="utf-8")
    for p in V9.glob("*.swift")
)

require('MARKETING_VERSION: "0.9.0"' in project, "V9 version must be 0.9.0")
require('CURRENT_PROJECT_VERSION: "1"' in project, "V9 build must be 1")
require("path: V9" in project, "V9 source root missing")
require("path: Leno/Assets.xcassets" in project, "asset catalog missing")
require("url: https://github.com/yattee/MPVKit.git" in project, "MPVKit package missing")
require("exactVersion: 1.0.1" in project, "MPVKit must be pinned to 1.0.1")
require("product: MPVKit" in project, "non-GPL MPVKit product missing")
require("MPVKit-GPL" not in project, "GPL MPVKit product must not be linked")
require("UIBackgroundModes:" in project and "- audio" in project, "background audio mode missing")

for forbidden in [
    "import WebKit",
    "import YouTubeKit",
    "WKWebView(",
    "AVPlayer(",
    "AVQueuePlayer(",
    "BackgroundAudioHandoff(",
]:
    require(
        forbidden not in all_v9,
        f"V9 target contains forbidden legacy engine symbol: {forbidden}",
    )

for required in [
    "import Libmpv",
    "mpv_create()",
    "mpv_initialize",
    '"vo"',
    '"libmpv"',
    '"hwdec"',
    '"videotoolbox-copy"',
    "mpv_render_context_create",
    "mpv_render_context_update",
    "mpv_render_context_render",
    "MPV_RENDER_PARAM_OPENGL_FBO",
    "MPRemoteCommandCenter",
    "MPNowPlayingInfoCenter",
    "desiredPlayback",
    "func handleScenePhase",
]:
    require(required in player, f"native MPV invariant missing: {required}")

render_view = read("V9/V9MPVRenderView.swift")
for required in [
    "CAEAGLLayer",
    "EAGLContext",
    "glBindFramebuffer",
    "glReadPixels",
    "CVPixelBufferCreate",
    "onFrame",
    "pauseRendering",
    "resumeRendering",
]:
    require(required in render_view, f"libmpv render surface invariant missing: {required}")

require(
    "V9MetalLayer" not in all_v9,
    "obsolete wid/CAMetalLayer renderer must not return",
)

pip_bridge = read("V9/V9MPVPiPBridge.swift")

for required in [
    "AVSampleBufferDisplayLayer",
    "AVPictureInPictureController",
    "ContentSource",
    "AVPictureInPictureSampleBufferPlaybackDelegate",
    "CMSampleBufferCreateReadyWithImageBuffer",
    "CMVideoFormatDescriptionCreateForImageBuffer",
    "sampleBufferRenderer",
    "pictureInPictureControllerIsPlaybackPaused",
    "pictureInPictureControllerTimeRangeForPlayback",
    "skipByInterval",
    "setPlaying",
    "shouldKeepRendering",
    "isPictureInPicturePossible",
    "NSKeyValueObservation",
]:
    require(required in pip_bridge, f"native MPV PiP invariant missing: {required}")

for required in [
    "V9MPVPiPBridge",
    "isPiPPossible",
    "isPiPActive",
    "togglePiP()",
    "updatePiPPlaybackState",
    "shouldKeepRendering",
]:
    require(required in player, f"V9 PiP service integration missing: {required}")

require(
    "captureFrames" in render_view
    and "onFrame" in render_view
    and "CVPixelBufferCreate" in render_view,
    "MPV framebuffer is not exposed to native PiP",
)

require(
    "NSAllowsLocalNetworking: true" in project
    and "NSLocalNetworkUsageDescription:" in project
    and "NSAllowsArbitraryLoads" not in project,
    "Media Lab local resolver networking is not narrowly configured",
)

require(
    'case .background:' in player
    and ".pauseRendering()" in player
    and "setPause(" not in player.split("case .background:", 1)[1].split("case .active:", 1)[0],
    "background lifecycle must pause rendering only, never MPV playback",
)

require(
    '"loadfile"' in player
    and "edl://!new_stream;!no_clip;!no_chapters;" in player
    and '"audio-add"' not in player,
    "separate video/audio MPV EDL load path missing or legacy audio-add race returned",
)

require(
    "V9MPVPlayerView" in view
    and "VcdResolverClient" in view,
    "Media Lab UI is not wired to resolver + MPV",
)

for required in [
    'APP_VERSION = "0.1.0-lab"',
    "yt-dlp",
    "/v1/video/{video_id}",
    "/v1/relay/{token}",
    "Range",
    "relayURL",
    "httpx.AsyncClient",
]:
    require(required in resolver or required in requirements, f"resolver invariant missing: {required}")

require(
    "nodejs" in dockerfile
    and '"node"' in resolver,
    "resolver JS challenge runtime is inconsistent",
)

require(
    "yt-dlp==2026.08.19" in requirements,
    "resolver yt-dlp version is not the audited current pin",
)

require(
    "h264" in resolver
    and "avc1" in resolver
    and "aac" in resolver
    and "mp4a" in resolver,
    "Media Lab resolver must prefer conservative H264/AAC formats first",
)

# The API response must expose relay URLs, not raw upstream URLs.
response_block = resolver.split("return {", 2)[-1]
require(
    '"relayURL"' in resolver,
    "resolver does not return relay URLs",
)
require(
    "googlevideo" not in resolver.lower(),
    "resolver source should not hardcode direct googlevideo delivery",
)

if errors:
    print("V9 MEDIA LAB AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V9 MEDIA LAB AUDIT PASSED")
print(" - legacy WebKit/AVPlayer engines excluded from V9 target")
print(" - MPVKit 1.0.1 non-GPL product pinned")
print(" - one persistent libmpv transport owner")
print(" - separate video/audio relay load path present")
print(" - native lock-screen ownership present")
print(" - background lifecycle does not pause MPV")
print(" - resolver hides upstream media behind Range relay")
print(" - yt-dlp and Node runtime pinned for laboratory")
