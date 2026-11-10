# Watch6T native HOLO BLE uploader — V1

**Status:** the uploader is implemented. The native BIN parser and simulated 26/27 transfer sequence have tests. It has **NOT** been verified against a physical iHunt Watch6T (firmware RB235DCEV004137). This does NOT install a PNG wallpaper, and it does NOT use the watch firmware/OTA channel.

## Features

- Finds an iHunt Watch6T BLE peripheral, with explicit selection for multiple matches.
- Requires standard GloryFit service 55FF, write 33F1, notify 33F2.
- Subscribes to notifications before sending commands.
- Sends the READ-ONLY 26 01 capabilities query to determine native dial resolution, storage size and compatibility level.
- Validates the native D1898001.bin file format: 24-byte header, element table, 240x240 pixels, CRC32 and complete size.
- Only after explicit consent and acceptance gates: sends RK/classic 26 02 prepare/erase, 27 indexed fragments, checks 26 03 04 per-block acknowledgment, 26 03 03 resumption and 26 03 00 completion.
- Never addresses OTA/DFU characteristics.
- Rejects JX/Actions protocol, missing acknowledgments, unsupported sizes, corrupted file or wrong face ID.

## Safety

On related GloryFit watches, 26 02 can erase the custom dial slot before transferring new bytes. If interrupted, a blank custom face is possible until the original can be re-uploaded. The private HOLO V6 archive contains the original BIN, but actual recovery behavior on this particular watch is not known.

Do not use the watch's "Upgrade de firmware" screen and do not rerun the previous V3–V6 phone cache scripts.

## Windows instructions

Use GitHub Actions to build a portable Watch6T-BLE.exe, or Python 3.11+ and Bleak:

    py -m pip install -r requirements.txt
    py watch6t_ble.py scan --all

Close GloryFit or temporarily turn the PHONE Bluetooth off, because the watch may reject simultaneous connections. Keep PC Bluetooth on.

Installation command with automatic capability gate:

    Watch6T-BLE.exe install --name "iHunt Watch6T" --file "D1898001_HOLO_V6_BETA_UNTESTED.bin" --confirm ERASE-DIAL-SLOT

The tool first performs 26 01 itself, checks resolution, supported slot capacity, GATT services and file integrity, and refuses to issue 26 02 if these checks fail.

For discovery-only: Watch6T-BLE.exe scan --all
For capabilities-only: Watch6T-BLE.exe probe --name "iHunt Watch6T"
If the watch advertises with another name, use --address from scan.

This is a **native BLE uploader running on the PC's Bluetooth adapter**. It does not use ADB, a phone-side cache or the firmware-update menu.

## Tests

    py -m unittest discover -s tests -v

If a private D1898001_HOLO_V6_BETA_UNTESTED.bin is placed next to the code, test discovery includes a real file-integrity check. No actual BLE hardware write is performed by tests.

## Research references

- User-supplied com.yc.gloryfit APK, native DEX methods ActsDialCommandUtil, WriteCommandToBLE; see ../UPLOAD-FLOW-2026-11-09.md
- RK dial protocol research: https://github.com/davidbuzz/RyzeWaveWatch/blob/main/docs/watch_features_research.md
- BIN data format: https://github.com/janaboy74/wfeditormk66

These references concern related GloryFit devices and are **not proof of compatibility** with the user's watch. APK sources and proprietary art must remain private.