# Watch6T GloryFit: dynamic dial prototype and upload code audit

Date: 2026-11-09. Source: user-provided installed `com.yc.gloryfit` APK and dial resources. The private APK, proprietary art, device metadata, and DEX are **not committed**.

## Prototype implemented

The `Build-HOLO.py` script derives a 240 × 240 candidate from the user's bundled `dial_1_circle_240x240` template and their chosen HOLO source image. It retains the factory layers for hour/minute, day/month/weekday, five digit positions for steps, 11 progress frames and five battery states. A 240 × 240 simulation preview and two ZIP path layouts were produced locally. All original PNG dimension tuples were preserved and both ZIPs passed zip CRC checks.

The generated ZIPs are **not verified as accepted by GloryFit or by firmware**. The central heart-rate, SpO₂ and weather readouts are explicitly non-live placeholders in this iteration.

## Read-only DEX call-flow evidence

A targeted Dalvik method-index and code-item inspection of `classes6.dex` identified:

| Method | Direct outgoing call / behavior |
|---|---|
| `ActsDialCommandUtil.uploadWatchFace()` | `setWatchFaceType()` → `prepareSendWatchFaceData()` |
| `ActsDialCommandUtil.prepareSendWatchFaceData()` | `WriteCommandToBLE.getInstance()` → `writeCharaBle5()` |
| `ActsDialCommandUtil.setImageWatchFace()` | `getSetImageWatchFaceCmd()` → `startSendDataSegments()` |
| `ActsDialCommandUtil.startSendDataSegments()` | `sendDataSegments()` |
| `ActsDialCommandUtil.getWatchFaceParams()` | `WriteCommandToBLE.writeCharaBle5()` |

This establishes **two distinct upload pathways** in this APK: the online dial path and the photo/image watch-face path. It does **not** yet prove which accepts custom layered `DialCustom` ZIPs, nor the exact framing/confirmation/recovery procedure.

Tools: `dex_methods.py`, `inspect_dex_flow.py`. They are read-only and require the user's own locally extracted APK.

## Safety gates before device installation

1. Confirm the current watchface, supported face parameters and slot/state from a read-only device exchange.
2. Prove whether the layered ZIP is compiled into `.bin` or sent as images by the actual device-specific path.
3. Verify the replacement does not exceed reported `dialMaxDataSize` or violate required CRC, transport chunks, permissions or version constraints.
4. Preserve a return path to a known-good installed original before any experimental write.

**Do not use the firmware update screen to send the HOLO ZIP or any modified binary.**
