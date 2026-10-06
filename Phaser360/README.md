# Phaser360 SOF Windows Port

Integrated Windows audio port for Lenovo/Chromebook Phaser360 (Gemini Lake, Intel 8086:3198).

This branch is isolated from the existing iOS project on `main`.

## Target stack

```
SklHDAudBus / CSAUDIO\ADSP
        ↓
P360 GLK SOF host
        ↓
SOF firmware + IPC3
        ↓
Phaser360 topology
        ↓
PortCls / WaveRT
        ↓
DA7219 / MAX98357A / DMIC
        ↓
Windows Audio Engine
```

Known board routing:

- SSP1 → MAX98357A → internal speakers
- SSP2 → DA7219 → headset
- DMIC0 → internal microphones
- initial stream target: 48 kHz

## Safety

The internal speaker path is disabled by default.

Runtime progression:

`DISCOVER → RESOURCES_OK → SOF_BOOTING → SOF_READY → IPC_READY → TOPOLOGY_READY → AUDIO_CORE_READY → HEADPHONE_READY → SPEAKER_ARMED`

Any invariant failure returns to a fail-closed state. No automatic BIOS/ACPI modification is permitted.
