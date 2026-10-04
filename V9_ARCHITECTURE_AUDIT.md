# V9 Architecture Audit — Native Custom Client

Date: 2026-10-04

## Decision

V9 must not continue the WKWebView-wrapper architecture and must not repeat the previous direct AVPlayer architecture.

Chosen direction:

1. Native SwiftUI application shell.
2. Separate, updateable media/content resolver backend.
3. One persistent libmpv/MPVKit playback engine.
4. Native Picture-in-Picture using AVSampleBufferDisplayLayer + AVPictureInPictureController.
5. Native background audio, lock-screen controls, interruptions, queue and navigation.
6. No YouTube mobile/desktop page is used as the application UI.
7. No public Piped/Invidious instance is a required dependency.
8. No direct AVPlayerItem(url:) handoff from captured YouTube URLs.
9. No AVMutableComposition of independent YouTube DASH URLs.
10. No duplicate playback ownership between JavaScript and native code.

## Why the old AVPlayer attempts failed

### Direct YouTubeKit / local resolution

The old native player preferred progressive muxed formats and otherwise attempted to compose separate DASH video/audio URLs in AVMutableComposition.

Failure modes:
- progressive muxed streams were not consistently available;
- separate YouTube video/audio URLs were transient and session-sensitive;
- DASH composition introduced two independent remote assets and track readiness failure modes;
- codec/container support constrained the usable formats;
- resolver breakage and player failure were coupled in the same binary.

Conclusion: AVPlayer itself was not the only failure. The input contract was not reliable enough.

### Public Piped / Invidious resolver

The old StreamResolver raced multiple public instances and chose returned stream URLs.

Failure modes:
- public instances were unreliable or unavailable;
- API behavior varied by instance;
- returned media URLs could be tied to an instance/IP/egress path;
- direct client playback could use a different egress path from extraction;
- fixing extraction required shipping a new client version or changing instance lists.

Conclusion: public third-party instances cannot be a core reliability dependency.

### 0.4.3 native background handoff

The foreground WebKit player captured a media URL and handed it to AVPlayer only for background.

Failure modes:
- captured URLs did not carry the complete YouTube playback context;
- switching between two independent playback clocks caused resume/seek races;
- foreground and background each owned playback state;
- PiP/background/lock-screen behavior regressed;
- stale or invalid direct URLs failed after the handoff.

Conclusion: never switch engines merely because app lifecycle changes.

## What V4–V8 proved

The WebKit line proved several useful facts:
- iOS can keep the app's audio session alive;
- native MPRemoteCommandCenter/MPNowPlayingInfoCenter ownership is preferable to page Media Session ownership;
- explicit Pause must be a native user-intent state;
- PiP must have a persistent media source independent of browsing UI;
- lifecycle transitions must not be interpreted as user Pause.

It also proved that a YouTube page is the wrong permanent playback engine for the requested product:
- WebKit can pause/suspend media on system transitions;
- PiP remains coupled to the page/video element;
- browsing and playback require increasingly complex DOM/lifecycle interception;
- mobile YouTube continuously tries to restore its own product behavior.

## Better architecture discovered

### Resolver tier

Recommended base: a private/self-hosted service modeled after Yattee Server.

Responsibilities:
- search, home/trending, channels, playlists and metadata;
- InnerTube extraction where practical;
- yt-dlp fallback and decipher/challenge maintenance;
- PO-token provider support when required;
- optional credential/cookie management;
- normalize streams into a stable client-facing model;
- re-extract when upstream URLs expire;
- signed byte-relay for direct playback;
- HTTP Range support;
- rewrite HLS/DASH manifests through the relay;
- keep extraction egress and media relay egress consistent.

The iOS app must never depend on raw upstream googlevideo URLs remaining valid for long periods.

### Player tier

Recommended playback engine: libmpv via the non-GPL MPVKit build unless a GPL-only feature is actually required.

Why MPV:
- accepts separate video and audio URLs directly;
- handles HLS, DASH, MP4, WebM, H.264, HEVC, VP9, AV1, AAC, Opus and MP3;
- no AVMutableComposition is needed;
- supports a persistent player instance;
- rendering can be paused while audio/decode state remains intact;
- stream refresh can reload the same video at the previous time;
- quality/audio track changes do not require a second playback engine.

### PiP tier

Do not hand off to AVPlayer.

Architecture:
- MPV continues to be the only playback clock;
- decoded MPV frames are copied/presented as CVPixelBuffer/CMSampleBuffer;
- AVSampleBufferDisplayLayer is attached to AVPictureInPictureController.ContentSource;
- PiP playback delegate maps Play/Pause/Seek to the same MPV instance;
- sample-buffer timebase follows MPV time;
- pre-buffer a short set of future frames before the iOS background transition to bridge the system suspension window;
- the sample-buffer layer remains alive even when the main player UI is collapsed.

This keeps foreground, background, lock screen and PiP on one engine.

### Background tier

When the app enters background without PiP:
- do not pause MPV;
- do not disable the video track;
- pause only the render/display loop;
- keep demux/decode/audio clock alive;
- resume rendering when foreground becomes active.

Disabling the video track is intentionally avoided because it can create A/V desynchronization on re-enable.

### Native user intent

One state machine owns transport:
- desiredPlayback = playing / paused;
- explicit Pause always wins;
- phone/Siri interruptions pause and resume only when iOS returns shouldResume;
- MPRemoteCommandCenter is the only lock-screen transport owner;
- app navigation never owns playback lifecycle;
- Home/Search/Channel screens cannot stop or recreate the player.

## Client module layout

V9 should be split into:

- AppShell
  - Native TabView / NavigationStack
  - Home
  - Search
  - Channel
  - Library
  - Settings

- Content
  - ResolverAPI
  - Video/Channel/Playlist models
  - pagination and cache

- Playback
  - PlayerBackend protocol
  - MPVBackend
  - MPVRenderView
  - MPVPiPBridge
  - PlaybackState
  - NowPlayingService
  - AudioSessionCoordinator
  - Queue

- Resolver contract
  - video metadata
  - format list
  - video-only/audio-only relationship
  - muxed streams
  - HLS/DASH
  - headers if needed
  - expiry metadata
  - refresh token/video ID
  - relay URL

No YouTube WebView belongs in the normal V9 UI path.

## Stream refresh contract

Playback URLs are assumed to expire.

When MPV receives an HTTP expiry/failure:
1. capture video ID, time, play/pause state, quality and audio-language preference;
2. request fresh streams from resolver;
3. select equivalent stream pair;
4. load replacement without autoplay;
5. seek to captured position;
6. restore rate/volume/mute;
7. resume only if desiredPlayback == playing.

Limit retries and expose a real error rather than infinite loops.

## Ad-free behavior

The app does not embed the YouTube web player. The resolver returns media streams and the native player renders those streams, so the embedded-player ad UI is not part of the client playback path.

This architecture must not use the official YouTube API/embedded-player contract for playback because that contract explicitly forbids blocking YouTube ads and background playback.

## Why not the alternatives

### Official YouTube IFrame/Data API
Reject for target product:
- background playback prohibited by YouTube API policies;
- ad blocking prohibited;
- player modification prohibited.

### WKWebView player
Reject as primary engine:
- already demonstrated lifecycle suspension/pause behavior;
- PiP remains page-element dependent;
- requires DOM/visibility/media-session interception.

### Direct AVPlayer
Reject as primary engine:
- prior DASH/progressive failures;
- format limitations;
- requires muxing/composition or HLS for many high-quality combinations.

AVPlayer may be retained only for future optional compatibility experiments, never as the architectural foundation.

### Public Piped/Invidious
Reject as required backend:
- availability and stream egress are outside our control.

May be optional user-configurable sources only.

### On-device yt-dlp/Python
Reject for V9:
- heavy and difficult to maintain on iOS;
- challenge runtime/update cycle is better handled off-device;
- increases app size and signing/runtime complexity.

## Deployment model

Recommended:
- private Docker resolver on a VPS/home server reachable via HTTPS;
- resolver can be updated independently from the IPA;
- iOS client stores only endpoint + authentication token;
- resolver health/version endpoint lets the client show a useful error when extraction needs an update.

For reliability outside the home network, a small remote VPS is preferable to a LAN-only host.

## License note

Prefer the LGPL MPVKit variant. Do not enable the GPL MPVKit build unless the project is intentionally distributed under compatible GPL terms.

## V9 implementation gates

Do not build the full UI on an unproven media foundation.

Gate 1 — resolver:
- search returns results;
- video endpoint returns metadata + stream list;
- separate audio/video streams are valid;
- relay supports Range;
- expired stream can be refreshed.

Gate 2 — MPV playback:
- 10 normal videos;
- at least one 1080p separate audio/video pair;
- VP9/AV1 fallback where device supports it;
- seek forward/back repeatedly;
- quality switch at same timestamp;
- 30+ minute playback without clock drift.

Gate 3 — background:
- screen lock for 2+ minutes without user command;
- Home/app switching;
- return to foreground without manual Play;
- Pause on lock screen remains paused;
- Play/Pause/seek work repeatedly from Control Center.

Gate 4 — PiP:
- enter/exit repeatedly;
- navigate entire app while PiP stays alive;
- lock/unlock while PiP is active;
- PiP Play/Pause/seek map to the same MPV instance;
- player UI can be destroyed/recreated without destroying MPV/PiP service.

Only after these gates pass should Home/Search/Channel UI be considered release work.

## Immediate next step

Do not port old AVPlayer code.

Create a minimal V9 media laboratory:
- one native screen;
- resolver endpoint configuration;
- one hard-coded video ID/search result;
- MPV playback;
- separate audio/video load;
- native remote controls;
- native MPV PiP bridge;
- background render pause only.

If this laboratory passes the four gates above, build the full custom UI around it.
