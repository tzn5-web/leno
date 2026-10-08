# Standalone YouTube Vanced

The earlier `VancedCore` IPA did not implement the requested YouTube ad blocking,
background playback or PiP. This entry point builds those modules and packages
the user's local decrypted YouTube 20.21.6 as a separate application.

## Identity

- OS bundle identifier: `ro.ion.youtubevanced` (a signer may append its team suffix).
- Display name: `YouTube Vanced`.
- URL schemes: `youtubevanced` and `ro.ion.youtubevanced`, separate from the original app.
- Keychain: the standalone app's own signing group, discovered through Security APIs.
- Original Google app-group requests: separate private folders in this app's sandbox.
- Only Google's in-process client metadata uses the registered original client ID.
  No global NSBundle identity override is installed.
- The five original Google app extensions are excluded. This build does not promise
  widgets, share extensions, Siri extensions or Google push notification delivery.

## Playback modules

`YouTubeX` implements video/feed ad filtering and background availability hooks.
`YouPiP` enables YouTube's native PiP; `YTVideoOverlay` is built and explicitly
linked as its dependency. Source revisions are pinned in `dependencies.json`.
The Logos internal Objective-C backend avoids external Substrate and jailbreak
path dependencies. The iOS 11-14 legacy PiP compatibility code is excluded;
the minimum supported iOS version for this package is 15.
The dynamically resolved protobuf `hasPictureInPicture` accessor is explicitly
added, because the internal backend cannot hook a method missing from the original
method table. This is checked against the fixed YouTube 20.21.6 input.

The existing YouTube player handles audio, PiP and pause/resume. No timer or
application lifecycle callback is added to force playback to resume.
This avoids introducing automatic replay after the user pauses, but actual
pause retention still requires a device test.

## Guest profile

The user reported that the previous standalone IPA installs and opens, but its
Google sign-in returns HTTP 404 and Continue as Guest stalls. `VancedGuest`
uses the native first-time guest transaction instead of presenting OAuth UI.
Its ABI and transaction behavior were checked against YouTube 20.21.6: a nil
future identity becomes a native unauthenticated guest, and the native success
block commits the transaction and finishes its coalescer. It does not fake
`isSignedIn` or report a successful Google login.

The Guest Library is accessible from settings and a clock/history overlay button.
It stores watch history with progress, favorites, Watch Later and named playlists
in this application's private Application Support folder, using atomic JSON writes.
History is capped at 1,000 videos. Each saved collection is capped at 1,000 videos,
with up to 100 playlists. Pause and clear controls are available. Incognito,
signed-in playback and the native watch-history pause setting suppress recording.
Deleting history does not delete favorites or playlists. Native signed-out search
history remains managed by YouTube. Local lists do not act as Google likes or
subscriptions, and they do not synchronize to a Google account. Uninstalling the
app deletes the local profile. Corrupt libraries are preserved instead of overwritten.

The user-confirmed sign-in failure remains unresolved for optional Google login;
guest access and persistence still require testing on the user's iPhone.

## Build and package

On a Mac with Xcode:

```sh
python3 VancedIOS/Standalone/build.py
python3 -m unittest discover -s VancedIOS/Standalone/Tests -p 'test_*.py'
python3 VancedIOS/Standalone/package.py /path/to/youtube-v20.21.6.ipa \
  VancedIOS/Standalone/artifacts /path/to/YouTube_Vanced_UNSIGNED.ipa
```

The GitHub workflow builds only the open-source modules, resources and evidence.
The proprietary YouTube IPA and personal signing credentials stay local.
Packaging starts from the original hash listed in the manifest, rejects encrypted
code, removes all old signatures/profiles, strips executable signatures without
rewriting their code/chained fixups, and appends the required library commands.
Every Info.plist is stored uncompressed for signer compatibility.

## Installation and validation

Use Sideloadly's Apple ID signing/install mode. Load the standalone IPA and do not
add another tweak or another generic identity-spoofing module. The package already
contains its own modules. Full recursive signing and a valid provisioning profile
are still required. The app is separate from App Store YouTube; do not uninstall
the original app to test it.

Build success and ad-hoc codesign checks do not prove installation on an iPhone.
Device tests are required for launch, normal playback, pre-roll/mid-roll ads,
feed/search ads, screen-off background audio, PiP and user pause retention.
Google account login uses a private callback scheme and compatibility hooks, but
is unverified. The exact root cause of the earlier `0xe8008001` installation error
is not established from the screenshot alone.

## Upstream sources

- https://github.com/PoomSmart/YouTube-X
- https://github.com/PoomSmart/YouPiP
- https://github.com/PoomSmart/YTVideoOverlay

Upstream MIT license notices are included with the packaged modules.
