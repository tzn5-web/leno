# Standalone YouTube Vanced with local Premium feature gates

Packages the user's decrypted official YouTube **20.21.6** as an independent app.
The earlier direct Guest candidate FAILED the user's playback test and is withdrawn.
The current candidate is experimental until tested on the user's iPhone.

## Current behavior

- Separate OS bundle `ro.ion.youtubevanced`, private URL schemes, sandbox and signing keychain group.
- Preserve Google's OAuth-derived SSO callback; SSOSafariSignIn uses ASWebAuthenticationSession.
- Only automatic startup transactions enter Guest; explicit Google login remains native, including coalesced requests.
- Local Unlimited/Premium account-menu flag and branding, background/PiP availability gates enabled.
- YouTube-X continues to filter ads; YouPiP/overlay provide native PiP.
- Dedicated upgrade-check requests finish locally with their native completion. Native worker lifecycle remains intact.
- Reported IOS client version uses the verified Apple catalog version (21.40.5 on 2026-10-08), refreshed asynchronously from Apple's lookup at most once per day after a successful lookup. Other client types retain their original protobuf version.
- The actual executable remains 20.21.6. A version label does not implement newer response protocols or prove compatibility with future versions.
- Identified YouTube watch/statistics and Google telemetry URLs are intercepted in URLSession and acknowledged locally; no upload is performed through those routes.
- The app-local native history flag is paused. The local library records history, position, favorites and playlists both with and without Google login, except in incognito or when local recording is paused.
- No local diagnostic/error report or telemetry log is included.

## Privacy and runtime limits

OAuth, player, browse/search, attestations and media are allowed to communicate with Google.
Authenticated playback necessarily sends account authorization and requested video IDs.
This does not promise invisibility from the service or prevent its server from inferring
activity from necessary requests. The interceptor covers the listed routes in VPrivacy.m;
background sessions, other native transports and Google's browser process are not proven
covered. Google account settings are not globally changed. The local JSON library is
not uploaded to the account. Native Home is not replaced by a local recommendation algorithm.
Blocking watch signals therefore does not establish personalized Home based on local history.

Premium hooks affect local flags and feature gates. They do not create a paid Google
subscription, manufacture media URLs or override the main isPlayable check. A server-side
refusal can still occur. No successful login, full video playback, PiP, ad blocking or
background playback on the current user's phone is claimed from CI tests alone.

## Build and installation

The workflow builds only open-source modules. The proprietary IPA and signing credentials
stay local. Sources are pinned in dependencies.json; licenses ship in VancedLicenses.
Modules use Logos' internal Objective-C backend and have no external jailbreak runtime.

On a Mac with Xcode:

```sh
python3 VancedIOS/Standalone/build.py
python3 -m unittest discover -s VancedIOS/Standalone/Tests -p 'test_*.py'
python3 VancedIOS/Standalone/package.py /path/to/youtube-v20.21.6.ipa \
  VancedIOS/Standalone/artifacts /path/to/YouTube_Vanced_UNSIGNED.ipa
```

Sign/install the unsigned IPA with Sideloadly's normal Apple ID mode and recursive signing.
Do not inject additional tweaks into this package. Retain the same signing identity/bundle
suffix to update the existing sandbox rather than deleting the local library. Five original
Google app extensions are excluded. App Store YouTube can coexist with this app.

Validation covers native fixture routing, dynamic protobuf getters, verified-format version
updates, privacy URL scope, local HTTP completion, upgrade callbacks, persistence and
module re-signability. These checks do not establish acceptance by Google's servers.
