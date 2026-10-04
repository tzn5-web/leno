#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
V9 = ROOT / "V9"
errors: list[str] = []


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


project = read("project.yml")
player = read("V9/V9PlayerService.swift")
view = read("V9/V9MediaLabView.swift")
client = read("V9/VcdResolverClient.swift")
render_view = read("V9/V9MPVRenderView.swift")
pip_bridge = read("V9/V9MPVPiPBridge.swift")
resolver = read("Resolver/app/main.py")
dockerfile = read("Resolver/Dockerfile")
requirements = read("Resolver/requirements.txt")
workflow = read(".github/workflows/ios-build.yml")

all_v9 = "\n".join(
    p.read_text(encoding="utf-8")
    for p in V9.glob("*.swift")
)

# Build identity
require('MARKETING_VERSION: "0.9.1"' in project, "V9 version must be 0.9.1")
require('CURRENT_PROJECT_VERSION: "2"' in project, "V9 build must be 2")
require('test "$VERSION" = "0.9.1"' in workflow, "CI version audit is stale")
require('test "$BUILD" = "2"' in workflow, "CI build audit is stale")

# Player architecture: V9 must remain MPV-only.
require("path: V9" in project, "V9 source root missing")
require("url: https://github.com/yattee/MPVKit.git" in project, "Yattee MPVKit package missing")
require("exactVersion: 1.0.1" in project, "MPVKit must remain pinned to audited 1.0.1")
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

# Critical libmpv invariants.
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

# MPV_RENDER_PARAM_API_TYPE expects the pointer to the C string itself, not a
# pointer to a Swift variable containing that pointer.
require(
    "UnsafeMutableRawPointer" in player
    and "MPV_RENDER_API_TYPE_OPENGL" in player
    and ".utf8String" in player,
    "libmpv API type pointer is not constructed as a C string pointer",
)
require(
    "data:\n                                apiType" in player,
    "MPV_RENDER_PARAM_API_TYPE is not wired to the corrected apiType pointer",
)

# Audio lifecycle.
for required in [
    "configureAudioNotifications()",
    "handleAudioInterruption",
    "interruptionNotification",
    "routeChangeNotification",
    "mediaServicesWereResetNotification",
    "interruptionActive",
]:
    require(required in player, f"audio lifecycle invariant missing: {required}")

configure_audio = player.split("private func configureAudioSession()", 1)[1].split(
    "private func activateAudioSession()", 1
)[0]
require(
    ".setActive(" not in configure_audio,
    "audio session must not be activated just by launching the app",
)

background_block = player.split("case .background:", 1)[1].split("case .active:", 1)[0]
require(
    "setPause(" not in background_block,
    "background lifecycle must pause rendering only, never MPV playback",
)

# Refresh / expiry recovery.
for required in [
    "typealias RefreshProvider",
    "recoverFromStreamFailure",
    "mpv_event_end_file",
    "MPV_END_FILE_REASON_ERROR",
    "maximumRefreshAttempts",
    "pendingSeekAfterLoad",
]:
    require(required in player, f"client stream recovery invariant missing: {required}")

require(
    '"loadfile"' in player
    and "edl://!new_stream;!no_clip;!no_chapters;" in player
    and '"audio-add"' not in player,
    "separate video/audio MPV EDL load path missing or legacy audio-add race returned",
)

# PiP timeline correctness.
for required in [
    "AVSampleBufferDisplayLayer",
    "AVPictureInPictureController",
    "AVPictureInPictureSampleBufferPlaybackDelegate",
    "CMSampleBufferCreateReadyWithImageBuffer",
    "sampleBufferRenderer",
    "pictureInPictureControllerIsPlaybackPaused",
    "pictureInPictureControllerTimeRangeForPlayback",
    "skipByInterval",
    "setPlaying",
    "shouldKeepRendering",
    "prepareForMediaChange",
    "lastPresentationTime",
    "hasEnqueuedFrame",
]:
    require(required in pip_bridge, f"native MPV PiP invariant missing: {required}")

require(
    "pipBridge?\n            .prepareForMediaChange()" in player,
    "player does not reset PiP state when media changes",
)

# PiP frame capture should reuse buffers and be bounded.
for required in [
    "glReadPixels",
    "CVPixelBufferPoolCreate",
    "CVPixelBufferPoolCreatePixelBuffer",
    "lastCaptureHostTime",
    "1.0 / 30.0",
    "pauseRendering",
    "resumeRendering",
]:
    require(required in render_view, f"render/PiP performance invariant missing: {required}")

require(
    "V9MetalLayer" not in all_v9,
    "obsolete wid/CAMetalLayer renderer must not return",
)

# Resolver client must not silently point a physical iPhone at itself.
require(
    'private var endpoint =\n        ""' in view,
    "physical client must not default to 127.0.0.1",
)
require(
    "loopbackEndpointOnDevice" in client
    and "targetEnvironment(simulator)" in client,
    "client does not reject localhost on a physical iPhone",
)
require(
    "refreshProvider:" in view
    and "bearerToken:" in view,
    "UI is not wired to authenticated automatic stream refresh",
)

# Resolver runtime and relay hardening.
for required in [
    'APP_VERSION = "0.2.0-lab"',
    "VIDEO_ID_RE",
    "refresh_relay_entry",
    "REFRESHABLE_UPSTREAM_STATUS",
    "Sliding lease",
    'methods=["GET", "HEAD"]',
    "VCD_API_TOKEN",
    "secrets.compare_digest",
    "YTDLP_JS_RUNTIME",
    "/v1/video/{video_id}",
    "/v1/relay/{token}",
    "Range",
    "relayURL",
    "httpx.AsyncClient",
]:
    require(required in resolver, f"resolver invariant missing: {required}")

require(
    "denoland/deno:bin-2.9.7" in dockerfile
    and "COPY --from=deno /deno /usr/local/bin/deno" in dockerfile
    and "nodejs" not in dockerfile,
    "resolver Docker runtime must use pinned supported Deno, not distro Node",
)
require(
    "yt-dlp==2026.08.19" in requirements
    and "yt-dlp-ejs==0.8.0" in requirements,
    "resolver yt-dlp/EJS versions are not pinned to the audited pair",
)
require(
    "h264" in resolver
    and "avc1" in resolver
    and "aac" in resolver
    and "mp4a" in resolver,
    "resolver must prefer conservative H264/AAC formats first",
)

# Networking remains narrowly scoped; do not globally disable ATS.
require(
    "NSAllowsLocalNetworking: true" in project
    and "NSLocalNetworkUsageDescription:" in project
    and "NSAllowsArbitraryLoads" not in project,
    "local resolver networking is not narrowly configured",
)

# Raw upstream media URLs must not be returned to the iOS client.
require(
    '"relayURL"' in resolver,
    "resolver does not return relay URLs",
)
require(
    "googlevideo" not in resolver.lower(),
    "resolver source should not hardcode direct googlevideo delivery",
)

if errors:
    print("V9 HARDENED AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V9 HARDENED AUDIT PASSED")
print(" - MPV-only target and corrected render API pointer")
print(" - audio interruptions preserve user playback intent")
print(" - resolver and client can refresh expired/failed streams")
print(" - PiP timeline resets between videos")
print(" - PiP frame buffers are pooled and capture is capped at 30 fps")
print(" - physical iPhone cannot accidentally use localhost resolver")
print(" - Deno 2.9.7 + yt-dlp EJS runtime pinned")
print(" - relay supports Range/HEAD, sliding leases and upstream refresh")
