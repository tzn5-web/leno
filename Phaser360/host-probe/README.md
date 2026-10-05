# PHASER360 ADSP interface probe

Binds only to `CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198` created by the existing functioning `SklHDAudBus` parent.

This **is not an audio driver**. It is a minimal KMDF diagnostic function driver which queries `GUID_ADSP_BUS_INTERFACE` version 1 and exposes only a read-only IOCTL for querying the interface status, controller ID and presence of the GetResources and RegisterInterrupt methods. It does **not** call those methods, register an ISR, start firmware, send IPC, touch MMIO, enable speakers or render audio.

No alteration to the already-working bus is needed. Test-signing is required for loading, and installation should happen only after reviewing the signed artifact.

The result `BUS_INTERFACE_OK=TRUE` will prove that a function driver can bind to the DSP child and obtain the intended ABI. It **cannot** prove interrupt delivery, SOF readiness, or working sound.

WARNING: This probe claims the DSP PnP child. Before installing a production SOF host, uninstall this probe and verify the child has returned to Code 28 (or binds to the intended production host).
