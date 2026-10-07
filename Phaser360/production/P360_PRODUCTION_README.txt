PHASER360 PRODUCTION AUDIO PACKAGE
=================================

This is the single production package for the PHASER360 Windows audio path.

Final architecture:
Windows Audio / WASAPI shared
  -> PortCls / WaveRT
  -> P360SofAudio
  -> CoolStar SklHDAudBus HDA DMA
  -> SOF HOST pipeline
  -> SSP1
  -> MAX98357A
  -> internal speakers

Hardware routing kept from the proven Linux/CoolStar model:
- SSP1 = internal speaker amplifier (MAX98357A)
- SSP2 = DA7219 codec/headset path
- DMIC remains a separate capture path

Production identity:
- one P360AudioBundle.inf
- one P360AudioBundle.cat
- one package DriverVer
- P360SofAudio.sys for CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198
- P360Max98357Safe.sys for ACPI\MX98357A
- pinned p360-f686.ri firmware

The speaker endpoint declares an explicit shared-mode OEM format:
48 kHz, stereo, PCM, 32-bit container, 16 valid bits.

P360SofAudio uses the valid WaveRT push/position model for this ADSP path.
The CoolStar ADSP child exposes GUID_ADSP_BUS_INTERFACE, not the HDAUDIO V2/V3
notification interfaces that CoolStar exposes on codec children. Therefore this
package does NOT advertise PKEY_AudioEndpoint_Supports_EventDriven_Mode. It
does not claim a notification contract the ADSP bus cannot supply.

P360_PRODUCTION_INSTALL.ps1 is the only production installer/self-healing
runner. Its normal Install mode only installs or repairs this same bundle and
never swaps to PREAUDIO, bounded-tone, diagnostic, or alternate driver
versions. It does not automatically roll back. Restore is a separate explicit
manual mode.

Final acceptance is P360_WASAPI_TEST.exe:
- unique active PHASER360 render endpoint
- IAudioClient activation
- WASAPI shared-mode format support
- shared stream initialization
- real IAudioRenderClient playback
- IAudioClock advancement

P360_WAVERT_TEST.exe is retained only as a lower-level WinMM/waveOut diagnostic.
A waveOut PASS is not final production acceptance.

The catalog is test-signed. Windows must accept the PHASER360 test certificate
and test-signed driver package on the target machine.
