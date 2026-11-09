# Xiaomi 11T LatinIME — Glass + emoji, Samsung S24

This is an **extension of the original, working Xiaomi LatinIME APK**, not a new keyboard UI. It keeps the original `classes.dex`, original key drawings, borders, labels, dictionaries, language assets, and native ARM64 library **byte for byte**.

## Features

- **Glass background only:** slider with 0–100% background opacity; 0 = transparent, 100 = original opacity. Background drawables on keyboard/suggestion containers only; no change to keycaps, legends, or their borders.
- **Optional system compositor blur:** Android 12+ `FLAG_BLUR_BEHIND`, when supported by the device/window compositor. Blur strength/appearance cannot be guaranteed on Samsung One UI.
- **Appearance settings:** app icon / launcher entry and small **Glass ⚙** shortcut in a separate 34 dp bar above the original keyboard.
- **Advanced emoji:** separate **☺ Emoji** button in that bar, category tabs, in-memory Romanian/English search with its own mini-keyboard, skin tone variants, and Unicode emoji rendered by Android. Original emoji UI remains intact.
- **No new network, analytics or keystroke logging:** extension contains no HTTP, logging, clipboard reads, usage history or text storage. Only appearance switches and opacity are saved.
- Compatible with Android API 30+; the APK's original minimum and target SDK settings remain unchanged.

**Privacy limitation:** the original `classes.dex` is intentionally preserved. Its existing dictionary and personalization logic may write local data; therefore absolute zero text retention is **not yet verified**. The original APK repair removed requested permissions but did not rewrite its internal learning algorithms.

## Build process

1. Run the GitHub workflow `S24 Xiaomi LatinIME Glass + Emoji addon`. Download artifact `S24-LatinIME-Glass-Emoji-DEX`, which contains `classes.dex` for the extension.
2. Prepare the previously working, signed `LatinIME_S24_OriginalUI_Test.apk` (this personal APK is **not** committed publicly).
3. Use `python3 repack_glass.py LatinIME_S24_OriginalUI_Test.apk S24-LatinIME-Glass-Emoji-DEX.zip output-unsigned.apk`. The script replaces only the manifest's LatinIME service entry with `GlassIME`, the Setup activity with `GlassActivity`, injects a launcher category, and adds `classes2.dex`.
4. Sign the unsigned APK with Android SDK `zipalign` and `apksigner`, using **the same signing certificate as the previously installed working APK**. Reinstalling with a different certificate causes `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.
5. Open the new **Xiaomi Keyboard · Glass** icon or tap **Glass ⚙** above the keyboard. Set opacity and reopen the keyboard to apply.
6. To use advanced emoji, tap **☺ Emoji** above the original keyboard; search remains entirely in RAM.

The original keyboard APK and private signing key must not be uploaded to this public repository. Compilation and static integrity checks do not replace installation and visual validation on the Samsung phone.

## Validation

The extension's GitHub Actions job compiles against Android API 35 and checks that no addon network/telemetry/file logging APIs are referenced. The repacker verifies that all original `res/`, `assets/`, `lib/` and the original `classes.dex` remain byte-identical. Device-side testing is required for visual transparency, optional blur, emoji input and stability.
