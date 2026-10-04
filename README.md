# Leno

Minimal iOS media player scaffold for iPhone, designed for iOS 27+ development and built entirely in GitHub Actions.

## Current scope

- SwiftUI shell with Home / Search / Library
- AVPlayer-based playback
- Background audio session
- Lock Screen / Control Center media commands
- Picture in Picture
- No analytics, ads, or third-party SDKs
- Unsigned device build packaged as an IPA artifact in CI

## Policy boundary

This project does not contain code to bypass YouTube advertising, Premium entitlements, DRM, or access controls. Media providers are intentionally isolated behind a clean integration boundary.

## Build

GitHub Actions uses the `xcode-27` runner, generates the Xcode project with XcodeGen, builds for generic iOS with code signing disabled, and uploads an unsigned IPA artifact.
