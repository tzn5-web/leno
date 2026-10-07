PHASER360 FULL AUDIO DRIVER
===========================

Run INSTALL_PHASER360_AUDIO.cmd. This is the only installation entry point.

The package installs the complete internal-speaker chain:
  SklHDAudBus
  -> CSAUDIO ADSP
  -> P360SofAudio
  -> SOF firmware / IPC3 host playback
  -> SSP1
  -> P360Max98357Safe
  -> MAX98357A
  -> PortCls / WaveRT
  -> Windows Audio speaker endpoint

FULL INSTALL / REPAIR
---------------------
The installer:
- validates the signed INF/CAT, binaries and pinned firmware;
- saves the original ADSP and MAX98357A drivers once for explicit restore;
- imports the package test certificate;
- stages the single combined INF;
- force-binds that exact INF to both Phaser360 hardware IDs through
  UpdateDriverForPlugAndPlayDevices + INSTALLFLAG_FORCE, so Windows driver
  ranking cannot leave an older CoolStar/P360 driver selected;
- verifies both ADSP and MAX98357A are healthy, use the expected services and
  provider, and are on the same package version;
- restarts Windows Audio;
- verifies the PHASER360 WASAPI shared endpoint without starting playback;
- repairs a stale endpoint format with
  IAudioEndpointFormatControl::ResetToDefault(0);
- repeats only installation/repair/preflight operations;
- removes stale PHASER360 Project packages only after the complete active stack
  and Windows Audio endpoint are healthy.

The installer does not use waveOut and does not start a physical speaker tone.
Its job is to leave the complete driver stack installed and the Windows Audio
endpoint ready for normal applications.

WINDOWS AUDIO FORMAT
--------------------
PKEY_AudioEngine_OEMFormat defines the endpoint manufacturer default:
48 kHz, stereo PCM, 32-bit container, 16 valid bits.

PKEY_AudioEngine_DeviceFormat is checked as the active shared-mode device
format. GetMixFormat is only the Windows Audio Engine internal processing
format and may be floating-point.

The driver does not advertise event-driven WaveRT because the Phaser360 ADSP
child exposes CoolStar GUID_ADSP_BUS_INTERFACE rather than the HDAUDIO
notification interfaces exposed on codec children. The current driver uses
WaveRT position polling.

HARDWARE ROUTING
----------------
- SSP1: MAX98357A internal speaker amplifier.
- SSP2: DA7219 headset codec.
- DMIC: separate capture path.

DA7219 is not required for internal-speaker rendering.

ACPI\BOOT0000 Code 28 is logged as NOT_AUDIO_BLOCKER. BOOT0000 is the
coreboot-table/debug ACPI device and is not part of the speaker dependency
chain.

RESTORE
-------
RESTORE_PHASER360_AUDIO.cmd restores the exported original ADSP and MAX98357A
drivers when a saved original baseline exists.
