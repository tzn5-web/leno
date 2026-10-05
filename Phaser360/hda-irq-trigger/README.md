# PHASER360 HDA read-only IRQ trigger

Purpose: prove or disprove the physical/parent ISR path without booting the DSP or rendering audio.

The driver binds only to the Intel HDA codec child:

`HDAUDIO\FUNC_01&VEN_8086&DEV_280D`

Its single IOCTL issues exactly one fixed HDA verb: `GET_PARAMETER(Node 0, Vendor ID)`. No user-supplied verb is accepted. This operation is read-only at the codec protocol level.

`RUN_ACTIVE_IRQ_TEST.cmd` reads the ADSP passive IRQ counter, issues the HDA vendor-ID read, then reads the counter again. CoolStar SklHDAudBus invokes the ADSP callback at the beginning of `hda_interrupt()`, while CORB/RIRB completion is also handled through that ISR/DPC path.

A successful HDA response plus `IRQ_DELTA > 0` therefore proves that the parent interrupt path is alive.

This package does not boot SOF, touch DSP MMIO, send IPC, allocate DMA streams, create endpoints or play audio. If the graphics codec is disconnected, the parent may return STATUS_DEVICE_NOT_CONNECTED and the result is inconclusive rather than failed.
