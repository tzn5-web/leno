# Implementation checkpoint — no additional handset audits (2026-11-09)

We already have all artifacts required for offline work:
- Installed GloryFit Android APK set, including base.apk and ABI/language splits.
- Original downloaded dial `DialCustom_240x240_90.zip`.
- Cached binary `D1898001.bin`, with 22 element records and confirmed 240×240 RGB565 format.
- HOLO V1 layered prototype and HOLO V2 343,944-byte binary candidate.

The prior `Watch6T-Cache-Gate.ps1` request was **redundant**, because the user's supplied APK archive already included `D1898001.bin`. Do not ask user to run it again.

## Offline implementation path

1. Trace the *call graph*, not a new ADB dump, from `ActsDialCommandUtil.uploadWatchFace()` through `setWatchFaceType()` and `prepareSendWatchFaceData()` to `WriteCommandToBLE.writeCharaBle5()`.
2. Trace `setImageWatchFace()` separately through `getSetImageWatchFaceCmd()` and `startSendDataSegments()`.
3. Determine which of these two protocols is used by the model before selecting a path to install a modified candidate.
4. Preserve a stock face and never use the **firmware update** endpoint to transfer an unvalidated watchface.

## Relevant verified method evidence in classes6.dex

- `uploadWatchFace` invokes `setWatchFaceType` then `prepareSendWatchFaceData`.
- `prepareSendWatchFaceData` invokes `WriteCommandToBLE.writeCharaBle5`.
- `setImageWatchFace` obtains an `ImageWatchFaceConfig` and invokes `getSetImageWatchFaceCmd` and `startSendDataSegments`.
- `applyWatchFace` constructs a separate BLE command for selecting a previously known watchface ID/version.
- `getWatchFaceParams` queries device watchface parameters via BLE.

These are Android-app code paths and are not a verified match to the connected iHunt watch's runtime chipset.

## Acceptance criteria

A finished output requires a correct image layout, exact existing dynamic field bindings, a validated data-transfer path and a working rollback. CRC32 alone is insufficient proof of installability. No further user-driven cache checks are needed to continue *offline* research.
