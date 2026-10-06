# Phaser360 port strategy

## Decision

Do not reimplement the whole Linux audio stack and do not continue the earlier
one-off Windows probe architecture.

The integrated driver is a thin translation layer:

```
CoolStar sklhdaudbus
  ├─ owns HDA controller / stream descriptors
  ├─ exposes ADSP BAR + NHLT + PCI config
  ├─ allocates render/capture streams
  └─ dispatches DSP interrupt callback
          │
          ▼
P360 SOF host
  ├─ GLK ROM boot state machine (from audited B4 + Linux SOF behavior)
  ├─ SOF IPC3 mailbox/doorbell transport
  ├─ fixed Phaser360 topology first
  └─ fail-closed lifecycle
          │
          ▼
P360 PortCls / WaveRT
  ├─ headphone render first (SSP2 / DA7219)
  ├─ headset mic / DMIC
  └─ internal speaker last (SSP1 / MAX98357A)
```

## What B4 contributes

Keep:
- firmware image validation;
- GLK/APL ROM boot sequencing;
- FW_READY validation;
- monotonic boot epochs;
- IPC generation/timeout poisoning;
- IRQ capture/dispatch discipline;
- rollback/quarantine rules.

Replace:
- direct ownership of HDA playback stream descriptors in `p360_hda_dma.c`.

Reason:
the pinned CoolStar ADSP interface already provides
`GetRenderStream`, `GetCaptureStream`, `PrepareDSP`, `CleanupDSP`,
`TriggerDSP`, `StreamPosition` and `FreeStream`.

This removes duplicate HDA stream ownership from the P360 driver.

## Pinned CoolStar ABI

Reference commit:

`5477b93a3b68c474819abf2094a49d0e2d8d9799`

Interface:
- GUID: `752A2CAE-3455-4D18-A184-8B34B22632CE`
- Version: 1
- x64 size: 144 bytes
- controller: Gemini Lake `0x3198`

Unknown interface versions are rejected. There is no best-effort ABI guessing.

## Board profile

Initial driver is intentionally Phaser360-specific:

- PCI: Intel `8086:3198`
- 48 kHz
- SSP1 -> MAX98357A
- SSP2 -> DA7219
- DMIC0
- NHLT must prove SSP1 render, SSP2 render/capture and DMIC capture.

A generic `.tplg` parser is deferred until real audio is stable.

## Speaker policy

Internal speaker is compile-time disabled initially.

The first physical playback target is DA7219/headphones. Speaker enable requires:
1. exact hardware identity;
2. valid NHLT;
3. SOF FW_READY;
4. healthy IPC3;
5. instantiated topology;
6. working WaveRT audio core;
7. proved headphone stream;
8. explicit speaker policy enable.

Any failure returns to fail-closed state.
