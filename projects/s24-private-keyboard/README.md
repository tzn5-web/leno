# S24 Glass Keyboard — One UI 8.5

This is a reimplementation built from the GitHub IME source, not an exact Xiaomi APK repack.

## Implemented v0.9
- Offline English/Romanian QWERTY, ă â î ș ț, numeric/symbol mode, shift, caps lock, long-press accents, repeat delete and editor actions.
- Settings gear inside the keyboard and Settings activity from launcher.
- Glass background transparency, key opacity, key height, rounding, spacing, three palettes (Smoke, Ruby black/red, Ice).
- Optional Android 12+ system blur (device-dependent), optional haptic typing feedback.
- Eight categorized Unicode emoji groups, with long-press tone choices for hand gestures.
- No Internet permission, telemetry, network, clipboard reads, text history, or personal dictionary. Only appearance preferences persist.

## APK
CI: https://github.com/tzn5-web/leno/actions/workflows/s24-private-keyboard.yml
Direct APK is published at https://github.com/tzn5-web/leno/releases/download/s24-glass-keyboard-v0.9/S24-Glass-Keyboard.apk when the release step succeeds.
GitHub Actions artifact is the backup. The debug certificate can change between hosted-runner builds; upgrading prior debug installs can require uninstalling.

## Limitations
Not a byte-for-byte port of Xiaomi, no prediction/gesture typing, no Xiaomi-native theme editor. Successful CI compilation is not proof of stability or exact visuals on an S24+ with One UI 8.5. Device checks remain necessary.
