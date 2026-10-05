# YoutubeVcd V9.2 — as-built architecture audit

This document describes the code that actually ships in the V9.2 Media Lab.
It deliberately separates implemented behavior from future full-client work.

## Release identity

- App: YoutubeVcd V9
- Version: 0.9.2
- Build: 4
- iOS deployment target: 17.0
- Playback engine: libmpv through MPVKit 1.0.1 non-GPL product
- Resolver: VcdResolver 0.3.0-lab
- Resolver extraction stack: yt-dlp 2026.08.19 + yt-dlp-ejs 0.8.0 + Deno 2.9.7

## What V9.2 is

V9.2 is a native media-foundation laboratory. It proves the playback,
background, remote-control, resolver and PiP architecture before a complete
YouTube-style browsing UI is built.

The current UI contains:

- resolver endpoint configuration;
- optional resolver bearer token;
- manual 11-character YouTube video ID;
- resolver health check;
- Resolve + Play;
- Play/Pause;
- +/-15 second seek;
- PiP control;
- playback diagnostics.

It does **not** yet contain native Home, Search, Channel, Playlist or Library
screens. Those are later client work and must not be described as implemented.

## Playback architecture

V9.2 contains no WKWebView or YouTube web player in the V9 target and no
AVPlayer playback engine.

One persistent `mpv_handle` owns playback. Separate YouTube video/audio URLs
are hidden behind resolver capability URLs and loaded atomically through MPV
EDL when separate streams are available.

Relevant modules:

- `V9PlayerService` — persistent mpv core, playback intent, audio session,
  lock-screen controls, stream recovery and lifecycle.
- `V9MPVRenderView` — libmpv software rendering into pooled CVPixelBuffers.
- `V9MPVPiPBridge` — native PiP using the same AVSampleBufferDisplayLayer.
- `VcdResolverClient` — resolver health/resolve client and transport checks.
- `ResolverTokenStore` — bearer token storage in iOS Keychain.

## Renderer: software by design

OpenGL ES was removed from V9.2.

libmpv uses `MPV_RENDER_API_TYPE_SW` with:

- `MPV_RENDER_PARAM_SW_SIZE`;
- `MPV_RENDER_PARAM_SW_FORMAT`;
- `MPV_RENDER_PARAM_SW_STRIDE`;
- `MPV_RENDER_PARAM_SW_POINTER`.

The guaranteed `bgr0` output is rendered into pooled BGRA CVPixelBuffers. The
fourth byte is forced opaque before the buffer is wrapped in a CMSampleBuffer.

The visible player and PiP use one AVSampleBufferDisplayLayer. There is no
second playback engine and no foreground/background engine handoff.

Rendering is bounded to roughly a 1280x720 pixel budget and at most 30 visual
frames per second. This is a correctness-first path; physical-device CPU,
thermal and battery performance still require measurement.

## Background behavior

The audio session uses the playback category and `UIBackgroundModes = audio`.

When the app goes to background without PiP:

- MPV is not paused merely because of scene lifecycle;
- visible frame production is stopped;
- libmpv render updates are still consumed with
  `MPV_RENDER_PARAM_SKIP_RENDERING` so hidden video does not back-pressure
  and stall audio;
- the audio clock and transport remain owned by the same MPV instance.

For automatic PiP transitions, V9.2 keeps software frames flowing briefly
while iOS transitions the app to background. If PiP does not become active,
visual rendering is stopped after the bounded grace window.

No app-owned OpenGL/GPU commands are issued in background.

## Audio interruptions and route changes

The player observes:

- AVAudioSession interruption notifications;
- route-change notifications;
- media-services reset.

Explicit user Pause clears desired playback intent.

A phone/Siri/system interruption preserves intent while interrupted, but
automatic resume occurs only when iOS supplies `.shouldResume`. If iOS does
not grant resume, desired playback is cleared so a later foreground scene
transition cannot restart playback behind the user's back.

Disconnecting the old audio output route (for example unplugging headphones)
is treated as an explicit safety pause.

## Lock-screen / Control Center

MPRemoteCommandCenter owns:

- Play;
- Pause;
- Toggle Play/Pause;
- Skip +15;
- Skip -15;
- absolute playback-position seek.

MPNowPlayingInfoCenter publishes title, current position, duration and
playback rate.

The remote commands map back to the same MPV instance.

## Native PiP

PiP uses:

- AVSampleBufferDisplayLayer;
- AVPictureInPictureController.ContentSource;
- AVPictureInPictureSampleBufferPlaybackDelegate.

The same sample-buffer layer used for foreground presentation is the PiP
source. The PiP delegate maps Play/Pause/Seek to V9PlayerService.

The presentation timeline is reset:

- when a new media item is loaded;
- before every seek, including backward seeks;
- after display-layer failure.

This prevents an old monotonic PTS from forcing a newly sought frame into the
future.

PiP is only enabled in the UI after iOS reports it possible.

## SwiftUI lifetime

The mpv core lives in `@StateObject V9PlayerService`, not in the UIView.

If SwiftUI recreates the V9MPVRenderView, the new view is explicitly rebound
to the already-existing persistent mpv/render context and the PiP bridge is
reconfigured around the new sample-buffer layer.

This is compile-verified, but repeated destroy/recreate behavior still needs a
physical-device gate.

## Stream recovery

Relay URLs are expected to expire or fail.

Two recovery layers exist:

1. Resolver relay refresh:
   - a 403/404/410 from upstream triggers yt-dlp re-extraction;
   - refresh is serialized per relay entry to avoid a refresh stampede;
   - the same format ID is preferred when still available;
   - the client-facing relay capability URL remains stable.

2. Client recovery:
   - on terminal MPV stream failure, capture video ID and current time;
   - request a newly resolved stream pair;
   - retry with bounded backoff;
   - reload paused;
   - seek to the captured time;
   - resume only when desired playback is still true.

A successful `MPV_EVENT_FILE_LOADED` resets the future retry budget.

V9.2 currently preserves video ID, time and play/pause intent. A future
full-client quality/audio-language/rate preference layer is not implemented.

## Resolver security and reliability

VcdResolver 0.3.0-lab:

- validates the 11-character video ID;
- bounds concurrent yt-dlp processes;
- bounds active relay entries;
- gives each relay a high-entropy capability token;
- supports sliding relay leases;
- supports GET and HEAD;
- forwards byte Range;
- uses finite connect/read timeouts;
- returns raw bytes without transparent HTTP decompression;
- serializes per-stream refresh;
- never returns raw video/audio upstream URLs;
- does not return the raw upstream thumbnail URL;
- marks relay responses `private, no-store`;
- sanitizes yt-dlp failures returned to API clients;
- supports optional cookies;
- supports optional resolve authentication;
- requires an explicit trusted `VCD_PUBLIC_BASE_URL` for non-LAN deployment.

The iOS client additionally:

- rejects localhost/127.0.0.1/::1 on a physical iPhone;
- permits plaintext HTTP only to a local/private host;
- never sends a resolver bearer token over HTTP;
- validates every returned relay URL before handing it to MPV;
- rejects HTTPS-to-HTTP relay downgrade.

The bearer token is stored in Keychain, not UserDefaults.

## Direct-stream boundary

V9.2 intentionally relays only directly addressable HTTP/HTTPS media formats.

HLS/m3u8 and fragment-list formats are rejected because a correct HLS/DASH
proxy must rewrite every nested segment/key/map URL. Passing a manifest through
unchanged would leak upstream URLs and make expiry/header refresh unreliable.

Therefore some live streams are **not supported in V9.2**. This is a known
boundary, not a claimed working feature.

## Content requiring authentication

A Netscape-format cookie file can be mounted into the resolver through
`VCD_COOKIES_FILE`.

Cookies do not guarantee every age-restricted, members-only or anti-bot case.
Some current YouTube paths may additionally require PO Token provider support.
That remains a resolver deployment concern, not something the IPA can
guarantee.

## Ad-free playback boundary

The V9 target never embeds the YouTube web player. For successfully resolved
direct media, playback therefore does not include the embedded YouTube player
ad UI.

V9.2 does not implement SponsorBlock or automatic removal of creator-inserted
sponsor segments.

## CI gates

Every V9.2 PR build runs:

1. structural architecture audit;
2. Python syntax validation;
3. Xcode static analysis;
4. iOS Simulator clean build;
5. unsigned Release device build;
6. built-app metadata audit;
7. unsigned IPA packaging;
8. clean V9 source packaging;
9. real Docker resolver build/start;
10. resolver health/runtime/format-safety smoke checks.

CI verifies compilation and structural invariants. It does not simulate the
iOS lock screen, real Control Center, thermal behavior or physical PiP
transitions.

## Physical-device release gates still required

Before calling the media foundation device-proven, test on a real iPhone:

1. at least 10 normal videos;
2. separate 1080p H.264/AAC playback;
3. repeated forward/backward seeks;
4. 30+ minute playback;
5. lock screen for 2+ minutes;
6. background app switching and foreground return;
7. repeated Control Center Play/Pause/seek;
8. audio interruption by phone/Siri and recovery;
9. headphones disconnect safety pause;
10. repeated PiP enter/exit;
11. PiP + lock/unlock;
12. repeated player-view destroy/recreate while the MPV service survives;
13. CPU, thermal and battery observation during software-render PiP.

## Not release-complete yet

The following are intentionally outside the V9.2 Media Lab and must not be
reported as finished:

- Home feed;
- native Search;
- Channel pages;
- playlists;
- Library/history/subscriptions;
- account login;
- quality selector;
- audio-language selector;
- HLS/live relay;
- SponsorBlock;
- polished YouTube-style navigation/UI.

The correct next milestone after the physical media gates is a native content
and navigation shell around this persistent player, not another playback
engine rewrite.
