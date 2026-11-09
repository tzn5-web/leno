# Watch6T HOLO V3 — installable cache-stage candidate

Date: 2026-11-09. Target: iHunt Watch6T-D123, reported firmware RB235DCEV004137.
Branch: `watch6t-gloryfit-analysis`.

## What has been implemented now
1. An **offline BIN constructor** used the owner's `D1898001.bin` (343,944 bytes) and the third HOLO concept as the visual reference. The generated dial keeps all 22 original metadata/record definitions and replaces **only** two 240×240 RGB565 images (preview and live background), recalculating CRC32.
2. Local checks passed: exact file length, header payload length, CRC32, record table byte identity, unchanged other 20 image payloads, SHA256 of untouched original versus candidate.
3. A **Windows cache staging / rollback script** (`Stage-HOLO-V3.ps1`) validates the exact current cache file SHA256; creates a verified, timestamped backup; pushes the candidate into a temporary cache filename; checks its SHA256; atomically renames the file to `D1898001.bin`; verifies the final hash. It refuses to overwrite unknown cache content. No OTA/firmware/BLE commands are emitted by the script.
4. Private conversation package: `Watch6T_HOLO_V3_INSTALEAZA.zip`, containing installer launchers, original backup, new BIN, original-source dependent Python builder, image and integrity manifest. **Do not commit proprietary APK, BIN, or face artwork to public GitHub.**

Original SHA256: `b299263efe3a1d60bd76d1e93f6541980128bdd5975699a66d28e217ba6214c1`
V3 candidate SHA256: `f0bd882256f7775b9c1373217d132b483ef171b44236f2ad5d8390349411b1b0`

## How the installed owner's app is expected to be used
1. Extract the private ZIP on Windows, connect the already-authorized Xiaomi USB device.
2. Close any currently running watchface synchronization screen in GloryFit.
3. Run `START_INSTALEAZA.cmd`. It writes **only** to `/sdcard/Android/data/com.yc.gloryfit/files/D1898001.bin` after ensuring source hash matches.
4. Open GloryFit > Device > Watch face settings > My faces, choose the **same previously downloaded face associated with this BIN**, and tap Sync. Do not use Firmware upgrade.
5. `RESTAUREAZA_ORIGINAL.cmd` writes back the verified original, after which sync the stock face.

The cache-swap procedure is described for other GloryFit-compatible watches in [wfeditormk66](https://github.com/janaboy74/wfeditormk66) but **has not been proven on iHunt Watch6T or this particular firmware**. The app might download the original again or ignore the replaced cache. The cache file's ID has not been definitively matched to a specific face in the app's UI; picking a different face will not load the candidate. The staged BIN is **not the system firmware**, and no method for direct device flashing is supplied.

## Limits
- The V3 face is a *stylistically adapted* HOLO dashboard, not a pixel-identical reproduction of the high-resolution concept at 240×240.
- Existing dynamic slots remain, but the original source file's live data semantics and actual runtime rendering have not been measured on the iHunt Watch6T.
- Modifying the background/preview **does not add new live HR, SpO₂, weather or step indicators**. Only whatever the stock face firmware is already configured to render can update. The full fantasy HOLO artwork cannot be made functionally exact by replacing backgrounds alone.
- No hardware installation or successful Bluetooth sync has been observed. Only local structural validation is confirmed.

## Next technical research, no redundant ADB audits
Trace the exact bin cache selection and corresponding Gallery UI entity inside GloryFit's Android code. A matching watch model/firmware must be established before claiming universal compatibility, and a successful dial sync must be observed before calling the candidate verified as installed.
