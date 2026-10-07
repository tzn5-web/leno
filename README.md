# Leno

Minimal iOS YouTube client scaffold for iPhone, targeting iOS 27+ and built entirely in GitHub Actions.

## Current scope

- YouTube web client hosted in WKWebView
- Early injected JSON filter adapted from the user's Tizen implementation
- Removes YouTube ad payload keys: `adPlacements`, `playerAds`, `adSlots`
- Content rules for common external ad domains
- DOM fallback to remove ad UI and press skip controls when present
- Native background audio session
- Lock Screen / Control Center play, pause and ±15 second commands
- Picture in Picture request bridge
- Automatic WebKit/navigation recovery with bounded retries
- No analytics or third-party SDKs
- Unsigned device build packaged as an IPA artifact in CI

## Reliability model

The Tizen package uses a health gate plus fallback architecture. Leno mirrors that philosophy on iOS with explicit loading/recovery states, bounded retries, WebKit process recovery, and one authoritative media-session path to avoid competing remote-control handlers.

## Build

GitHub Actions uses the `xcode-27` runner, generates the Xcode project with XcodeGen, runs a device build and static analysis, then uploads an unsigned IPA artifact.
