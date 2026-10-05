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
root_view = read("V9/V9ClientRootView.swift")
browse_views = read("V9/V9BrowseViews.swift")
player_ui = read("V9/V9PlayerUI.swift")
player = read("V9/V9PlayerService.swift")
player_view = read("V9/V9MPVPlayerView.swift")
client = read("V9/VcdResolverClient.swift")
models = read("V9/ResolverModels.swift")
token_store = read("V9/ResolverTokenStore.swift")
render_view = read("V9/V9MPVRenderView.swift")
render_core = read("V9/V9MPVRenderCore.swift")
pip_bridge = read("V9/V9MPVPiPBridge.swift")
resolver = read("Resolver/app/main.py")
dockerfile = read("Resolver/Dockerfile")
requirements = read("Resolver/requirements.txt")
workflow = read(".github/workflows/ios-build.yml")

all_v9 = "\n".join(
    p.read_text(encoding="utf-8")
    for p in V9.glob("*.swift")
)

# Release identity: this is a native client, not the old Media Lab.
require('MARKETING_VERSION: "0.10.0"' in project, "client version must be 0.10.0")
require('CURRENT_PROJECT_VERSION: "6"' in project, "client build must be 6")
require("CFBundleDisplayName: YoutubeVcd" in project, "display name must be YoutubeVcd")
require('test "$VERSION" = "0.10.0"' in workflow, "CI version audit is stale")
require('test "$BUILD" = "6"' in workflow, "CI build audit is stale")
require('test "$DISPLAY_NAME" = "YoutubeVcd"' in workflow, "CI display-name audit is stale")
require("V9ClientRootView()" in app, "app still launches the old lab UI")
require(not (V9 / "V9MediaLabView.swift").exists(), "obsolete video-ID Media Lab still exists")

# The normal app flow must be a usable YouTube browser.
for required in [
    "TabView",
    "V9HomeFeedView",
    "V9SearchView",
    "V9SettingsSummaryView",
    "V9MiniPlayerView",
    "V9PlayerSheet",
]:
    require(required in root_view, f"root client UI missing: {required}")

for required in [
    "struct V9HomeFeedView",
    "struct V9SearchView",
    "struct V9VideoFeed",
    "struct V9VideoCard",
    "struct V9ChannelView",
    "AsyncImage",
    ".searchable(",
    ".home(",
    ".search(",
    ".channel(",
]:
    require(required in browse_views, f"native browsing UI missing: {required}")

for required in [
    "struct V9MiniPlayerView",
    "struct V9PlayerSheet",
    "V9MPVPlayerView",
    "player.togglePiP()",
    "player.seek(",
    "V9ResolverSettingsView",
]:
    require(required in player_ui, f"player/settings UI missing: {required}")

require("YouTube video ID" not in all_v9, "manual video-ID input leaked back into normal UI")
require('"V9 Media Lab"' not in all_v9, "Media Lab branding leaked back into app UI")

# Browse data contract and client calls.
for required in [
    "struct BrowseVideo",
    "Identifiable",
    "thumbnailURL",
    "channelID",
    "viewCount",
    "isLive",
    "struct BrowseResponse",
]:
    require(required in models, f"browse model missing: {required}")

for required in [
    "func home(",
    "func search(",
    "func channel(",
    '"home"',
    '"search"',
    '"channel"',
]:
    require(required in client, f"resolver browse client missing: {required}")

# Player architecture remains MPV-only.
require("path: V9" in project, "V9 source root missing")
require("exactVersion: 1.0.1" in project, "MPVKit version must remain pinned")
require("product: MPVKit" in project and "MPVKit-GPL" not in project, "wrong MPVKit product")
require("UIBackgroundModes:" in project and "- audio" in project, "background audio mode missing")

for forbidden in [
    "import WebKit",
    "import YouTubeKit",
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
    "MPRemoteCommandCenter",
    "MPNowPlayingInfoCenter",
    "desiredPlayback",
    "recoverFromStreamFailure",
    "reportExternalFailure",
]:
    require(required in player, f"player invariant missing: {required}")

# Persistent surface and off-main software rendering.
for required in [
    "persistentRenderSurface",
    "renderSurfaceHostToken",
    "setRenderSurfaceHosted",
]:
    require(required in player, f"persistent surface invariant missing: {required}")

for required in [
    "hostToken",
    "dismantleUIView",
    "persistentRenderSurface()",
]:
    require(required in player_view, f"SwiftUI surface host invariant missing: {required}")

for required in [
    "final class V9MPVRenderCore",
    "NSLock",
    "MPV_RENDER_API_TYPE_SW",
    "MPV_RENDER_PARAM_SW_POINTER",
    "MPV_RENDER_PARAM_SKIP_RENDERING",
    "mpv_render_context_render",
]:
    require(required in render_core, f"software render core invariant missing: {required}")

for required in [
    '"com.tzn5web.leno.v9.render"',
    "renderQueue.async",
    "CVPixelBufferPoolCreate",
    "AVSampleBufferDisplayLayer",
    "CMSampleBufferCreateReadyWithImageBuffer",
    "frameGeneration",
]:
    require(required in render_view, f"render-view invariant missing: {required}")

# PiP / lifecycle / remote controls.
for required in [
    "AVPictureInPictureController",
    "AVPictureInPictureSampleBufferPlaybackDelegate",
    "sampleBufferDisplayLayer:",
    "skipByInterval",
    "setPlaying",
    "prepareForMediaChange",
    "prepareForSeek",
    "stopIfActive",
]:
    require(required in pip_bridge, f"PiP invariant missing: {required}")

for required in [
    "interruptionNotification",
    "routeChangeNotification",
    "mediaServicesWereResetNotification",
    "shouldResume",
    "deactivateAudioSession",
    "changePlaybackPositionCommand",
    "skipForwardCommand",
    "skipBackwardCommand",
]:
    require(required in player, f"audio/remote invariant missing: {required}")

require(
    player.count("!new_stream;!no_clip;!no_chapters;") >= 2,
    "separate video/audio EDL headers are incomplete",
)
require(
    "guard hasLoadedMedia" in player,
    "remote seek can run without loaded media",
)

# Keychain and resolver transport.
for required in [
    "SecItemCopyMatching",
    "SecItemUpdate",
    "SecItemAdd",
    "kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly",
]:
    require(required in token_store, f"Keychain invariant missing: {required}")

for required in [
    "ResolverNoRedirectDelegate",
    "willPerformHTTPRedirection",
    "sameOrigin(",
    "relayOriginMismatch",
    "insecureTokenTransport",
    "insecurePublicHTTP",
    "inet_pton(",
    "AF_INET6",
]:
    require(required in client, f"client transport invariant missing: {required}")

# Resolver must now support browsing plus playback.
for required in [
    'APP_VERSION = "0.4.0-client"',
    "VIDEO_ID_RE",
    "CHANNEL_ID_RE",
    "SEARCH_QUERY_RE",
    "BROWSE_LIMIT",
    "browse_video_entry",
    "extract_browse",
    '@app.get("/v1/home")',
    '@app.get("/v1/search")',
    '@app.get("/v1/channel/{channel_id}")',
    '@app.get("/v1/thumb/{video_id}")',
    "ytsearch",
    '":ytrec"',
    "thumbnailURL",
    "client_browse",
]:
    require(required in resolver, f"native browse resolver invariant missing: {required}")

for required in [
    "refresh_relay_entry",
    'methods=["GET", "HEAD"]',
    "VCD_API_TOKEN",
    "VCD_PUBLIC_BASE_URL",
    "VCD_COOKIES_FILE",
    "VCD_MAX_CONCURRENT_EXTRACTS",
    "VCD_MAX_VIDEO_HEIGHT",
    "VCD_MAX_VIDEO_FPS",
    "validated_upstream_url",
    "follow_redirects=False",
    '"Accept-Encoding"] = "identity"',
    "aiter_raw",
    "peer_host = request.client.host",
]:
    require(required in resolver, f"relay hardening invariant missing: {required}")

require("read=None" not in resolver, "upstream read timeout became unbounded")
require("aiter_bytes" not in resolver, "relay is transparently decoding media bytes")
require("googlevideo" not in resolver.lower(), "resolver hardcodes raw googlevideo URLs")
require("extraction_semaphore" in resolver, "yt-dlp extraction concurrency is unbounded")
require("asyncio.CancelledError" in resolver and "proc.kill()" in resolver, "yt-dlp process can leak after cancellation")

# CI must test the new client APIs, not only /health.
for required in [
    "Native client API smoke",
    "fake_ytdlp.py",
    "/v1/home",
    "/v1/search",
    "/v1/channel/UCaaaaaaaaaaaaaaaaaaaaaa",
    "/v1/video/dQw4w9WgXcQ",
    'assert health["version"] == "0.4.0-client"',
    'assert health["client_browse"] is True',
]:
    require(required in workflow, f"client API CI gate missing: {required}")

require(
    "denoland/deno:bin-2.9.7" in dockerfile,
    "resolver Docker runtime is not pinned to Deno 2.9.7",
)
require(
    "yt-dlp==2026.08.19" in requirements
    and "yt-dlp-ejs==0.8.0" in requirements,
    "resolver extraction versions are not pinned",
)

if errors:
    print("YOUTUBE VCD 0.10 CLIENT AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("YOUTUBE VCD 0.10 CLIENT AUDIT PASSED")
print(" - app launches native Home/Search/Channel browsing, not Media Lab")
print(" - native mini-player and full persistent MPV player are wired")
print(" - Home/Search/Channel/Resolve APIs have deterministic HTTP CI smoke")
print(" - no WebKit/AVPlayer/OpenGL ES playback path")
print(" - background/PiP/remote controls remain on one persistent MPV engine")
print(" - resolver transport and relay hardening remain enforced")
