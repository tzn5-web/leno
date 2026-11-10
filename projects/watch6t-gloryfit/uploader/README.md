# Watch6T native HOLO BLE uploader — V1

## IMPORTANT — upload halted after real 26 02 timeout (2026-11-10)

The user's last actual Watch6T run reached the 26 02 prepare stage, then returned an empty BLOCKED message. It did **not** log a single 27 data section. The custom-face slot may have been erased. **DO NOT repeat the install launcher.** `install` is now explicitly blocked BEFORE sending another 26 02, pending confirmation of the proper device ready/ACK sequence.

Reading the user's actual GloryFit classes6.dex reveals **26 01 and 26 02 go to 33F1; 27 data sections go to 34F1**. The previous uploader used 33F1 for all sections and would have been wrong even if 26 02 succeeded. Current code discovers 34F1, validates its properties and implements `send_section` on the correct characteristic. This route is not yet physically tested.

Read-only discovery without clearing the slot:

    call PREGATESTE.cmd
    py -3 watch6t_ble.py probe --name Watch6T

This does not upload a BIN or send 26 02. The current Windows bundle's install script still displays a warning/prompt, but its downloaded Python code refuses to perform another write; use `probe` instead.

See [BLE-DEX-INVESTIGATION-2026-11-10.md](BLE-DEX-INVESTIGATION-2026-11-10.md).


**Status:** the uploader is implemented. The native BIN parser and simulated 26/27 transfer sequence have tests. It has **NOT** been verified against a physical iHunt Watch6T (firmware RB235DCEV004137). This does NOT install a PNG wallpaper, and it does NOT use the watch firmware/OTA channel.

## Răspunsul real al Watch6T — 10 noiembrie 2026

Ceasul a răspuns la interogarea 26 01 cu cei 15 octeți:

    26 01 0002E569 00F0 00F0 00 00100000

Decodificare: identificator 189801, ecran 240×240, tip ecran 0, dimensiune maximă 1.048.576 octeți. Câmpurile de compatibilitate și unghi sunt opționale și lipsesc din acest răspuns. Parserul le păstrează ca None, fără să respingă mesajul.

Prima încercare s-a oprit înainte de comanda 26 02: nu a șters slotul și nu a trimis BIN-ul.

Bluetooth-ul PC-ului a raportat ATT MTU 247, dar dimensiunea maximă GATT write-without-response este 20. Codul nou limitează pachetele la maximum 20 de octeți. La 16 octeți utili și 3 octeți antet, HOLO V6 (421.238 octeți) cere 26.328 fragmente. Confirmările de transfer nu au fost testate încă pe ceas.

Important: pachetul privat existent include PREGATESTE.cmd, care descarcă automat versiunile curente protocol.py și watch6t_ble.py din această ramură. Nu este nevoie de alt ZIP pentru corectarea parserului.

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
## Update: native BLE write-with-response on Watch6T (2026-11-10)

The second owner run passed the 15-byte dial capability response and rejected upload before 26 02 because `33F1` advertises `write` (with-response) but not `write-without-response`.

This software guard was wrong for this hardware: read-only 26 01 had already succeeded over the same GATT write-with-response transport.

Uploader revision:

- Allows `write` / with-response mode; each GATT fragment is acknowledged at the ATT layer.
- Uses 16 payload bytes + a 3-byte 27/index header, which stays below the conservative 20-byte write limit even with MTU 247.
- Checks `26 03 04` block ACKs, and requires `26 03 00` (not a generic 26 03) for actual upload success.
- Preserves the CRC, size, 240×240 and face-ID checks before preparing the custom dial slot.
- Added a simulated with-response upload test. CI success and hardware upload remain unverified.

To load this fix, run the EXISTING Windows `2_INSTALEAZA_HOLO_BLE_EXPERIMENTAL.cmd`: `PREGATESTE.cmd` always retrieves the latest `watch6t_ble.py` and `protocol.py` from the GitHub branch.

**Risk:** the next run may actually reach destructive `26 02`. A failed or interrupted transfer can leave the custom face slot empty. The presence of the original BIN in the archive is not proof of hardware recovery. Only proceed if willing to accept that risk.

## Read-only Watch6T follow-up — FF FF FF FF after interrupted preparation

2026-11-10: the user ran `probe` and supplied:

    GloryFit BIN data 34F1: properties=['read', 'write-without-response']; max_write=244; mode=without-response
    BLE DIAL NOTIFY: 2601ffffffff00f000f00000100000

Compared with the earlier `26010002e56900f000f00000100000`, only the 4-byte dial ID changed, from `0002E569` (189801) to `FFFFFFFF` (4294967295); the 240×240 resolution, screen type, and 1 MB capacity are unchanged.

The change happened after the previous program attempted `26 02` and then stopped without delivering any `27` data fragments. `FFFFFFFF` plausibly indicates an unassigned/erased custom slot, **but its exact device-specific semantic remains unverified**. The source does not prove that the watch is damaged or that a factory face was deleted.

The uploader now records this slot state as `unassigned-or-erased` and refuses all upload attempts before another `26 02`. It can continue doing read-only capability probes, but rerunning them provides no new installation path.

Next actual recovery step: if the watch face is missing or blank, use official GloryFit to install a known-good **official** watch face and confirm it works. This is recovery only, not the final HOLO design, and must not use the Firmware Upgrade / OTA page. To implement HOLO upload independently, the developer must reproduce the vendor's device-specific prepare ACK/flow-control sequence from actual application traffic rather than guessing the meaning of `FFFFFFFF`.
