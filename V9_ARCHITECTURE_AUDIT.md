# YoutubeVcd 0.11.2 build 9 — autonomous native client audit

This document describes the code shipped by the current YoutubeVcd branch.

## Product contract

YoutubeVcd now starts directly as an iPhone YouTube client. Normal use does not
require a PC, VPS, local resolver, manual video ID, WebView, or the old Media
Lab.

The primary path is entirely on-device:

- native Home feed from YouTube;
- native Search;
- native Channel video pages;
- continuation/infinite loading;
- real YouTube thumbnails, titles, channel names, view text and duration;
- persistent mini-player containing the real playing video;
- full player sheet using the same playback engine and render surface;
- background audio;
- lock-screen / Control Center Play, Pause and seek;
- native Picture in Picture;
- one persistent libmpv engine.

The optional VcdResolver remains available only as an independent playback
fallback if current YouTube stream extraction changes or fails.

## Browsing

Browsing uses the pinned YouTubeKit revision in `project.yml`.

The pinned library still contains an older February 2026 WEB client version in
its default request templates. YoutubeVcd overrides Home/Search/Channel and all
three continuation request types to the current audited WEB client version
`2.20260708.00.00`, matching the current yt-dlp YouTube client table used for
this audit.

- Home: `HomeScreenResponse`.
- Search: `SearchResponse`.
- Channel: `ChannelInfosResponse` Videos tab.
- Home/Search/Channel continuations are merged on-device.
- If anonymous Home is empty, the app falls back to an on-device YouTube
  discovery search instead of requiring a backend.

Only `YTVideo` objects are mapped into the video feed. SearchResponse itself
skips YouTube `adSlotRenderer` entries. The UI therefore does not render the
normal YouTube web/app advertising surfaces.

## On-device playback resolution

Heavy stream resolution runs in `V9NativePlaybackWorker`, a separate actor,
rather than on MainActor.

Primary resolution:

1. load the real YouTube `/watch` page through `VideoInfosResponse`;
2. extract the current `base.js` player and build the JavaScriptCore
   signature/`n` solver;
3. if the decoded watch-page HLS manifest exists, use it directly for VOD or
   live;
4. otherwise request current `TVHTML5` Innertube streaming data with
   `VideoInfosWithDownloadFormatsResponse`;
5. run the TV HLS/direct formats through the player obtained from the watch
   page before any TV media URL can reach MPV;
6. prefer <=1080p / <=30 fps H.264 MP4 video and AAC/M4A audio when direct
   split formats are needed.

The TV request uses the JSON response decoder matching
`/youtubei/v1/player`. The earlier invalid design — feeding Innertube JSON
into the HTML `.videoInfos` decoder — is forbidden by the audit.

Undeciphered TV media is also forbidden. If the watch page cannot provide a
current player at all, the app rejects the TV media instead of presenting a
possibly broken URL as a successful native resolve; the optional VcdResolver
then remains the independent fallback.

The obsolete iOS Innertube direct-format fallback is not used because current
YouTube GVS policy may require PO tokens for those URLs.

## HLS and media cost

libmpv's default HLS policy is maximum bitrate. YoutubeVcd overrides
`hls-bitrate=8000000`, so HLS does not automatically select a 4K/60 variant
only to downscale it for the phone.

The foreground/PiP software output is further bounded to roughly a 1280x720
pixel budget and at most ~30 rendered frames per second.

When the persistent surface is hosted by the compact mini-player, normal
navigation keeps the render target small to save CPU. If PiP becomes pending or
active, the renderer temporarily enforces at least a 640x360 target before the
same sample-buffer layer is handed to PiP. This avoids a PiP window inheriting
the tiny mini-player buffer size.

## Playback engine

Playback remains MPVKit 1.0.1 non-GPL / libmpv.

- `vo=libmpv`
- `hwdec=videotoolbox-copy`
- `profile=sw-fast`
- `hls-bitrate=8000000`
- `keep-open=yes`

Separate video/audio streams are loaded atomically with MPV EDL. Both EDL
streams receive `!no_clip;!no_chapters`.

The libmpv software render API is isolated in `V9MPVRenderCore` and serialized
off MainActor. Pixel output is delivered through a persistent
`AVSampleBufferDisplayLayer`.

## Mini-player and navigation

`V9PlayerService` owns one persistent `V9MPVRenderView`.

SwiftUI creates disposable host views. The same render surface is reparented
between the full player and the mini-player. The mini-player therefore shows
the actual playing video, not a placeholder icon.

While the full player sheet is open, the mini-player is hidden so two hosts
cannot compete for the same render surface. A host UUID prevents stale
`dismantleUIView` callbacks from pausing a newer host.

Dismissing/swiping down the full player keeps playback alive and returns the
same video surface to the mini-player.

## Background, lock screen and PiP

The app declares `UIBackgroundModes = audio` and uses an AVAudioSession
playback category.

Scene backgrounding does not change user playback intent. If PiP is not active,
hidden video frames are consumed with `MPV_RENDER_PARAM_SKIP_RENDERING` so
video back-pressure cannot stall background audio.

PiP uses:

- `AVSampleBufferDisplayLayer`;
- `AVPictureInPictureController.ContentSource`;
- `AVPictureInPictureSampleBufferPlaybackDelegate`.

Seek/media changes flush the sample-buffer timeline. System interruptions,
route changes and media-services reset are handled explicitly. Automatic
resume only occurs when iOS grants `.shouldResume`.

## Optional resolver fallback

The fallback VcdResolver is not required for Home, Search, Channel, or normal
on-device playback.

When configured, it provides an independent yt-dlp/Range-relay extraction path.
On initial native resolve failure it may be used as fallback. On playback
expiry/failure, the refresh path can use the optional resolver as an
independent extraction route before retrying autonomous native extraction.

Recovery is bounded: a mere `FILE_LOADED` event no longer resets the retry
budget. A stream must remain active for the stable-playback interval before a
later incident receives a fresh retry budget. Rapid open/fail loops therefore
cannot refresh forever.

The resolver retains its transport hardening:

- finite yt-dlp and upstream timeouts;
- bounded extraction concurrency and relay-token count;
- Range relay with `Accept-Encoding: identity`;
- refresh serialization;
- redirect validation;
- private/loopback upstream rejection;
- HTTPS + token requirements for public deployment.

## CI gates

The branch must pass:

1. autonomous-client structural audit;
2. resolver Python syntax audit;
3. Xcode static analysis;
4. clean iOS Simulator compile;
5. unsigned Release iPhone build;
6. built-app version/display-name/background-mode audit;
7. IPA packaging;
8. source packaging;
9. resolver Docker build/start;
10. deterministic fallback Home/Search/Channel/Resolve HTTP smoke.

Structural audit also rejects regressions to:

- WebKit/WKWebView playback;
- AVPlayer as the main playback engine;
- OpenGL ES rendering;
- mandatory resolver configuration;
- Media Lab/manual video-ID UX;
- the obsolete TVHTML5_SIMPLY embedded path;
- the invalid TV JSON -> HTML decoder wiring;
- the stale iOS Innertube direct-format fallback;
- placeholder-only mini-player UI.

## What CI cannot prove

A cloud Xcode build cannot prove real iOS lifecycle behavior. These remain
physical-device gates, not claimed CI facts:

1. signed IPA installation on an iPhone;
2. real Home/Search/Channel responses on the user's network;
3. multiple normal VOD starts;
4. live stream start where YouTube exposes compatible HLS;
5. mini-player navigation for several minutes;
6. screen lock for 2+ minutes without a manual Play command;
7. Control Center Play/Pause/seek;
8. repeated backward/forward seeks;
9. PiP enter/exit while navigating;
10. lock/unlock while PiP/background is active;
11. Siri/phone-call interruption;
12. headphone unplug behavior;
13. 30+ minute CPU, thermal and battery observation.

## Explicit non-goals in this build

These are not falsely presented as complete:

- authenticated Google/YouTube account login;
- synchronized Subscriptions / Watch Later / account History;
- member-only/private videos requiring account credentials;
- SponsorBlock;
- every surface and feature of the official YouTube app.

The current product contract is autonomous Home/Search/Channel + ad-surface-free
native browsing + persistent MPV playback with background/PiP and optional
resolver fallback.
