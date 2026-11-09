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


## Glass + advanced emoji extension (2026-11-09)

The updated project keeps the original Xiaomi `classes.dex`, original letters, layout and **every key-border image unchanged**. It adds a small secondary DEX containing:
- `GlassLatinIME` extending the original `com.android.inputmethod.latin.LatinIME`. The existing service is redirected to this subclass, not replaced with a new keyboard renderer.
- `GlassSettingsActivity` accessible through the tiny ⚙ icon over the suggestion bar. Background opacity range is **0–100%**, with independent blur radius. Appearance preferences only; typed content is not persisted by this extension.
- An integrated **☺+** emoji panel with eight categories, recent Unicode glyphs, and a skin-tone selector. Emoji are committed to the focused app using `InputConnection.commitText`. No clipboard access, telemetry or emoji history.
- Original keyboard and suggestion-strip nine-patch backgrounds are made transparent while their compiled nine-patch metadata is preserved. The alpha overlay is rendered underneath the original keys. Glass blur depends on One UI window blur support.

**Security/privacy caveat:** the unchanged original `classes.dex` still contains dictionary and storage code. We explicitly set the existing preferences for personalized dictionaries and contacts access to off at service startup, but a full dynamic no-storage guarantee requires instrumentation and device verification. This is a test candidate.

### Reproduce in GitHub

See [Compile Xiaomi LatinIME Glass and Emoji extension](../../.github/workflows/s24-latinime-glass-emoji-addon.yml). PR/push builds the extra DEX on GitHub and runs a static extension privacy check. A manual `workflow_dispatch` with an HTTPS `apk_url` builds a full signed test APK using `prepare_original.py` and `build_glass_apk.py`. The original user-supplied binary is never committed to this public repository.

When GitHub creates a new temporary signing key, **uninstalling a previous user-installed test build may be necessary** because Android prohibits updating with a different signature. Never uninstall a system keyboard.

Static compilation and ZIP integrity are checked. Actual appearance and behavior have **not** been verified on a physical S24 running One UI 8.5.
