PHASER360 PRODUCTION AUDIO PACKAGE
=================================

This is the single installable production package for the PHASER360 Windows
internal-speaker path.

FINAL ARCHITECTURE
------------------
Windows Audio / WASAPI shared
  -> PortCls / WaveRT
  -> P360SofAudio
  -> CoolStar SklHDAudBus HDA DMA
  -> SOF HOST pipeline
  -> SSP1
  -> MAX98357A
  -> internal speakers

The hardware routing follows the Linux/CoolStar machine model:
- SSP1 = internal speaker amplifier (MAX98357A)
- SSP2 = DA7219 codec/headset path
- DMIC = separate capture path

DA7219 is not a dependency of the SSP1 internal-speaker render path.

PRODUCTION IDENTITY
-------------------
The ZIP contains one installable driver package:
- P360AudioBundle.inf
- P360AudioBundle.cat
- one DriverVer for the combined production package
- P360SofAudio.sys for CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198
- P360Max98357Safe.sys for ACPI\MX98357A
- pinned p360-f686.ri firmware

PREAUDIO, bounded-tone and alternate P360SofAudio driver versions are not
shipped as installable production variants. They may still be compiled inside
CI only as source regressions.

WINDOWS AUDIO FORMAT CONTRACT
-----------------------------
The endpoint is classified as KSNODETYPE_SPEAKER.

PKEY_AudioEngine_OEMFormat declares the manufacturer default:
48 kHz, stereo, PCM, 32-bit container, 16 valid bits.

PKEY_AudioEngine_DeviceFormat is the active shared-mode device format and is
what the final acceptance tool requires to match that exact production format.

IAudioClient::GetMixFormat is NOT treated as the hardware/device format. It is
the Windows Audio Engine internal shared-mode processing format and may be
floating-point. P360_WASAPI_TEST.exe records it for diagnosis but does not
incorrectly require it to be 32-container/16-valid PCM.

If DeviceFormat is stale or was changed previously, the production self-healer
uses IAudioEndpointFormatControl::ResetToDefault(0), then restarts the Windows
audio services before retrying the no-sound preflight. This resets the endpoint
back to the OEM production default through the Windows audio API rather than
patching endpoint registry state by hand.

WAVERT MODE
-----------
P360SofAudio uses WaveRT push/position polling on this ADSP path. The CoolStar
ADSP child exposes GUID_ADSP_BUS_INTERFACE, not the HDAUDIO V2/V3 notification
interfaces published on codec children. Therefore the package deliberately
does NOT advertise PKEY_AudioEndpoint_Supports_EventDriven_Mode.

INSTALL / SELF-HEAL
-------------------
P360_PRODUCTION_INSTALL.ps1 is the only production installer/self-healing
runner.

Normal Install mode:
1. validates hashes, version, provider, INF format contract and payload;
2. saves the original driver state once for explicit manual restore;
3. installs the same combined production INF;
4. requires healthy P360SofAudio and P360Max98357Safe bindings;
5. removes stale PHASER360 Project packages only after the current production
   binding is proved healthy;
6. performs repair rounds using only the same production package;
7. runs WASAPI preflight without starting audio;
8. performs exactly one physical WASAPI speaker playback attempt after all
   preflight repair has passed.

There is no automatic rollback and no alternate-driver swap. If the single
physical playback attempt fails, production remains installed for diagnosis and
the runner does not automatically replay audio.

Restore is an explicit manual mode through RESTORE_P360_PRODUCTION.cmd.

FINAL ACCEPTANCE
----------------
P360_WASAPI_TEST.exe is the final acceptance path. It requires:
- exactly one active PHASER360 render endpoint;
- exact OEMFormat = 48k/stereo/PCM/32-container/16-valid;
- exact DeviceFormat = 48k/stereo/PCM/32-container/16-valid;
- IAudioClient activation;
- expected format accepted in AUDCLNT_SHAREMODE_SHARED;
- successful shared-stream initialization;
- real IAudioRenderClient playback;
- IAudioClock advancement after Start.

The physical test is 997 Hz for 2000 ms at less than 0.5 percent amplitude.

P360_WAVERT_TEST.exe is retained only as a lower-level WinMM/waveOut
diagnostic. waveOut success is never final production acceptance.

BOOT0000
--------
ACPI\BOOT0000 is the coreboot table/debug ACPI device. Code 28 on BOOT0000 is
reported in the result log as NOT_AUDIO_BLOCKER=YES. It is not part of the
P360 speaker dependency chain and is not used as an audio readiness gate.

SIGNING
-------
The CI artifact is test-signed. Windows must accept the PHASER360 test
certificate and test-signed package on the target machine.
