# Samsung Galaxy Tab 2 GT-P5100 — porting workspace

**Status: source adaptation / preflight only. NO BOOTABLE ROM, NO FLASH.**

Target model: **GT-P5100**, 10.1-inch cellular + Wi-Fi, `espresso3g`, OMAP4430/ARMv7, 1 GiB RAM, PowerVR SGX540.

## Strategy

1. Restore the known LineageOS 14.1 (Android 7.1.2) hardware baseline using *exact pinned* upstream source revisions in `sources.lock.json`. Preserve distinct 3G device tree; never substitute `espressowifi` for `espresso3g`.
2. Run `scripts/preflight.py` and examine partition geometry, boot image format, RIL, framebuffer/SGX, audio and Wi-Fi. This checks **source consistency**, not runtime compatibility.
3. Investigate Android 8/9 ports as intermediate bootable targets. Record device logs and regressions.
4. In parallel, evaluate 2026 upstream Linux device-tree patch series for `samsung-espresso10` (includes P5100) for a **separate modern kernel track**. Kernel patches do **not** mean Android HAL, SGX GPU or modem support is ready.
5. Only after reproducing older working boot, attempt Android 11 and then Android 14 bring-up; 15/16 are contingent. Unverified product targets must not be described as working.

## Sources

- https://github.com/LineageOS/android_device_samsung_espresso3g/tree/cm-14.1
- https://github.com/LineageOS/android_device_samsung_espressowifi/tree/cm-14.1
- https://github.com/LineageOS/android_kernel_ti_omap4/tree/cm-14.1
- https://github.com/LineageOS/android_hardware_ti_omap4/tree/cm-14.1
- https://www.spinics.net/lists/devicetree/msg900356.html — March 2026 kernel patch series (review status must be checked before use)

Note: the 3G tree deliberately inherits common files from **espressowifi**. Cloning `espressowifi` does not change the output target to a Wi-Fi-only model.

## Local usage (Linux/WSL)

```bash
bash projects/galaxy-tab2-p5100/scripts/bootstrap-sources.sh "$HOME/gt-p5100-legacy"
python3 projects/galaxy-tab2-p5100/scripts/preflight.py "$HOME/gt-p5100-legacy"
```

These commands clone only four device/kernel/hardware repos, **not** the whole Android platform. Full AOSP/Lineage source checkout, proprietary blobs, build/boot tests and device backup remain future steps.

**Safety:** No automatic flashing, partition changes, unlocking, wipe, or modification of a connected tablet. `FLASH_ALLOWED=NO` irrespective of preflight outcome. Back up EFS/modem and partitions before any later experiments. Exact model must be confirmed on the tablet before release.
