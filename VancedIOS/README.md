# VancedIOS

VancedIOS is an iOS Vanced/ReVanced-style patch layer for the official YouTube
application. It is **not a standalone YouTube clone** and does not use the old
WKWebView, AVPlayer handoff, MPV client, Resolver, or V9 playback architecture.

The user supplies a decrypted YouTube IPA. VancedIOS builds immutable, pinned
tweak modules, injects them into that host, and validates the input and output
before an IPA is accepted.

## Supported host contract

The current compatibility baseline is intentionally strict:

- official input bundle: `com.google.ios.youtube`;
- tested YouTube version: **21.18.4**;
- device architecture: **arm64**;
- minimum VancedIOS target: **iOS 15.0**;
- input Mach-O must be decrypted (`cryptid == 0`);
- the host must expose background audio capability;
- the repository never downloads or commits a YouTube IPA.

A different YouTube version is treated as unsupported until its hooks are
re-audited and the manifest is deliberately moved to that version.

## Architecture

1. **Host** — user-supplied decrypted YouTube IPA.
2. **YouMod** — ad filtering, background playback, SponsorBlock, persistent
   quality/speed controls, player and Shorts/UI behavior.
3. **YTVideoOverlay** — shared player overlay substrate.
4. **YouPiP** — native Picture in Picture integration.
5. **YTUHD** — quality/codec extension for sideloaded YouTube.
6. **Return YouTube Dislikes** — dislike counter integration.
7. **VancedIOSCore** — a deliberately small integration/defaults/diagnostic
   layer. It does not install a second lock-screen command center, audio
   session, or application-background playback engine.
8. **Cyan / pyzule-rw** — jailed IPA injection/repackaging.
9. **Stage runner** — static contract audit, source-hook audit, deterministic
   build, package/Mach-O audit, and optional host/injection audit.

All external source repositories are pinned to exact 40-character commits in
`manifest.json`.

## Required behavior

The architecture preserves the original YouTube navigation, account, Home,
Search, Subscriptions, comments and player pipeline while adding:

- ad filtering;
- background playback;
- native PiP;
- SponsorBlock;
- Return YouTube Dislike;
- persistent quality and playback-speed settings;
- player/Shorts conveniences exposed by the pinned patch layer.

The official YouTube media session remains authoritative. This is deliberate:
the previous custom-player approaches created competing playback authorities
and caused pause/resume, lock/unlock and PiP regressions.

## Autonomous audit runner

Hostless build/audit:

```bash
python3 VancedIOS/Scripts/stage_runner.py \
  --build \
  --report-dir artifacts/vanced-ios-stage-audit
```

Validate a user-supplied host without injection:

```bash
python3 VancedIOS/Scripts/stage_runner.py \
  --ipa /path/to/decrypted-YouTube.ipa
```

Full injection plus postflight validation:

```bash
python3 VancedIOS/Scripts/stage_runner.py \
  --ipa /path/to/decrypted-YouTube.ipa \
  --inject \
  --output /path/to/VancedIOS.ipa \
  --bundle-id com.google.ios.youtube \
  --display-name YouTube
```

The runner emits `report.json`, `report.md`, command logs and package
SHA-256 values. Hard failures make the runner exit non-zero. A hostless run can
only finish as `PASS_HOSTLESS`; only a real supplied IPA can reach
`PASS_HOST_VALIDATED` or `PASS_FULL`.

## Validation gates

The runner and scripts check, among other things:

- Python and shell syntax;
- official host bundle/version/architecture/background contract;
- decrypted Mach-O state;
- exact dependency revisions, including Theos, SDK and headers;
- presence of upstream ad/background/SponsorBlock/PiP/quality/speed hooks;
- no competing media/lifecycle authority in VancedIOSCore;
- deterministic rootless package production;
- exact six-package output and arm64 dylibs;
- injected dylib presence and `LC_LOAD_DYLIB` references;
- GitHub Actions least privilege and immutable action revisions;
- absence of proprietary YouTube IPA/app binaries in the repository.

## GitHub Actions

- `VancedIOS Stage Audit` runs the full hostless audit/build on the stage
  branch and pull requests into `vanced-ios-patcher`.
- `VancedIOS Patch Build` builds release patch artifacts through the same
  runner.
- `VancedIOS Inject User IPA` accepts a user-provided decrypted host URL,
  builds the pinned patch set, injects it, runs strict postflight validation,
  uploads the validated unsigned IPA artifact, then removes host/generated IPA
  files from the ephemeral runner.
