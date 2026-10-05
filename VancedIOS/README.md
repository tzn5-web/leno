# Vanced iOS

This directory is the clean-room implementation path for the requested iOS Vanced experience.

It does **not** build the legacy SwiftUI/WKWebView client under ../Leno. The base application is a user-supplied decrypted official YouTube iOS IPA/app. This project builds and injects a jailed tweak stack into that app.

## Required behavior

- official YouTube UI/navigation/account experience remains the base
- video/feed ad suppression
- native background playback
- native Picture in Picture
- lock/unlock without a forced replay command
- user Pause remains Pause; this project does not hook app lifecycle to auto-resume
- SponsorBlock
- Return YouTube Dislike
- remembered/default quality controls
- remembered/default playback speed controls
- YouTube A/B and UI controls, including Shorts-related controls where supported

## Architecture

VancedCore is our own small runtime hook layer. It owns ad suppression and background-playability hooks and deliberately does not replace YouTube's player with AVPlayer, WKWebView, MPV, or a remote stream resolver.

Large mature features are built from pinned source modules and injected as separate dylibs. Exact commit SHAs and licenses are recorded in Config/dependencies.lock.json. Third-party source is fetched only during a build and is not vendored here.

The input IPA is never committed or uploaded by these scripts.

Static success is not proof of runtime success. Lock-screen, PiP, foreground/background transitions, and playback-state preservation remain explicit device test gates.
