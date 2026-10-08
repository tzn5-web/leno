# Vanced iOS

For the current standalone app with video/feed ad blocking, background playback
and native PiP, use [Standalone/README.md](Standalone/README.md). Its bundle ID is
`ro.ion.youtubevanced`, separate from App Store YouTube. The legacy VancedCore
implementation documented below does not provide these three playback features.

This directory is the isolated implementation path for the requested iOS Vanced experience.

It does **not** build the legacy SwiftUI/WKWebView client under `../Leno`. The runtime base is a user-supplied decrypted official YouTube iOS IPA/app. No YouTube binary is stored in this repository.

## Product target

- official YouTube UI/navigation/account experience remains the base
- video/feed ad suppression
- native background playback
- native Picture in Picture
- lock/unlock without a forced replay command
- user Pause remains Pause; no lifecycle auto-resume takeover
- SponsorBlock
- Return YouTube Dislike
- remembered video quality
- remembered playback speed
- Shorts/UI controls

`Config/implementation_status.json` is authoritative for what is actually implemented. The full product audit intentionally stays `NEEDS_REVIEW` until every required item has implementation and validation evidence.

## Current implemented core

- remembered playback speed using crash-tolerant dynamic YouTube runtime hooks
- remembered video quality with exact/closest available quality-label mapping
- optional native Shorts shelf/cell filtering outside history
- native SponsorBlock auto-skip using the public SponsorBlock API and a four-character SHA-256 prefix query
- Return YouTube Dislike count retrieval and dislike-button integration for normal/Shorts UI paths
- an independent `Vanced` section inside YouTube Settings for these controls

These items remain unvalidated until the macOS compile gate and a compatible decrypted YouTube IPA pass the static compatibility audit. Device-only behavior is never marked passed from static analysis.

## Architecture rules

`VancedCore` extends the native YouTube application in place. It does not introduce WKWebView, a mobile-web YouTube client, a replacement AVPlayer/MPV player, a remote stream resolver, or a second media-session owner.

The audit runner rejects those legacy architectures if they leak into `VancedIOS/`.

Third-party repositories in `Config/dependencies.lock.json` are pinned research/build references. A pin in that file does not mean the dependency is automatically linked into the product. `PSHeader` is explicitly marked `NO-LICENSE-DETECTED` and must not be vendored/distributed unless its terms are resolved.

## Audit

Full product stage gate:

```bash
cd VancedIOS
bash Scripts/run_stage_audit.sh
```

Audit a decrypted stock YouTube IPA/app without applying the full product-completeness gate:

```bash
python3 Scripts/audit.py --ipa-only --ipa /path/to/YouTube.ipa
```

The IPA audit checks bundle identity, version/build metadata, arm64, Mach-O encryption state where `otool` is available, and the YouTube classes/selectors required by each implemented runtime hook.

## Build

Compile the arm64 tweak core only:

```bash
cd VancedIOS
bash Scripts/build.sh
```

Package the implemented core into a user-supplied decrypted stock YouTube IPA:

```bash
cd VancedIOS
bash Scripts/build.sh /path/to/YouTube.ipa
```

The packaging path performs pre-build IPA compatibility checks, uses Theos jailed packaging, then audits the resulting IPA for `Frameworks/VancedCore.dylib` and a corresponding Mach-O load command. Reports are written under `VancedIOS/reports/`. Generated IPA/dylib/report/toolchain paths are ignored by Git.

## Runtime device gates

The full project is not complete until device tests prove background continuation, lock-screen Pause/Play state preservation, unlock state restoration, PiP while navigating YouTube, return-from-PiP state preservation, ad suppression, SponsorBlock skipping, and RYD UI behavior. See `Config/feature_matrix.json`.

## Service attribution

- SponsorBlock API: `https://sponsor.ajay.app/`
- Return YouTube Dislike API: `https://returnyoutubedislikeapi.com/`

The API integrations use bounded request timeouts and local caches. SponsorBlock uses the hash-prefix endpoint rather than sending the full video ID in the request path.
