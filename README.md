# Leno

Minimal native iOS media player for iPhone, designed for iOS 27+ development and built entirely in GitHub Actions.

## Architecture goals

The stability model is inspired by the supplied Tizen TubeVanced package: local critical components, explicit startup/playback states, health/recovery behavior, and a fallback-oriented design rather than a single fragile execution path.

## Current scope

- SwiftUI shell with Home / Search / Library
- AVPlayer-based playback
- Background audio session
- Lock Screen / Control Center media commands
- Picture in Picture
- Explicit playback state machine
- Limited automatic retry and stall recovery
- Manual retry and clean player reset
- No analytics or third-party SDKs
- Unsigned device build packaged as an IPA artifact in CI

## Compatibility boundary

The project intentionally keeps media-source integration separate from the native player. It does not include code that bypasses YouTube advertising, Premium entitlements, DRM, or access controls.

## CI quality gates

GitHub Actions uses the `xcode-27` runner and XcodeGen. CI performs:

1. project generation;
2. Debug simulator compilation;
3. static analysis;
4. Release device compilation with signing disabled;
5. unsigned IPA packaging;
6. artifact upload.
