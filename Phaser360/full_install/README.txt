PHASER360 FULL AUDIO DRIVER
===========================

Run INSTALL_PHASER360_AUDIO.cmd as the only installation entry point.

The package contains one combined production driver version/INF/CAT and binds:
  SklHDAudBus -> CSAUDIO ADSP -> P360SofAudio -> SOF host playback
  -> SSP1 -> P360Max98357Safe -> MAX98357A -> internal speakers
  -> PortCls/WaveRT -> Windows Audio / WASAPI shared endpoint.

INSTALL / REPAIR MODEL
----------------------
The installer:
- validates the signed package and pinned firmware;
- saves the original ADSP/MAX98357A baseline once, but never records an
  already-installed PHASER360 production driver as the original baseline;
- imports the test certificate;
- stages the single combined INF;
- force-binds that exact same INF to both Phaser360 hardware IDs with
  UpdateDriverForPlugAndPlayDevices + INSTALLFLAG_FORCE so driver ranking
  cannot silently leave the older driver selected;
- verifies ADSP and MAX98357A are healthy, use the expected services/provider,
  and are on the same production version;
- restarts Windows Audio;
- performs WASAPI shared preflight without starting playback;
- repairs a stale endpoint format through
  IAudioEndpointFormatControl::ResetToDefault(0);
- repeats only no-sound repair/preflight operations;
- removes stale PHASER360 Project packages only after the active production
  binding and Windows Audio endpoint are healthy.

FINAL ACCEPTANCE
----------------
The installer itself is install-only: it does not start physical playback.

After INSTALL_PHASER360_AUDIO.cmd reports PASS, run
TEST_PHASER360_AUDIO.cmd when you want the real final acceptance. That command
performs exactly ONE physical WASAPI shared playback attempt:
- 48 kHz stereo PCM;
- 32-bit container / 16 valid bits;
- 997 Hz;
- 2000 ms;
- less than 0.5 percent amplitude.

There is no automatic second physical attempt. The test result does not swap
drivers or roll back the installed production stack.

The legacy waveOut utility is not part of the full-install package and is not
used as production acceptance.

WINDOWS AUDIO FORMAT
--------------------
PKEY_AudioEngine_OEMFormat defines the manufacturer default endpoint format.
PKEY_AudioEngine_DeviceFormat must resolve to the exact production format
before playback. GetMixFormat is only the Windows Audio Engine internal mix
format and may be floating-point; it is observed but not mistaken for the
hardware/device format.

The driver deliberately does not advertise event-driven WaveRT. The Phaser360
ADSP child exposes CoolStar GUID_ADSP_BUS_INTERFACE, while HDAUDIO V2/V3
notification interfaces belong to codec children. The current production path
therefore uses WaveRT position polling.

HARDWARE TOPOLOGY
-----------------
The speaker path follows the Linux/CoolStar topology:
- SSP1: MAX98357A internal speaker amplifier;
- SSP2: DA7219 headset codec;
- DMIC: separate capture path.

DA7219 is not a dependency of internal-speaker rendering.

ACPI\BOOT0000 Code 28 is logged as NOT_AUDIO_BLOCKER. It is the coreboot table
/debug ACPI device and is not part of the speaker dependency chain.

RESTORE
-------
RESTORE_PHASER360_AUDIO.cmd is manual. It restores the exported original ADSP
and MAX98357A drivers only when a real original baseline was saved.
