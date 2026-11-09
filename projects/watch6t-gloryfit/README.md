# iHunt Watch6T / GloryFit watch-face format investigation

Target device: `iHunt Watch6T-D123`, reported firmware `RB235DCEV004137`; Android companion package `com.yc.gloryfit`.

This directory holds **original analysis tools and sanitized research notes only**. It does **not** include the proprietary GloryFit APK, decompiled code, proprietary dial artwork, device identifiers, credentials, or personal health data. Do not push recovered third-party app binaries or sources into this public repository.

## Confirmed from the user's `DialCustom_240x240_90.zip`

- ZIP: 317,178 bytes; root folder: `dial_10027_circle_240x240/`.
- 124 ZIP entries, including directory records; PNG assets and zero-length `config_WxH_XxY.txt` coordinate markers.
- Layers: `background`, `preview`, `hour2min`, `timehour1`, `timehour2`, `timemin1`, `timemin2`, `timeday1`, `timeday2`, `week`.
- The background and preview are 240 x 240 PNGs. Hour/minute numbers are 32 x 42 PNGs at declared coordinates.
- No dedicated step counter, heart rate, battery percentage, SpO2 or weather layers were found **in this particular dial archive**. Other dials may differ. This package is not evidence that the device lacks those features.
- This is not an OTA firmware file. The `DialCustom` ZIP is not proof that a custom ZIP can be installed directly, without using the official GloryFit synchronization process.

## Step 1 — pull the installed companion app (Windows)

1. Connect exactly one authorized Android phone via USB debugging. Keep its existing ADB installation at `Desktop\platform-tools\adb.exe`.
2. In CMD, run this script after downloading it (or clone the repository):

   ```cmd
   powershell -NoProfile -ExecutionPolicy Bypass -File "Collect-GloryFit.ps1"
   ```

   The script uses `adb shell pm path com.yc.gloryfit` then pulls **all** APK splits. It separately copies accessible public watchface cache files. It never roots the phone, flashes the watch, modifies the app, or uploads anything.
3. It creates `Desktop\GloryFit_APK_<date>.zip`. For private analysis, upload that ZIP directly to this chat rather than to a public GitHub repository.

This is the [Android-recommended](https://developer.android.com/tools/adb) way to find installed package paths. The APK could consist of `base.apk` plus split APKs.

## Step 2 — scan the APK/ZIP assets

On a machine with Python 3 installed:

```sh
python Inspect-Watchfaces.py DialCustom_240x240_90.zip --output report --extract
python Inspect-Watchfaces.py "path/to/apks" --output apk_report --extract
```

Inspect `watchface_related` file paths, assets, resources and any downloaded dial archives. APK files are ZIP containers, but Java/Dalvik program logic in `classes*.dex` needs an additional decompiler (e.g. [JADX](https://github.com/skylot/jadx)) for code-level tracing. The script does **not** pretend to reconstruct full Java sources from DEX.

## Step 3 — tracing the dial pipeline

Once the actual installed APK is available, locate code references to `DialCustom`, `com.yc.gloryfit`, dial asset paths, sync methods, ZIP unpacking, image scaling and BLE commands. Distinguish cloud-fetched artwork from bundled resources. Validate any rebuilt dial against a **known-working backup** before considering synchronization, and do not write/flash the device until compatibility is established.

## Update — APK acquired and inspected (2026-11-09)

The user provided \`GloryFit_APK_20261109_170204.zip\`. Local analysis confirmed five APK splits, **two built-in 240×240 dial templates**, and one valid 240×240 RGB565 binary watchface with **22 element records and a verified CRC32**. Its image payloads have been decoded.

Detailed report: [FINDINGS-2026-11-09.md](FINDINGS-2026-11-09.md).  
Read-only analyzer: [Analyze-GloryFit.py](Analyze-GloryFit.py).

**Status:** APK package and dial assets analyzed; cached .bin format partially decoded. Full JADX-level code decompilation, verified BLE upload route, and safe installation of a modified HOLO dial are **not yet complete**. Proprietary APK and proprietary watchface images stay out of this public repository.