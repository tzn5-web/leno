# Phaser360 Gemini Lake audio bus mod

Target: Google Phaser360 / Octopus, Windows 10 x64, PCI audio controller 8086:3198.

## Root cause

The machine currently binds PCI 8086:3198 to Intel `IntcAudioBus`. That bus enumerates the DSP as:

`INTELAUDIO\DSP_VEN_8086&DEV_0222`

The CoolStar Gemini Lake bus uses the same physical PCI controller but creates a different DSP PDO:

`CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198`

and exposes `GUID_ADSP_BUS_INTERFACE` to the SOF function driver. This interface carries the mapped HDA/ADSP resources, NHLT/topology access, interrupt registration and HDA stream helpers. The old PHASER360 loader duplicated that layer and is where the previous MMIO/IRQ path failed.

## What this branch changes

The build pins CoolStar `sklhdaudbus` at commit `5477b93a3b68c474819abf2094a49d0e2d8d9799`.

The patch:
- keeps CoolStar's native Gemini Lake match `PCI\VEN_8086&DEV_3198&CC_0401`;
- labels the Gemini Lake device explicitly for Phaser360;
- adds a `Phaser360Mode=1` registry marker;
- preserves the canonical `CSAUDIO\ADSP...` DSP identity;
- adds `P360AUDIO\ADSP_GEMINILAKE` as an additional compatible ID for our own SOF host, without replacing the canonical CoolStar ID.

The bus mod does **not** boot SOF and does **not** play audio. Its job is to replace the wrong parent bus layer and expose a stable ADSP interface for the next host-driver stage.

## Expected post-install state

Parent:
- `PCI\VEN_8086&DEV_3198...`
- service: `SklHDAudBus`

DSP child:
- device/hardware ID: `CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198`
- compatible ID: `P360AUDIO\ADSP_GEMINILAKE`
- Code 28 is acceptable until the PHASER360 SOF host is installed.

The existing Intel package is exported before replacement and is not deleted from Driver Store.
