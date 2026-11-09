# Xiaomi 11T LatinIME — Glass + emoji, Samsung S24

This is an **extension of the original, working Xiaomi LatinIME APK**, not a new keyboard UI. It keeps the original `classes.dex`, original key drawings, borders, labels, dictionaries, language assets, and native ARM64 library **byte for byte**.

## Features

- **Glass background only:** slider with 0–100% background opacity; 0 = transparent, 100 = original opacity. Background drawables on keyboard/suggestion containers only; no change to keycaps, legends, or their borders.
- **Optional system compositor blur:** Android 12+ `FLAG_BLUR_BEHIND`, when supported by the device/window compositor. Blur strength/appearance cannot be guaranteed on Samsung One UI.
- **Appearance settings:** registered through Android's `android:settingsActivity` in `res/xml/method.xml` (settings gear in supporting system UI). No separate launcher icon and no Glass settings button in the keyboard. Android/Samsung controls whether a gear is shown directly in the quick IME picker.
- **Advanced emoji:** a compact **☺ Emoji** shortcut in the dedicated top row, category tabs, in-memory Romanian/English search, skin tone variants, and Unicode emoji rendered by Android. Original emoji UI remains intact.
- **No new network, analytics or keystroke logging:** extension contains no HTTP, logging, clipboard reads, usage history or text storage. Only appearance switches and opacity are saved.
- Compatible with Android API 30+; the APK's original minimum and target SDK settings remain unchanged.

**Privacy limitation:** the original `classes.dex` is intentionally preserved. Its existing dictionary and personalization logic may write local data; therefore absolute zero text retention is **not yet verified**. The original APK repair removed requested permissions but did not rewrite its internal learning algorithms.

## Build process

1. Run the GitHub workflow `S24 Xiaomi LatinIME Glass + Emoji addon`. Download artifact `S24-LatinIME-Glass-Emoji-DEX`, which contains `classes.dex` for the extension.
2. Prepare the previously working, signed `LatinIME_S24_OriginalUI_Test.apk` (this personal APK is **not** committed publicly).
3. Use `repack_glass.py` or a verified local repacker to preserve the original LatinIME resources and create an unsigned APK containing the updated `classes2.dex`. Run `python3 patch_picker_gear.py input-unsigned.apk picker-unsigned.apk` to point the IME's `settingsActivity` to `GlassActivity` and remove the app launcher category. The patcher keeps both DEX files and all keyboard resources unchanged.
4. Sign the unsigned APK with Android SDK `zipalign` and `apksigner`, using **the same signing certificate as the previously installed working APK**. Reinstalling with a different certificate causes `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.
5. Open the keyboard's settings from Android/Samsung keyboard settings if offered. The standard settings gear routes to GlassActivity. Set opacity and reopen the keyboard to apply. The quick Samsung IME chooser's gear is OEM-controlled and may still appear only for Samsung Keyboard; this APK cannot force that UI.
6. To use advanced emoji, tap **☺ Emoji** above the original keyboard; search remains entirely in RAM.

The original keyboard APK and private signing key must not be uploaded to this public repository. Compilation and static integrity checks do not replace installation and visual validation on the Samsung phone.

## Validation

The extension's GitHub Actions job compiles against Android API 35 and checks that no addon network/telemetry/file logging APIs are referenced. The repacker verifies that all original `res/`, `assets/`, `lib/` and the original `classes.dex` remain byte-identical. Device-side testing is required for visual transparency, optional blur, emoji input and stability.

## Verification — system gear build

- The original APK's `res/xml/method.xml` previously referenced LatinIME's original settings activity. `patch_picker_gear.py` redirects this field to `GlassActivity`.
- It removes the only `android.intent.category.LAUNCHER` entry from the manifest. GlassActivity stays exported for system settings.
- The original `classes.dex` and keyboard assets remain byte-identical; the replacement addon `classes2.dex` no longer includes a Glass settings toolbar button.
- GitHub Actions compiles and checks the addon, but the completed APK is signed locally using the same development certificate as the user's working test installation; the signing key is never committed.
