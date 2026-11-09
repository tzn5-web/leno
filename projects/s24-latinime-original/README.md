# Original Xiaomi LatinIME → Samsung S24 (test candidate)

This project preserves the **actual Xiaomi 11T LatinIME code and original visual resources**, unlike the earlier, unrelated QWERTY MVP. The user's APK is not committed to the public repository.

The repair:
- Retains `classes.dex`, keyboard layouts, visual resources, language resources and dictionaries from the original APK.
- Places the bundled ARM64 native library (`assets/lib64/libjni_latinimegoogle.so`) in Android's standard `lib/arm64-v8a/` directory, and includes the 32-bit counterpart.
- Removes all `uses-permission` entries (including contacts, accounts, external storage and dictionary permissions), and disables app backup.
- Re-signs the modified APK with a test key.

**Important privacy limitation:** The original `classes.dex` is preserved. It contains dictionary and preferences code. Removing permissions does not prevent private app storage, and does **not** prove that words typed are never recorded locally. It cannot claim full zero-retention until the internal learning/persistence code is audited and disabled. There was no INTERNET permission in the original manifest.

**Compatibility limitation:** The original was observed crashing on Samsung S24, but the corrected native library location is only a plausible fix; Samsung One UI 8.5 device testing is outstanding. This project is a test build, not a guarantee.

## Run the GitHub workflow

1. Open **Actions → Repair Original Xiaomi LatinIME for S24 → Run workflow**.
2. Supply an HTTPS URL to the original `LatinIME.apk` file that the GitHub runner can download, and optionally SHA256 `568f9889a49451ef4d8d01b937de8c785c1c85c5d23e5398fcb41eac2fef144b` for the supplied extracted original.
3. Download the `LatinIME-S24-original-ui-test` artifact.

Each workflow run uses a disposable signing key, so updating a previous test install in place will fail signature verification. Uninstall only a previous *user-installed* `com.android.inputmethod.latin` APK if Android shows a signature conflict. Do not uninstall a system keyboard.

For local builds, run `python3 prepare_original.py LatinIME.apk unsigned.apk`, then zipalign and sign with official Android SDK `apksigner`.

Never rely on this candidate for highly sensitive typing until it has been verified on-device and the privacy requirement fully implemented.
