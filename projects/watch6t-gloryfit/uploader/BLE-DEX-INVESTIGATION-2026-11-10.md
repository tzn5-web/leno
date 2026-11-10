# Watch6T BLE upload investigation — 2026-11-10

Scope: user-provided installed GloryFit Android package `com.yc.gloryfit`, `classes6.dex`. No proprietary APK/code is uploaded to GitHub.

## Confirmed from actual application bytecode

| Function | APK method | Characteristic | Packet |
|---|---|---|---|
| Read capacity | `WriteCommandToBLE.readDeviceOnlineDialConfiguration` | standard `writeChara` -> `33F1` | `26 01` |
| Prepare/erase slot | `WriteCommandToBLE.prepareSendOnlineDialData` | standard `writeChara` -> `33F1` | **`26 02` exactly (2 bytes)** |
| Send indexed face section | `WriteCommandToBLE.sendSectionOnlineDialData` | `writeCharaBle5Gps` -> **`34F1`** | `27` indexed chunks |
| Finish | `WriteCommandToBLE.sendOnlineDialDataFinish` | standard `writeChara` -> `33F1` | finish command family |

The `writeCharaBle5Gps` method loads the literal UUID `000034f1-0000-1000-8000-00805f9b34fb`, then invokes `writeCharaBle5`. The `prepareSendOnlineDialData` method builds a 2-byte array containing 0x26 and 0x02, passes it to `writeChara`. These were inspected from the user's actual DEX code-item instructions, **not extrapolated from another GloryFit watch**.

The previous V1 uploader routed `27` packets to `33F1`, which is incorrect. GitHub's current implementation has an isolated `send_section()` that uses `34F1` and validates the channel's GATT properties and individual packet size. Legacy `command()` permits only `26 01` / `26 02` on `33F1`.

## Actual physical trial

- BLE device: iHunt Watch6T-D123, reported firmware `RB235DCEV004137`
- `26 01` reply: `26010002e56900f000f00000100000` (15 bytes)
- Native face ID: 189801, resolution 240x240, max size 1,048,576 bytes
- `33F1` was usable for write-with-response, with actual Windows Bleak max write 20
- V6 native face size: 421,238 bytes, 22 image type records, CRC32 validated offline
- User's last run printed `Starting transfer...` then an empty `BLOCKED:`
- **No 27 section transmission or successful device completion was logged**. The earlier `BLOCKED:` was empty because `asyncio.wait_for` propagated a blank `TimeoutError`; it is still unknown whether that occurred during the `26 02` GATT write or waiting for a readiness notification. `26 02` may already have erased or prepared the custom dial slot.

The previous program required `26 03 04` or `26 02 00` to proceed past preparation. It is not yet shown that this particular device emits exactly that immediate acknowledgement. Therefore **there is no justification to auto-retry 26 02**.

## Current safety behavior

- Real-time stages and timeouts now have nonempty error messages.
- Read-only `probe` queries `26 01` and displays both `33F1` and `34F1` existence/properties (plus optional `34F2` notifications).
- **Actual uploading is deliberately blocked BEFORE another 26 02** with explicit `PREPARE UNSAFE`. No new firmware/OTA calls.
- Bytecode-derived `34F1` data channel is implemented, but dormant until the physical handshake is established.
- One remaining safe observation, if wanted, is the uploader's `probe` mode (no slot erase, no BIN upload) to see the actual `34F1` properties.
- To recover a blank/custom slot, use stock GloryFit to select an official original dial, **not** the firmware-update menu.

The native GlorFit protocol likely needs vendor-specific transfer pacing, characteristic properties and ready/flow control. The BIN's valid CRC is only offline proof, not physical acceptance.

Code: `watch6t_ble.py`, `protocol.py`, `tests/test_ble.py`.
