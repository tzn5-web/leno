# Phaser360 SOF Windows Port

Integrated Windows audio port for Lenovo/Chromebook Phaser360
(Gemini Lake, Intel 8086:3198).

## Current delivered path

```
SklHDAudBus / CSAUDIO\ADSP
        ↓
P360SofAudio
        ↓
official SOF 1.9.3 APL/GLK firmware + IPC3
        ↓
HOST playback + SSP1
        ↓
P360Max98357Safe / MAX98357A
        ↓
PortCls / WaveRT
        ↓
Windows Audio Engine / WASAPI shared
        ↓
internal speakers
```

The current installable driver exposes **internal-speaker render only**.

Known board routing from Linux/ChromeOS:

- SSP1 → MAX98357A → internal speakers
- SSP2 → DA7219 → headset codec on the audited Phaser360 hardware
- DMIC0 → internal microphones
- 48 kHz speaker stream target

SSP2 and DMIC are board facts, not prerequisites for the speaker endpoint.
The NHLT gate therefore requires a valid table plus the matching SSP1 render
endpoint only. Headset and microphone support must be implemented and validated
separately before those endpoints are exposed.

## Firmware

The full-install package pins the official Intel-signed SOF 1.9.3 image from:

`thesofproject/sof-bin/v1.9.x/sof-v1.9.3/intel-signed/sof-apl.ri`

Gemini Lake resolves `sof-glk.ri` to the Apollo Lake payload in this SOF
generation. The pinned image is 287488 bytes with SHA-256:

`40029b5a05665f19a492ef00b8c0a24c42e90d7c00fc57146e07947fd1407d5c`

The earlier custom diagnostic-v2 firmware is no longer packaged.

## Windows dependencies

The current driver deliberately consumes CoolStar's
`GUID_ADSP_BUS_INTERFACE` from a healthy `SklHDAudBus` binding on
`PCI\VEN_8086&DEV_3198`. The full installer verifies that prerequisite before
binding P360SofAudio.

MAX98357A obtains SDMODE from its ACPI GPIO connection resource. A healthy
P360Max98357Safe PnP start proves that the Resource Hub GPIO target opened
successfully; the installer records this as `AMP_GPIO_RESOURCE=PASS_BY_DEVICE_START`.

## Safety

MAX98357A is forced muted in D0 until a generation-tagged speaker START callback
is received. STOP/D0Exit/ReleaseHardware force SDMODE low.

The install path does not play a test tone and does not advertise event-driven
WaveRT. It validates the Windows shared-mode endpoint without starting playback.
