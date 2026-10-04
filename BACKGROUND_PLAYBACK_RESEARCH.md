# Background Playback Research — WebKit V4

## Baseline

This branch starts from commit `336d046c0f7fbd19feb0b4ff8f410aaca3d58bb7`,
the 0.4.0 build-5 WebKit family that remained the most usable device baseline.

The 0.4.3 AVPlayer handoff experiment is intentionally not used here.
This branch does not activate YouTubeKit, Piped, Invidious, StreamResolver,
DASH reconstruction, or a second native media engine.

## Device regressions this branch must solve

1. Audio must continue after Home / screen lock without requiring PiP first.
2. Entering PiP must not pause audio/video.
3. Returning from background must not leave WebKit audio/video frozen.
4. Lock Screen / Control Center Play and Pause must remain usable.
5. An intentional Pause must never be undone by background recovery.

## Research evidence

### Brave iOS

Brave implemented a WebKit-only background playback/PiP compatibility layer:
- Issue: https://github.com/brave/brave-ios/issues/4031
- Merged implementation: https://github.com/brave/brave-ios/pull/4032

The implementation established two important behaviors:
- keep the website-facing visibility state effectively visible so sites such as
  YouTube do not voluntarily pause media when the app backgrounds;
- stop propagation of `webkitpresentationmodechanged` so a site cannot use
  the system PiP transition as a reason to pause playback.

Brave later attempted to simplify background recovery:
- https://github.com/brave/brave-ios/pull/5628
- https://github.com/brave/brave-ios/issues/5627

That simplification introduced a regression where an intentionally paused
YouTube video resumed when the user switched away:
- https://github.com/brave/brave-ios/issues/5775
- revert: https://github.com/brave/brave-ios/pull/5805

V4 therefore never treats "page became hidden" alone as permission to Play.
Recovery requires an existing playback intent, and explicit Pause clears it.

Brave also fixed WebKit-version compatibility by preserving native property
descriptor configurability:
- https://github.com/brave/brave-ios/pull/4872

### Fyoutube / Orion

Current project:
https://github.com/aditauqir/fyp

Relevant source:
https://github.com/aditauqir/fyp/blob/188d54cf36b2e6d315d14ec898ebfe6123cd03c8/youtube-mobile-background.user.js

Relevant architecture notes:
https://github.com/aditauqir/fyp/blob/188d54cf36b2e6d315d14ec898ebfe6123cd03c8/ARCHITECTURE.md

Independent lessons matching Brave:
- retain native visibility descriptors before spoofing page-facing visibility;
- track one active watch video, not the first arbitrary `<video>`;
- maintain an explicit `wantsPlayback` state;
- explicit Pause wins over recovery;
- set `navigator.audioSession.type = "playback"` when supported;
- install Media Session play/pause/seek handlers for system controls;
- recover a background-induced pause with a small bounded retry sequence;
- re-attach/re-assert state when WebKit changes presentation mode or replaces
  the media element.

### Unwatched iOS

Current native iOS project:
https://github.com/fer0n/Unwatched

Relevant WebKit configuration:
https://github.com/fer0n/Unwatched/blob/e21de2ecbb4520d9035ae0b378fa864f442dcff9/Unwatched/Unwatched/View/Player/PlayerWebView/PlayerWebView.swift

Relevant scripts:
https://github.com/fer0n/Unwatched/blob/e21de2ecbb4520d9035ae0b378fa864f442dcff9/Unwatched/Unwatched/View/Player/PlayerWebView/PlayerWebView%2BScripts.swift

Unwatched independently confirms two V4 decisions:
- inject before YouTube's scripts and neutralize Page Visibility/lifecycle handlers;
- stop propagation of `webkitpresentationmodechanged`.

Its current code also documents a newer iOS failure mode: after returning from
background YouTube may rebuild its MediaSource and leave the video element at
`readyState == 0` (black/unresponsive). V4 records `readyState`,
`networkState`, and DOM attachment in its bridge telemetry so a physical-device
failure can distinguish this WebKit/MediaSource condition from an ordinary pause.
V4 deliberately does not auto-reload the page merely because a transition is
slow; a destructive reload should only be added if the physical device proves
the `readyState == 0` condition persists.

### Current Brave regression (2026)

Open Brave issue:
https://github.com/brave/brave-browser/issues/52281

The reported symptom on modern iOS is unusually close to this app: a YouTube
video stops after backgrounding even though background audio is enabled, but
playback can return through system media controls. Reports also note that
desktop-site or fresh/incognito sessions can behave differently from a normal
signed-in YouTube session.

This matters for architecture: if V4's early lifecycle neutralization still
fails on a physical device, the next research branch should test a desktop
YouTube WebKit backend (as Fyoutube does), not return to AVPlayer stream
resolution. That experiment is intentionally kept separate because changing
the YouTube presentation mode also changes UI/layout behavior.

## V4 invariants

- WebKit is the only media engine.
- The actual YouTube watch video remains the audio/video source.
- Native `AVAudioSession(.playback)` and `UIBackgroundModes=audio` remain.
- Native MPRemoteCommandCenter support remains because it worked in the
  known-good baseline.
- JS Media Session support supplements, rather than replaces, the native route.
- No `setAllMediaPlaybackSuspended(true)`.
- No direct stream extraction or external stream proxy.
- No unconditional resume-on-hide.
- No first-`video` selector for transport commands.
- PiP transition events are prevented from propagating to YouTube, while the
  WebKit system transition itself is left untouched.

## Playback state model

The bridge keeps two separate visibility concepts:

- **website visibility**: reported as visible so YouTube does not intentionally
  stop playback;
- **real WebKit visibility**: read through descriptors captured before the
  spoof and used only by the bridge.

The bridge keeps explicit playback intent:

- Play -> `wantsPlayback = true`
- explicit Pause -> `wantsPlayback = false`
- WebKit/background Pause while hidden + wantsPlayback -> bounded recovery
- foreground Pause -> intentional stop
- background transition by itself -> never invents playback intent

## Required device test matrix before declaring success

1. Normal video -> Home, no PiP: audio continues.
2. Normal video -> lock screen, no PiP: audio continues.
3. Lock screen Pause: remains paused for at least 15 seconds.
4. Lock screen Play: resumes.
5. Background -> foreground while playing: video/audio continue, no freeze.
6. Background -> Pause on lock screen -> foreground: remains paused.
7. PiP while already playing: PiP opens without a pause.
8. Exit PiP: playback continues.
9. Repeat Home/foreground 10 times on one video.
10. Navigate to another video and repeat to confirm active-video rebinding.
11. Test an ad transition to ensure recovery does not attach to a preview/ad
    element permanently.
12. Test interruption (phone/other audio) and resume behavior.

Only an actual iPhone run can prove WebKit background behavior; simulator/static
checks cannot certify it.


## Full re-audit findings before build 10

The first 0.4.4 build-9 candidate passed compilation but failed a deeper
behavioral audit. It must not be treated as the final V4 candidate.

The second audit found and corrected all of the following before build 10:

- removed dormant AVPlayer / YouTubeKit / native-navigation source files instead
  of merely excluding them from the target;
- restored the 0.4.0 PiP and fullscreen on-page controls lost in the first V4 rewrite;
- fused Swift real scene background state with WebKit native visibility everywhere
  recovery makes a decision;
- preserved playback intent when YouTube replaces the active video element;
- restored last-known playback position after a same-video MediaSource rebuild;
- distinguished same-element SPA route changes so an old position cannot leak
  into the next video;
- stopped classifying the Shorts renderer as an inline preview;
- returned explicit Lock Screen / Control Center transport ownership to
  MPRemoteCommandCenter / MPNowPlayingInfoCenter instead of a second custom
  navigator.mediaSession action-handler layer;
- preserved native playback context while a rebuilt page temporarily has no video;
- made native scene state authoritative for Now Playing while JS is suspended;
- isolated AVAudioSession interruptions so recovery does not fight phone/Siri pauses;
- fixed PiP exit so the standards fallback cannot immediately re-enter PiP;
- retained the prefixed WebKit fullscreen fallback;
- consumed readyState/networkState/DOM/video-id telemetry in Swift;
- added a bounded foreground-only repair for persistent readyState == 0:
  two-second confirmation, 15-second cooldown, controlled reload, then position
  and Play restoration;
- added WKWebView.requestMediaPlaybackState probes so native suspended state can
  independently trigger the same bounded recovery;
- deferred WebContent-process termination recovery while backgrounded and performs
  it on the next foreground transition with position/play restoration;
- injected the playback lifecycle shield before the ad-block script;
- replaced the grep-only CI gate with structural source auditing plus JavaScript
  syntax checks.

The source candidate is now 0.4.4 build 10. No build-10 IPA should be accepted
unless structural audit, Swift static analysis, simulator compile, unsigned
device build, and metadata audit all pass.

### Remaining physical-device release gates

Static analysis cannot prove iOS scheduling behavior. The physical iPhone test
must still verify:

1. Home without PiP keeps audio playing.
2. Lock screen without PiP keeps audio playing.
3. Lock-screen Pause stays paused and Play resumes.
4. PiP enter/exit does not introduce a pause.
5. Foreground return does not freeze audio/video or reset position.
6. Repeat across multiple videos and a Short.
7. A phone/Siri/audio interruption pauses correctly and only resumes when the
   system says it should.
8. Repeated transitions do not trigger repair reload unless media is actually stuck.

A separate iOS 26 class of whole-WebContent-process suspension after long
background periods has been reported publicly. If a physical device shows that
stronger failure mode (no JS/native media-state response at all), the next
recovery layer should recreate the WKWebView rather than add more play timers.
