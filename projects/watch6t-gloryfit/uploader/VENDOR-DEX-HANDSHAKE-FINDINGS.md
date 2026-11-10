# GloryFit native online-dial handshake: evidence from the user's installed APK

Date: 2026-11-10. Scope: `com.yc.gloryfit`, `classes6.dex` (provided by the device owner).

This records **observed bytecode semantics**, without copying the proprietary DEX or application code into the public repository.

## Three independent bytecode findings

1. **`FFFFFFFF` does not prove a wiped custom face**. In `OnlineDialUtil.getDialNumber()`, the application checks the eight-character hex string `FFFFFFFF` and logs the Chinese message `表示当前没有显示的在线表盘` ("no online dial currently being displayed"). It returns -1 for that case. A `26 01` response containing `FFFFFFFF` is about the *currently displayed online dial*, not a reliable inspection of flash-slot health.
2. **Prepare readiness belongs to `26 02`, not the first `26 03 04`**. In `BluetoothLeService.dealWithOnlineDial()`, when the second incoming byte is 0x02 the app logs `准备开始发送表盘数据` ("preparing to start sending dial data") and emits an online-dial status callback. `26 03 04` belongs to the later per-block flow control. Actual iHunt hardware reply for the earlier `26 02` attempt remains uncaptured, so automated re-preparation is not permitted.
3. **Finishing is active, not passive**. `WriteCommandToBLE.sendOnlineDialDataFinish()` constructs the literal bytes `26 03 00` and sends them through `writeChara` (33F1) after all data sections; the watch then acknowledges final status. The old uploader waited without sending this command, guaranteeing a stall after complete data delivery if it had reached that stage.

## Verified DEX transport split

- `readDeviceOnlineDialConfiguration()` -> `26 01` on 33F1
- `prepareSendOnlineDialData()` -> `26 02` on 33F1
- `sendSectionOnlineDialData()` -> `27 + index + payload` via `writeCharaBle5Gps()` -> 34F1
- `sendOnlineDialDataFinish()` -> `26 03 00` on 33F1

The owner's physical BLE scan showed: 33F1 with-response, maximum 20 bytes; 34F1 without-response, maximum 244 bytes; ATT MTU 247. Read-only `26 01` returned 240×240 and a 1,048,576-byte face capacity.

## Code status

The uploader now has `transfer_after_vendor_ready()`, a separately testable 34F1 transfer sequence that checks 4KB flow-control status and sends a 33F1 `26 03 00` finish, then waits for the final success reply. There are simulated tests for this handshake.

**Live installation is intentionally halted before any repeated `26 02`**. The owner's previous attempt reached that command and timed out with no classified response. Sending more preparatory writes without checking the actual ready event risks clearing the custom slot.

## Next evidence

The release APK's `LogDial.i` and `LogSync.i` methods call Android's `android.util.Log.i`, so an `adb logcat` capture of **one official GloryFit watchface synchronization** may reveal the real prepare/ACK and block sequencing. Capture only those tags, redact source lines, and remove raw logs to avoid leaking health/phone data. If release logging is suppressed, Android Bluetooth HCI snoop would be the alternative, with explicit user consent.

The private `Watch6T_Captura_Protocol_GLORYFIT_V1.zip` prepared for the user contains a Windows PowerShell/ADB capture tool and a sanitizer; it does not write anything to the watch. Its two offline sanitizer tests passed on the author's runtime; it has not been executed against the owner's actual phone.

**Do not use firmware OTA/DFU to load HOLO.**
