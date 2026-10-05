# YoutubeVcd 0.10.0 build 6 — as-built native client audit

This document describes the code that ships in the current YoutubeVcd client.
The old manual video-ID Media Lab screen has been removed from the V9 target.

## Product surface

The app now opens directly into a native YouTube-style client with:

- Home feed;
- YouTube search;
- video thumbnails;
- video title, channel and view metadata when yt-dlp exposes it;
- channel video pages;
- persistent mini-player while navigating;
- full player sheet;
- Play/Pause and +/-15 second seeking;
- lock-screen / Control Center commands;
- background audio;
- native Picture in Picture;
- resolver settings hidden in a normal Settings tab instead of the main UI.

There is no WebKit YouTube page and no manual 11-character video-ID field in
normal application use.

## Browsing architecture

VcdResolver 0.4.0-client exposes:

- `GET /v1/home`;
- `GET /v1/search?q=...`;
- `GET /v1/channel/{channel_id}`;
- `GET /v1/thumb/{video_id}`;
- `GET /v1/video/{video_id}`;
- `GET|HEAD /v1/relay/{token}`.

Home first uses yt-dlp's YouTube recommended extractor (`:ytrec`) and falls
back to a normal YouTube search if recommendations are unavailable.

Search uses yt-dlp's `ytsearch` extractor. Channel pages use the YouTube
channel videos tab with flat-playlist extraction.

Browse results are normalized to a small client model and thumbnails are
served through the resolver's own `/v1/thumb/` path. The iOS client validates
that thumbnail URLs remain on the resolver's same origin, including deployments
that use a reverse-proxy base path.

The current media relay supports directly addressable HTTP/HTTPS media only.
Live/upcoming entries are therefore filtered out of Home/Search/Channel instead
of displaying cards that cannot be played.

## Playback architecture

Playback remains one persistent libmpv engine through MPVKit 1.0.1 non-GPL.

- video/audio direct streams are hidden behind resolver relay URLs;
- separate video + audio are loaded atomically with MPV EDL;
- both EDL streams use `!no_clip;!no_chapters`;
- H.264/AAC-compatible sources are preferred;
- source selection is capped by default at 1080p / 30 fps;
- VideoToolbox copy hardware decoding is enabled;
- libmpv software rendering uses `MPV_RENDER_API_TYPE_SW`;
- render work runs on a dedicated serial queue, not MainActor;
- foreground and PiP share one persistent `AVSampleBufferDisplayLayer`.

The SwiftUI host view is disposable, but the actual render surface stays owned
by `V9PlayerService`. A host token prevents stale SwiftUI teardown callbacks
from pausing a newly attached host.

## Navigation while playing

When a video is loaded, YoutubeVcd presents a compact mini-player above the tab
bar. The user can continue browsing Home, Search and channels without replacing
the MPV engine.

Opening the mini-player reattaches the same persistent render surface to the
full player sheet. Dismissing the sheet does not destroy playback.

If resolving a newly selected video fails, the existing playback is left alone
and the client shows an error instead of putting the current player into failed
state.

## Background, lock screen and PiP

The audio session uses the playback category and the app declares
`UIBackgroundModes = audio`.

Scene transitions do not change user playback intent. When foreground video is
not visible and PiP is not active, libmpv video updates are consumed with
`MPV_RENDER_PARAM_SKIP_RENDERING` so hidden video cannot back-pressure audio.

PiP uses:

- `AVSampleBufferDisplayLayer`;
- `AVPictureInPictureController.ContentSource`;
- `AVPictureInPictureSampleBufferPlaybackDelegate`.

Timeline state is reset at media changes and seeks. Remote Play/Pause/seek
commands map back to the same MPV service.

Audio interruptions, output-route changes and media-services reset are handled
explicitly. System interruptions only resume automatically when iOS grants
`.shouldResume`.

## Resolver reliability and security

The resolver:

- validates video, channel and search inputs;
- bounds concurrent yt-dlp processes;
- terminates yt-dlp subprocesses on cancellation/timeout;
- bounds active relay entries;
- uses high-entropy relay capability tokens;
- uses finite connect/read timeouts;
- forwards byte Range;
- forces `Accept-Encoding: identity`;
- streams raw upstream bytes;
- serializes refresh per relay entry;
- refreshes expired upstream URLs on 403/404/410;
- validates every upstream redirect;
- rejects loopback/private upstream media destinations;
- strips cookies after an upstream redirect changes host;
- requires HTTPS + explicit public base URL + API token for public deployment;
- checks both Host and TCP peer for LAN-only mode;
- keeps raw upstream media URLs out of iOS.

The client:

- rejects localhost on a physical iPhone;
- allows plain HTTP only for local/private resolver hosts;
- never sends a bearer token over HTTP;
- refuses resolver API redirects;
- validates media relay and browse-thumbnail same-origin paths;
- stores the resolver bearer token in Keychain.

## CI gates

Each PR build now runs:

1. native client structural audit;
2. Python syntax validation;
3. Xcode static analysis;
4. clean iOS Simulator build;
5. unsigned Release iPhone build;
6. built-app metadata audit;
7. unsigned IPA packaging;
8. clean source packaging;
9. real resolver Docker build/start;
10. resolver runtime/version audit;
11. deterministic HTTP smoke for Home;
12. deterministic HTTP smoke for Search;
13. deterministic HTTP smoke for Channel;
14. deterministic HTTP smoke for video Resolve;
15. checks that unsupported live entries never enter the playable feed.

The deterministic client API tests use a fake yt-dlp fixture so CI verifies the
complete HTTP contract without relying on YouTube allowing a GitHub runner IP.

## External boundaries

These are not silently presented as working features:

- authenticated YouTube account login;
- subscriptions/watch-later synchronized with a Google account;
- members-only/private content without valid cookies/PO-token deployment;
- live/HLS playback;
- SponsorBlock;
- a clone of every official YouTube surface.

Those require additional product/API work. They are not required for the
current Home/Search/Channel + persistent-player client to operate.

## Physical-device gates

CI cannot simulate real iOS lock-screen and PiP lifecycle. The remaining device
validation is therefore behavioral, not missing implementation:

1. install signed IPA on a real iPhone;
2. load Home and Search from the real resolver;
3. play several normal videos;
4. browse to another tab while playback continues in the mini-player;
5. lock for 2+ minutes;
6. use Control Center Play/Pause/seek;
7. repeat forward/backward seeks;
8. enter/exit PiP repeatedly;
9. use PiP while navigating Home/Search/Channel;
10. test Siri/phone audio interruption;
11. unplug headphones and confirm safety pause;
12. run 30+ minutes and observe CPU, battery and thermal behavior.
