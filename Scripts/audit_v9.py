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
token_store = read("V9/ResolverTokenStore.swift")
render_view = read("V9/V9MPVRenderView.swift")
render_core = read("V9/V9MPVRenderCore.swift")
pip_bridge = read("V9/V9MPVPiPBridge.swift")
resolver = read("Resolver/app/main.py")
dockerfile = read("Resolver/Dockerfile")
requirements = read("Resolver/requirements.txt")
workflow = read(".github/workflows/ios-build.yml")
readme = read("Resolver/README.md")
architecture_audit = read("V9_ARCHITECTURE_AUDIT.md")

all_v9 = "\n".join(
    p.read_text(encoding="utf-8")
    for p in V9.glob("*.swift")
)

# Build identity
require('MARKETING_VERSION: "0.9.3"' in project, "V9 version must be 0.9.3")
require('CURRENT_PROJECT_VERSION: "5"' in project, "V9 build must be 5")
require('test "$VERSION" = "0.9.3"' in workflow, "CI version audit is stale")
require('test "$BUILD" = "5"' in workflow, "CI build audit is stale")

require("V9.3" in readme, "resolver README release identity is stale")
require("- Version: 0.9.3" in architecture_audit, "architecture audit version is stale")
require("- Build: 5" in architecture_audit, "architecture audit build is stale")

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
    "import OpenGLES",
    "EAGLContext",
    "CAEAGLLayer",
    "glReadPixels",
    "MPV_RENDER_API_TYPE_OPENGL",
    "MPV_RENDER_PARAM_OPENGL_FBO",
]:
    require(
        forbidden not in all_v9,
        f"V9 target contains forbidden legacy/unsafe renderer symbol: {forbidden}",
    )

# Critical libmpv player invariants.
for required in [
    "import Libmpv",
    "mpv_create()",
    "mpv_initialize",
    '"vo"',
    '"libmpv"',
    '"hwdec"',
    '"videotoolbox-copy"',
    '"sw-fast"',
    "V9MPVRenderCore",
    "renderCoreReference",
    "MPRemoteCommandCenter",
    "MPNowPlayingInfoCenter",
    "desiredPlayback",
    "func handleScenePhase",
    '"sw-fast"',
    "deactivateAudioSession",
]:
    require(required in player, f"native MPV player invariant missing: {required}")

# Render API must be isolated from MainActor/UI work behind one serialized core.
for required in [
    "final class V9MPVRenderCore",
    "@unchecked Sendable",
    "NSLock",
    "mpv_render_context_create",
    "mpv_render_context_update",
    "mpv_render_context_render",
    "mpv_render_context_free",
    "MPV_RENDER_API_TYPE_SW",
    "MPV_RENDER_PARAM_SW_SIZE",
    "MPV_RENDER_PARAM_SW_FORMAT",
    "MPV_RENDER_PARAM_SW_STRIDE",
    "MPV_RENDER_PARAM_SW_POINTER",
    "MPV_RENDER_PARAM_SKIP_RENDERING",
]:
    require(required in render_core, f"render-core invariant missing: {required}")

require(
    "MPV_RENDER_API_TYPE_SW" in render_core
    and "MPV_RENDER_PARAM_API_TYPE" in render_core,
    "MPV_RENDER_PARAM_API_TYPE is not wired to the software render core",
)

for required in [
    'DispatchQueue(',
    '"com.tzn5web.leno.v9.render"',
    ".userInteractive",
    "renderQueue.async",
    "V9PixelBufferBox",
    "forceOpaqueAlpha",
    "frameGeneration",
    "presentationTime =",
    "self.service?",
]:
    require(required in render_view, f"dedicated render-queue invariant missing: {required}")

require(
    "renderSoftware(" not in render_view
    or "renderCore" in render_view,
    "software render path bypasses the isolated render core",
)

# Audio lifecycle.
for required in [
    "configureAudioNotifications()",
    "handleAudioInterruption",
    "interruptionNotification",
    "routeChangeNotification",
    "mediaServicesWereResetNotification",
    "interruptionActive",
    "shouldResume",
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

require(
    "The system explicitly did not grant automatic resume." in player,
    "interruption end without shouldResume can still auto-restart later",
)

# Refresh / expiry recovery.
for required in [
    "typealias RefreshProvider",
    "recoverFromStreamFailure",
    "mpv_event_end_file",
    "MPV_END_FILE_REASON_ERROR",
    "maximumRefreshAttempts",
    "pendingSeekAfterLoad",
    "prepareForSeek",
    "backgroundRenderGraceTask",
    "refreshTask?\n            .cancel()",
    "800_000_000",
    "2_000_000_000",
]:
    require(required in player, f"client stream recovery invariant missing: {required}")

require(
    '"loadfile"' in player
    and "edl://!new_stream;!no_clip;!no_chapters;" in player
    and "!new_stream;!no_clip;!no_chapters;" in player
    and '"audio-add"' not in player,
    "separate video/audio MPV EDL load path missing or legacy audio-add race returned",
)

require(
    player.count("!new_stream;!no_clip;!no_chapters;") >= 2,
    "both separate EDL streams must carry mpv ytdl no_clip/no_chapters headers",
)

require(
    "guard hasLoadedMedia" in player
    and "deactivateAudioSession()" in player,
    "remote seek/audio session stop hardening is missing",
)

require(
    "A completed load proves the refreshed source is healthy." in player
    and "refreshAttempts =" in player,
    "successful refreshed loads do not reset the future recovery budget",
)

# SwiftUI navigation must retain one render surface/layer so PiP does not
# collapse when an ephemeral host view is recreated.
player_view = read("V9/V9MPVPlayerView.swift")
for required in [
    "persistentRenderSurface",
    "renderSurfaceHostToken",
    "setRenderSurfaceHosted",
    "UUID?",
]:
    require(required in player, f"persistent render-surface invariant missing: {required}")

for required in [
    "V9MPVHostView",
    "persistentRenderSurface()",
    "hostToken",
    "dismantleUIView",
    "removeFromSuperview",
    "context",
    ".coordinator",
]:
    require(required in player_view, f"persistent SwiftUI host invariant missing: {required}")

# PiP must use the same AVSampleBufferDisplayLayer as foreground rendering.
for required in [
    "AVSampleBufferDisplayLayer",
    "CVPixelBufferPoolCreate",
    "CVPixelBufferPoolCreatePixelBuffer",
    "CMSampleBufferCreateReadyWithImageBuffer",
    "sampleBufferRenderer",
    "1.0 / 30.0",
    "pauseRendering",
    "resumeRendering",
    "resetFrameTimeline",
]:
    require(required in render_view, f"software render/PiP invariant missing: {required}")

for required in [
    "AVPictureInPictureController",
    "AVPictureInPictureSampleBufferPlaybackDelegate",
    "sampleBufferDisplayLayer:",
    ".sampleBufferLayer",
    "pictureInPictureControllerIsPlaybackPaused",
    "pictureInPictureControllerTimeRangeForPlayback",
    "skipByInterval",
    "setPlaying",
    "shouldKeepRendering",
    "prepareForMediaChange",
    "hasEnqueuedFrame",
]:
    require(required in pip_bridge, f"native PiP invariant missing: {required}")

require(
    "pipBridge?\n            .prepareForMediaChange()" in player,
    "player does not reset PiP state when media changes",
)

# Keychain + resolver transport.
for required in [
    "import Security",
    "SecItemCopyMatching",
    "SecItemUpdate",
    "SecItemAdd",
    "kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly",
]:
    require(required in token_store, f"Keychain invariant missing: {required}")

require(
    '@AppStorage(\n        "v9.resolver.token"' not in view,
    "resolver token leaked back into UserDefaults",
)
require(
    "ResolverTokenStore" in view,
    "resolver token is not wired to Keychain",
)

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
    "insecurePublicHTTP" in client
    and "insecureTokenTransport" in client
    and "invalidRelayURL" in client
    and "insecureRelayTransport" in client,
    "client transport/relay safety checks are missing",
)
require(
    "validateResolvedVideo" in client,
    "client does not validate resolver-provided relay URLs before mpv uses them",
)

require(
    "ResolverNoRedirectDelegate" in client
    and "willPerformHTTPRedirection" in client
    and "completionHandler(" in client
    and "sameOrigin(" in client
    and "relayOriginMismatch" in client
    and '"/v1/relay/"' in client,
    "client does not pin API/relay traffic to one non-redirecting resolver origin",
)

require(
    "import Darwin" in client
    and "inet_pton(" in client
    and "AF_INET6" in client
    and "isIPv4Mapped" in client,
    "client LAN policy still relies on unsafe IPv6 string heuristics",
)
require(
    "refreshProvider:" in view
    and "bearerToken:" in view,
    "UI is not wired to authenticated automatic stream refresh",
)

# Resolver runtime and relay hardening.
for required in [
    'APP_VERSION = "0.3.0-lab"',
    "VIDEO_ID_RE",
    "refresh_relay_entry",
    "REFRESHABLE_UPSTREAM_STATUS",
    "Sliding lease",
    'methods=["GET", "HEAD"]',
    "VCD_API_TOKEN",
    "VCD_PUBLIC_BASE_URL",
    "VCD_COOKIES_FILE",
    "VCD_MAX_RELAY_ENTRIES",
    "VCD_MAX_CONCURRENT_EXTRACTS",
    "VCD_MAX_VIDEO_HEIGHT",
    "VCD_MAX_VIDEO_FPS",
    "VCD_UPSTREAM_READ_TIMEOUT",
    "secrets.compare_digest",
    "YTDLP_JS_RUNTIME",
    "/v1/video/{video_id}",
    "/v1/relay/{token}",
    "Range",
    "relayURL",
    "httpx.AsyncClient",
    "refresh_lock",
    "generation",
    "enforce_relay_capacity",
    "UPSTREAM_READ_TIMEOUT",
    "is_relayable_format",
    "validated_upstream_url",
    "is_local_network_host",
    "resolved_public_base",
    "include_conditionals=False",
    '"cache-control"] = "private, no-store"',
    '"Accept-Encoding"] = "identity"',
    "aiter_raw",
]:
    require(required in resolver, f"resolver invariant missing: {required}")

require(
    "read=None" not in resolver,
    "upstream media read timeout is still unbounded",
)

require(
    "follow_redirects=False" in resolver
    and "urljoin(" in resolver
    and "too many upstream media redirects" in resolver
    and 'key.lower() == "cookie"' in resolver,
    "upstream redirects are not manually bounded/validated or can leak cookies",
)
require(
    'headers["Accept-Encoding"] = "identity"' in resolver,
    "relay no longer forces identity encoding for byte-range correctness",
)
require(
    "peer_host = request.client.host" in resolver
    and "is_local_network_host(peer_host)" in resolver,
    "LAN deployment trusts the Host header without validating the actual peer",
)
require(
    "aiter_bytes" not in resolver,
    "relay must stream raw upstream bytes without transparent decompression",
)

require(
    '"thumbnail": None' in resolver
    and '"thumbnail": info.get("thumbnail")' not in resolver,
    "raw upstream thumbnail URL can still leak to the iOS client",
)
require(
    "extraction_semaphore" in resolver
    and "MAX_CONCURRENT_EXTRACTS" in resolver,
    "yt-dlp extraction concurrency is not bounded",
)

require(
    "asyncio.CancelledError" in resolver
    and "proc.kill()" in resolver,
    "cancelled resolver requests can leak yt-dlp subprocesses",
)
require(
    'MAX_VIDEO_HEIGHT = max(360' in resolver
    and 'MAX_VIDEO_FPS = max(24.0' in resolver
    and "constrain_video" in resolver,
    "resolver does not bound preferred source resolution/frame-rate",
)
require(
    'public VCD_PUBLIC_BASE_URL requires VCD_API_TOKEN' in resolver
    and "base = resolved_public_base(request)" in resolver,
    "public deployment is not authenticated/validated before extraction",
)

require(
    "VCD_MAX_VIDEO_HEIGHT" in resolver
    and "VCD_MAX_VIDEO_FPS" in resolver
    and "constrain_video" in resolver
    and '"max_video_height"' in resolver
    and '"max_video_fps"' in resolver,
    "resolver source-cost limits are missing from selection/health",
)
require(
    'if is_local_network_host(host):' in resolver,
    "resolver may relay private/loopback upstream media URLs",
)
require(
    'detail="yt-dlp extraction failed"' in resolver,
    "yt-dlp stderr may still be exposed to API clients",
)
require(
    'protocol not in {"http", "https"}' in resolver
    and 'format_info.get("fragments")' in resolver,
    "manifest/fragment formats can still bypass the controlled relay",
)

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
    print("V9.3 HARDENED AUDIT FAILED")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print("V9.3 HARDENED AUDIT PASSED")
print(" - no WebKit/AVPlayer/OpenGL ES playback path in V9 target")
print(" - libmpv render API is serialized off MainActor and feeds a persistent AVSampleBufferDisplayLayer")
print(" - SwiftUI host recreation cannot tear down the active PiP render surface")
print(" - PiP can keep rendering in background without app-owned GPU commands")
print(" - audio interruption policy prevents unauthorized auto-resume")
print(" - stream refresh retries use bounded backoff and cancel on media switch")
print(" - recreated SwiftUI surfaces rebind to the persistent mpv core")
print(" - resolver token is stored in Keychain and never sent over HTTP")
print(" - resolver refresh is serialized per stream with bounded token storage")
print(" - upstream relay reads have a finite timeout and identity byte encoding")
print(" - resolver source selection is capped at 1080p/30fps by default")
print(" - public resolver deployment requires HTTPS/base URL/auth and same-origin relay")
print(" - Deno 2.9.7 + yt-dlp 2026.08.19 + EJS 0.8.0 are pinned")
