# Xiaomi 11T LatinIME — Glass + emoji, Samsung S24

This is an **extension of the original, working Xiaomi LatinIME APK**, not a new keyboard UI. It preserves the original **key drawings, borders, labels, dictionary/resource assets and native ARM64 libraries byte-for-byte**. The original Java `classes.dex` is intentionally **rewritten** to retain the original `LatinIME` service identity while subclassing the Xiaomi engine, and to suppress known local word/emoji-history persistence paths. It is incorrect to claim the original DEX is byte-identical in the Glass release.

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
5. Open the keyboard's settings from Android/Samsung keyboard settings if offered. The standard settings gear routes to GlassActivity. Set opacity and reopen the keyboard to apply. The quick Samsung IME chooser's gear is OEM-controlled and may still appear only for Samsung Keyboard; this APK cannot force that UI. As a reliable fallback, long-press the **☺ Emoji** key in the keyboard's own top bar to open Glass settings; tap it briefly to open the emoji picker.
6. To use advanced emoji, tap **☺ Emoji** above the original keyboard; search remains entirely in RAM.

The original keyboard APK and private signing key must not be uploaded to this public repository. Compilation and static integrity checks do not replace installation and visual validation on the Samsung phone.

## Validation

The extension's GitHub Actions job compiles against Android API 35 and checks that no addon network/telemetry/file logging APIs are referenced. The final repacker verifies that original `res/`, `assets/` and `lib/` files (apart from required IME metadata changes) remain byte-identical. The original `classes.dex` must differ due to service rebinding and privacy patches. Device-side testing is required for visual transparency, optional blur, emoji input and stability.

## Verification — system gear build

- The original APK's `res/xml/method.xml` previously referenced LatinIME's original settings activity. `patch_picker_gear.py` redirects this field to `GlassActivity`.
- It removes the only `android.intent.category.LAUNCHER` entry from the manifest. GlassActivity stays exported for system settings.
- The original keyboard **assets** remain byte-identical; `classes.dex` is **rebound** and privacy-patched. The add-on `classes2.dex` provides the Glass service and advanced emoji controls.
- GitHub Actions compiles and checks the addon, but the completed APK is signed locally using the same development certificate as the user's working test installation; the signing key is never committed.

**Settings UX:** A short press on the dedicated emoji key opens categories/search; long press opens Glass appearance settings. No separate settings button is displayed. The system IME metadata points to the same GlassActivity, subject to One UI rendering the settings gear.

## Privacy hardening for the original Xiaomi engine

In addition to removing Android app permissions and disabling backup, `PrivacyNoHistoryPatch` applies a fail-closed DEX modification to the **original** LatinIME engine. It blocks eight identified dynamic vocabulary write/flush paths. Seven methods become no-ops; `updateEntriesForInputEvents` skips writing but still invokes its `onFinished()` callback, preventing pending completion handlers from being stranded: `DictionaryFacilitatorImpl.addToUserHistory`, `addWordToUserHistory`, `ExpandableBinaryDictionary.updateEntriesForWord`, `updateEntriesForInputEvents`, `asyncFlushBinaryDictionary`, `addUnigramLocked`, `addNgramEntryLocked`, and `UserHistoryDictionary.addToDictionary`. It retains read-only dictionary lookup and the visual keyboard.

A one-time cleanup also attempts `PersonalizationHelper.removeAllUserHistoryDictionaries(Context)` before the original keyboard initializes, so histories created by earlier installs can be removed. Only a boolean cleanup marker is stored.

To build the privacy-hardened version, first run `DexServiceRebind original.dex glass-addon.dex rebound-original.dex rebound-addon.dex`, then `PrivacyNoHistoryPatch rebound-original.dex privacy-rebound-original.dex`. Supply `privacy-rebound-original.dex` to `repack_stable_ime.py` in place of `rebound-original.dex`. The CI workflow tests the patch against eight synthetic write methods and verifies the rewritten DEX reopens.

**Security limitation:** the original native ARM64 library and all possible storage paths have not been dynamically audited on Samsung. Blocking these eight methods and removing INTERNET permission materially reduces risk but cannot be represented as an absolute guarantee of no data retention. Do not treat this build as independently security-certified.


## Runtime release gate (10 November 2026)

- **PASS:** Native Xiaomi `LatinIME` service class ABI confirmed non-final and overridable; Glass subclass lifecycle linkage checked on the real Xiaomi DEX. Vocabulary history and old emoji recents read/write paths are disabled in patched Java bytecode. Original visual assets unchanged.
- **PASS:** Android 16 emulator with an isolated test-only keyboard base demonstrates advanced emoji insertion, long-press settings, opacity slider persistence, visible Glass pixel changes, and 12 hide/reopen cycles.
- **PASS:** Optional fixed dark Emoji button chip and navigation-bar insets improve legibility and avoid controls beneath Android gesture navigation.
- **BLOCKED:** *Full original Xiaomi APK on Samsung S24* has not undergone runtime checks. The original Xiaomi JNI `libjni_latinimegoogle.so` is ARM64. Android 16 GitHub UI tests use an x86_64 synthetic base, **not** the real Xiaomi engine.
- **BLOCKED:** The GitHub ARM64 runner probe established that `ubuntu-24.04-arm` lacks Android SDK/emulator and KVM, so it cannot simply host an accelerated native Android emulator. The probe is manual-only to avoid recurring CI load.
- **BLOCKED:** An in-place upgrade needs the private signing key matching the APK installed on the user phone. The cert is known, but the private key is not present; a new signature would require uninstalling the existing app first. Never claim that copying a certificate allows signing.
- **BLOCKED:** Original native library imports filesystem write routines. Java history patching alone cannot certify the user's absolute no-typed-text-retention requirement.
- **Shipping policy:** Do not distribute the simulated-test APK as the real Xiaomi keyboard. No final APK until full hardware-compatible runtime validation and appropriate update signature are possible.
