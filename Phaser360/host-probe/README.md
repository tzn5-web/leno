# PHASER360 ADSP passive IRQ probe v2

This package upgrades the earlier read-only interface probe bound to `CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198`.

The validated v1 probe already proved:

- ADSP bus query status = 0
- controller = 0x3198
- interface version = 1
- interface size = 144
- GetResources export exists
- RegisterInterrupt/UnregisterInterrupt exports exist

v2 performs one additional operation: it calls the bus interface's `RegisterInterrupt` method with a tiny callback that only increments an atomic 64-bit counter and returns FALSE. Returning FALSE means it does not claim the shared HDA interrupt; normal parent-bus processing continues.

v2 still performs **no** GetResources call, MMIO read/write, DSP power call, firmware boot, IPC, stream operation, codec/GPIO write, endpoint creation, or audio playback.

`START_PASSIVE_IRQ_TEST.cmd` samples the counter, waits five seconds, samples again, and prints a delta. A zero delta during an idle five-second window is **not** proof of broken routing because this stage deliberately generates no DSP interrupt source. A positive delta proves that the callback path is live.

Before any future production SOF host is installed, remove this diagnostic driver with `START_ROLLBACK.cmd`.
