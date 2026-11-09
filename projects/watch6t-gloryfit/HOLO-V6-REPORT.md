# HOLO V6: corrected native GloryFit BIN rebuild (9 November 2026)

**Target device:** iHunt Watch6T-D123, firmware shown as `RB235DCEV004137`. The selected art remains the *third* blue/cyan-green holographic concept from the user's conversation.

## Concrete changes after V5

The supplied 343,944-byte `D1898001.bin` was re-parsed against `janaboy74/wfeditormk66/src/watchface.h`. Previous V2-V5 research **incorrectly swapped per-item width and height**. Correct record layout is `type:u16 | width:u16 | ptr:u32 | height:u16 | x:u16 | y:u16 | reserved:u16 | frameCount:u8 | copyImage:u8 | dummy:u16 | four more bytes`, exactly 24 bytes per record. All small images are **row-major RGB565** in this file, not the earlier claimed column-major; row-major displays readable fonts and labels.

Using the owner's original 1254×1254 HOLO image, we rebuilt:
- Live 4-digit clock sprites (larger, crisp cyan hours and lime minutes) and a colon in the stock item classes.
- Date/weekday/month sprite families preserving original frame counts and indices.
- Battery 5-stage accents and numeric glyphs.
- HR-like and step-like numeric sprites in the original element slots (type-to-sensor binding **still inferred** from geometry, not hardware-verified).
- 16 weather icon frames recolored, and temperature-digit families.
- The original HOLO holographic person, ECG design, outer rings, and SpO2 panel visually retained.
- Unsupported **SpO2 remains blank** rather than showing a fake measured value. ECG is decorative.

The BIN builder re-serializes the 22-record table, image blocks and absolute offsets, preserving the original header's file ID, resolution, reserved data, record type IDs, frame counts and other unknown fields. Shared identical image blocks may reuse an offset. The 24-byte header length and CRC32 were regenerated.

## Verified offline

| Check | Result |
|---|---|
| Original size | 343,944 bytes |
| New file size | 421,238 bytes |
| Original 22 record type IDs | unchanged |
| Record metadata and frame counts | unchanged |
| Record pointers | within file bounds |
| Native display size | 240×240 |
| Image encoding | RGB565, big-endian, row-major |
| Original SHA256 | `b299263efe3a1d60bd76d1e93f6541980128bdd5975699a66d28e217ba6214c1` |
| Candidate SHA256 | `9af80f485d866a69f4ed954d819d3b5cf95ffc952828cc5198d1ccc4e69291cb` |
| Header declared size and CRC32 | verified |
| ZIP integrity / regression tests | PASS |
| Synchronization on physical iHunt Watch6T | **NOT TESTED** |
| Maximum watchface payload for this firmware | **UNKNOWN** |

The private package `Watch6T_HOLO_V6_CANDIDAT.zip` was prepared in this conversation. It contains the original BIN, reconstructed BIN, the full Python generator, PowerShell cache staging/restoration with SHA256 checks, standalone regression tests, preview, and original art. The proprietary binaries and user image are **not** placed in this public GitHub repository.

## Compatibility and installation

A cache replacement workflow is publicly described by `janaboy74/wfeditormk66`: GloryFit downloads a face, the user replaces the BIN in `/Android/data/com.yc.gloryfit/files`, and resynchronizes that same face.

V6's guarded Windows installer acts only on `/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin` after checking the source SHA256 and preserving a local backup. **It does not flash firmware or send BLE commands.** Resync must be initiated in GloryFit by the user, because remote BLE/device control is unavailable in this chat.

**This is not a demonstrated installed face.** This particular 421 KB candidate could exceed an unknown device-side watchface size cap or be rejected; the installed app might replace cached assets. Keep the stock BIN for rollback and do not use the Firmware upgrade menu.

References: 
- [wfeditormk66 source layout](https://github.com/janaboy74/wfeditormk66/blob/main/src/watchface.h)
- [wfeditormk66 cache replacement procedure](https://github.com/janaboy74/wfeditormk66)
