# Standalone YouTube Vanced with local Premium feature gates

Packages the user's decrypted official YouTube **20.21.6** as an independent app.
The earlier direct Guest candidate FAILED the user's playback test and is withdrawn.
The current compatibility candidate is experimental until tested on the user's iPhone. In particular, Google can reject a sideloaded app whose actual bundle/team identity is not registered for the original OAuth client; callback registration cannot override Google's App Check.

## Current behavior

- Separate OS bundle `ro.ion.youtubevanced`, private URL schemes, sandbox and signing keychain group. Packaging preserves declared Google SSO callback schemes and the GoogleService reversed OAuth client scheme while keeping official YouTube deep links unclaimed.
- Preserve Google's OAuth-derived SSO callback; SSOSafariSignIn uses ASWebAuthenticationSession.
- Native Google login and the native Guest choice are preserved by default. The legacy automatic Guest completion is disabled unless explicitly opted in; it was a plausible source of missing player authorization.
- Local Premium account branding/entitlement is disabled by default (it never conferred a server membership). Background/PiP client-side availability gates stay enabled.
- YouTube-X continues to filter ads; YouPiP/overlay provide native PiP.
- Dedicated upgrade-check requests finish locally with their native completion. Native worker lifecycle remains intact.
- Native client versions (20.21.6) are preserved in network requests by default. The legacy reported-version override is experimental opt-in only; it cannot make an old binary implement newer protocols.
- The executable remains 20.21.6. Native upgrade dialogs/checks are suppressed locally without inventing a new protocol version; this does not prevent a future server-side minimum-version requirement.
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
