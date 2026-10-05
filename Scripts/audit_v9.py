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
app = read("V9/V9App.swift")
root = read("V9/V9ClientRootView.swift")
browse = read("V9/V9BrowseViews.swift")
native = read("V9/V9NativeYouTubeClient.swift")
playback_worker = read("V9/V9NativePlaybackWorker.swift")
player_ui = read("V9/V9PlayerUI.swift")
player = read("V9/V9PlayerService.swift")
player_view = read("V9/V9MPVPlayerView.swift")
render_view = read("V9/V9MPVRenderView.swift")
render_core = read("V9/V9MPVRenderCore.swift")
pip_bridge = read("V9/V9MPVPiPBridge.swift")
resolver_client = read("V9/VcdResolverClient.swift")
token_store = read("V9/ResolverTokenStore.swift")
resolver = read("Resolver/app/main.py")
workflow = read(".github/workflows/ios-build.yml")
architecture_doc = read("V9_ARCHITECTURE_AUDIT.md")

all_v9 = "\n".join(
    p.read_text(encoding="utf-8")
    for p in V9.glob("*.swift")
)

# Release identity.
require('MARKETING_VERSION: "0.11.2"' in project, "version must be 0.11.2")
require('CURRENT_PROJECT_VERSION: "9"' in project, "build must be 9")
require('test "$VERSION" = "0.11.2"' in workflow, "CI version audit is stale")
require('test "$BUILD" = "9"' in workflow, "CI build audit is stale")
require("V9ClientRootView()" in app, "app does not launch native client")

# Native autonomous YouTube dependency.
require("YouTubeKit:" in project, "YouTubeKit package missing")
require("https://github.com/b5i/YouTubeKit.git" in project, "wrong YouTubeKit package")
require(
    "6532af39da4c1612b0a1af603792419d8fb0e67f" in project,
    "YouTubeKit revision is not pinned to audited revision",
)
require("product: YouTubeKit" in project, "YouTubeKit product not linked")

for required in [
    "import YouTubeKit",
    "HomeScreenResponse",
    "SearchResponse",
    "ChannelInfosResponse",
    "fetchContinuationThrowing",
    "mergeContinuation",
    "getChannelContentContinuationThrowing",
    "V9NativeYouTubeClient",
    "V9NativePlaybackWorker",
    "discoveryState",
]:
    require(required in native, f"native YouTube invariant missing: {required}")


# Native playback resolution must stay off MainActor and use the JSON Innertube
# response type for TVHTML5. The previous .videoInfos override fed JSON into an
# HTML watch-page decoder and was not a valid fallback.
for required in [
    "actor V9NativePlaybackWorker",
    "VideoInfosWithDownloadFormatsResponse",
    ".videoInfosWithDownloadFormats",
    '"TVHTML5"',
    '"7.20260707.07.00"',
    '"X-Youtube-Client-Name"',
    '"7"',
    "streamingURL",
    '"hls-vod"',
    '"hls-live"',
    "VideoInfosResponse",
    "processDownloadFormatURL",
    "/watch page",
    "VideoDownloadFormat",
    "AudioOnlyFormat",
    "ensureVisitorData",
]:
    require(required in playback_worker, f"native playback worker invariant missing: {required}")

require(
    "TVHTML5_SIMPLY_EMBEDDED_PLAYER" not in playback_worker,
    "obsolete TVHTML5_SIMPLY_EMBEDDED_PLAYER path returned",
)
require(
    "customHeaders[\n                .videoInfos\n" not in playback_worker,
    "TV Innertube JSON was wired back to the HTML .videoInfos decoder",
)
require(
    "VideoInfosResponse\n                .sendThrowingRequest" in playback_worker
    and "processDownloadFormatURL" in playback_worker,
    "secondary native fallback is not the real watch-page/player.js decipher path",
)
require(
    ".fetchStreamingInfosWithDownloadFormatsThrowing(" not in playback_worker,
    "stale iOS Innertube fallback returned; it can require GVS PO tokens",
)
require(
    "if let hls =" in playback_worker
    and "info.streamingURL" in playback_worker
    and "isLive" not in playback_worker.split("if let hls =", 1)[0][-160:],
    "HLS-first policy is not applied to both VOD and live media",
)
require(
    "private let playbackWorker" in native
    and "try await playbackWorker" in native,
    "MainActor client still performs heavy stream resolution itself",
)
require(
    "guard let watchPlayer" in playback_worker
    and "processFormats(" in playback_worker
    and "decodeNParameterInHLSManifestURL" in playback_worker,
    "TVHTML5 media can bypass watch-page player.js deciphering",
)

# Normal UI may not require/configure an external resolver.
require("V9HomeFeedView" in root and "V9SearchView" in root, "Home/Search missing")
require("@StateObject" in root and "V9NativeYouTubeClient()" in root, "native client state is not persistent")
require(
    "try await native" in root and ".resolve(" in root,
    "playback does not resolve natively first",
)
require(
    "resolveRefresh" in root
    and "try await resolver" in root
    and "return try await native" in root,
    "playback recovery does not use optional resolver as an independent fallback",
)
require(
    "fallbackEndpoint" in root and "guard !endpoint" in root,
    "optional resolver fallback path missing",
)
require(
    "showSettings =\n                true" not in root,
    "app still forces resolver settings at launch",
)
require(
    "endpoint:" not in browse
    and "resolverToken:" not in browse
    and "VcdResolverClient" not in browse,
    "Home/Search/Channel still depend on external resolver",
)
require(
    ".home(" in browse
    and ".search(" in browse
    and ".channel(" in browse
    and "V9NativeYouTubeClient" in browse,
    "browse views are not wired to native client",
)
require(
    "hasMore" in browse and "loadMore" in browse and ".onAppear" in browse,
    "infinite continuation loading is missing",
)
require(
    "Fallback opțional" in player_ui
    and "nu este necesar" in player_ui,
    "settings still present resolver as mandatory",
)

require(
    "V9MPVPlayerView" in player_ui
    and ".allowsHitTesting(" in player_ui
    and "width:\n                        96" in player_ui,
    "mini player still shows a placeholder instead of the persistent video surface",
)
require(
    "!showPlayer" in root,
    "mini player is not relinquishing the render surface while full player is open",
)

# No old lab/manual ID UX.
require(not (V9 / "V9MediaLabView.swift").exists(), "old Media Lab file returned")
require("YouTube video ID" not in all_v9, "manual video-ID input returned")
require('"V9 Media Lab"' not in all_v9, "Media Lab branding returned")

# Player stays MPV-only.
require("exactVersion: 1.0.1" in project, "MPVKit pin changed")
require("product: MPVKit" in project and "MPVKit-GPL" not in project, "wrong MPVKit product")
require("UIBackgroundModes:" in project and "- audio" in project, "background audio mode missing")

for forbidden in [
    "import WebKit",
    "WKWebView(",
    "AVPlayer(",
    "AVQueuePlayer(",
    "BackgroundAudioHandoff(",
    "import OpenGLES",
    "EAGLContext",
    "CAEAGLLayer",
    "glReadPixels",
    "MPV_RENDER_API_TYPE_OPENGL",
]:
    require(forbidden not in all_v9, f"forbidden playback symbol returned: {forbidden}")

for required in [
    "mpv_create()",
    "mpv_initialize",
    '"vo"',
    '"libmpv"',
    '"hwdec"',
    '"videotoolbox-copy"',
    '"sw-fast"',
    '"hls-bitrate"',
    '"8000000"',
    "MPRemoteCommandCenter",
    "MPNowPlayingInfoCenter",
    "desiredPlayback",
    "recoverFromStreamFailure",
    "deactivateAudioSession",
]:
    require(required in player, f"MPV player invariant missing: {required}")

# Persistent render surface and off-main software rendering.
for required in [
    "persistentRenderSurface",
    "renderSurfaceHostToken",
    "setRenderSurfaceHosted",
]:
    require(required in player, f"persistent render invariant missing: {required}")

for required in [
    "hostToken",
    "dismantleUIView",
    "persistentRenderSurface()",
]:
    require(required in player_view, f"persistent SwiftUI host invariant missing: {required}")

for required in [
    "final class V9MPVRenderCore",
    "NSLock",
    "MPV_RENDER_API_TYPE_SW",
    "MPV_RENDER_PARAM_SW_POINTER",
    "MPV_RENDER_PARAM_SKIP_RENDERING",
    "mpv_render_context_render",
]:
    require(required in render_core, f"render core invariant missing: {required}")

for required in [
    '"com.tzn5web.leno.v9.render"',
    "renderQueue.async",
    "CVPixelBufferPoolCreate",
    "AVSampleBufferDisplayLayer",
    "CMSampleBufferCreateReadyWithImageBuffer",
    "frameGeneration",
]:
    require(required in render_view, f"render view invariant missing: {required}")

# PiP/background/remote control state machine.
for required in [
    "AVPictureInPictureController",
    "AVPictureInPictureSampleBufferPlaybackDelegate",
    "sampleBufferDisplayLayer:",
    "skipByInterval",
    "setPlaying",
    "prepareForMediaChange",
    "prepareForSeek",
]:
    require(required in pip_bridge, f"PiP invariant missing: {required}")

for required in [
    "interruptionNotification",
    "routeChangeNotification",
    "mediaServicesWereResetNotification",
    "shouldResume",
    "changePlaybackPositionCommand",
    "skipForwardCommand",
    "skipBackwardCommand",
]:
    require(required in player, f"audio/remote invariant missing: {required}")

require(
    player.count("!new_stream;!no_clip;!no_chapters;") >= 2,
    "separate video/audio EDL headers incomplete",
)
require(
    "stablePlaybackResetInterval" in player
    and "lastSuccessfulLoadAt" in player
    and "timeIntervalSince" in player,
    "stream recovery retry budget still resets on FILE_LOADED instead of stable playback",
)

# Native playback supports live HLS without AVPlayer.
require(
    "adaptiveFormats:" in playback_worker
    and "progressiveFormats:" in playback_worker
    and '"embedded"' in playback_worker,
    "native resolver cannot handle adaptive/progressive fallback media",
)
require(
    "discoveryState" in native
    and "discoveryFallback(" in native
    and "continuationToken" in native,
    "anonymous Home fallback is not paginated",
)

# Native VOD format policy.
for required in [
    "1080",
    "isEligibleVideo",
    "isPreferredH264MP4",
    "bestVideo",
    '"avc1"',
    '"h264"',
    '"mp4a"',
    '"aac"',
]:
    require(required in playback_worker, f"native format policy missing: {required}")

require(
    "fps" in playback_worker and "30" in playback_worker,
    "native video frame-rate cap is missing",
)

# Optional fallback remains hardened, but it must not be required.
require(
    "VcdResolverClient()" in root and "fallbackEndpoint" in root,
    "optional resolver fallback was removed entirely",
)
for required in [
    "ResolverNoRedirectDelegate",
    "sameOrigin(",
    "insecureTokenTransport",
    "relayOriginMismatch",
]:
    require(required in resolver_client, f"fallback transport invariant missing: {required}")

for required in [
    "SecItemCopyMatching",
    "SecItemUpdate",
    "SecItemAdd",
]:
    require(required in token_store, f"fallback Keychain invariant missing: {required}")

# Resolver backend remains tested as fallback only.
require('APP_VERSION = "0.4.0-client"' in resolver, "fallback resolver version changed unexpectedly")
require("Native client API smoke" in workflow, "fallback resolver API smoke missing")
require("/v1/home" in workflow and "/v1/video/dQw4w9WgXcQ" in workflow, "fallback smoke incomplete")

require(
    "YoutubeVcd 0.11.2 build 9" in architecture_doc
    and "optional resolver fallback" in architecture_doc.lower()
    and "0.10.0 build 6" not in architecture_doc,
    "architecture document is stale or still describes the mandatory 0.10 resolver design",
)
require(
    "vcd-resolver:fallback-0.4" in workflow
    and "vcd-resolver:v0.10" not in workflow,
    "resolver CI image is still named as the old mandatory 0.10 architecture",
)

if errors:
    print("YOUTUBEVCD 0.11 AUTONOMOUS CLIENT AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("YOUTUBEVCD 0.11.2 AUTONOMOUS CLIENT AUDIT PASSED")
print(" - Home/Search/Channel are native on-device and paginated")
print(" - video stream URLs are resolved off-MainActor with YouTubeKit")
print(" - TVHTML5 Innertube JSON uses the correct response decoder and HLS-first playback")
print(" - resolver is optional fallback, not an app prerequisite")
print(" - VOD split streams and live HLS feed the same persistent MPV engine")
print(" - no WebKit/AVPlayer/OpenGL ES playback path")
print(" - background/PiP/lock-screen state machine remains intact")
