# S24 Private Keyboard — Android / Samsung One UI 8.5

A self-contained, **newly implemented** Android input method for Galaxy S24/S24+/S24 Ultra. It is not the Xiaomi APK and does not reproduce all of LatinIME's features. The original Xiaomi archive is deliberately **not** committed to GitHub.

## Functional scope (v0.1)

- Android InputMethodService; QWERTY, Romanian diacritics, Shift, delete, space, punctuation, numeric/symbol mode and editor actions.
- No native binaries or JNI, so no ABI dependency; usable on ARM64-only devices.
- No prediction, word learning, cloud sync, clipboard reads, personal dictionary, typing history or telemetry.
- No `<uses-permission>` entries (not even `INTERNET`). InputMethodService is protected by Android's required `BIND_INPUT_METHOD` service permission; this is **not** a permission requested by the app.
- `allowBackup=false`, cleartext traffic disabled, no network SDK or third-party runtime library.
- Text is delivered solely through Android's `InputConnection` to the focused application. The receiving application and Android OS may process it; this app cannot control those systems.

## Build in GitHub Actions

Open **Actions → Build S24 Private Keyboard → Run workflow**, or open the pull request. Download the uploaded artifact `S24PrivateKeyboard-debug` and install `app-debug.apk` on the phone.

The CI build runs a source-level privacy gate. Passing this check does not replace device testing or full security review.

## Install

1. Install the debug APK and open **S24 Private Keyboard**.
2. Tap **Enable keyboard** to activate it in Samsung's keyboard settings.
3. Tap **Select keyboard**, then choose **S24 Private Keyboard**.
4. Test ordinary text, Romanian characters, password fields, numbers and editor action keys.

This build installs under `dev.tzn5.privatekeyboard` alongside the Xiaomi original; no vendor signature conflicts.

## Known limitations

This is a privacy-first **functional MVP**, not a byte-for-byte port of Xiaomi LatinIME. Gesture typing, voice input, advanced autocorrect, adaptive layouts, multilingual prediction and theme editor are not implemented. A successful CI build is not proof of stability on the user's specific One UI 8.5 device.
