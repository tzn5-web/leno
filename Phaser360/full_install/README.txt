PHASER360 FULL AUDIO DRIVER
===========================

Run INSTALL_PHASER360_AUDIO.cmd as the only installation entry point.

The installer performs a complete bind of:
  SklHDAudBus -> CSAUDIO ADSP -> P360SofAudio -> SOF host playback
  -> SSP1 -> P360Max98357Safe -> MAX98357A -> internal speakers
  -> PortCls/WaveRT -> Windows Audio endpoint.

It does not run a physical speaker tone as an installation gate.

The installer:
- validates the signed package and pinned firmware;
- backs up the currently bound ADSP and MAX98357A drivers once;
- imports the test certificate;
- stages the combined INF;
- force-binds that exact INF to both Phaser360 hardware IDs with
  UpdateDriverForPlugAndPlayDevices + INSTALLFLAG_FORCE so driver ranking
  cannot leave an older driver selected;
- verifies both devices are healthy and on the same package version;
- restarts Windows Audio;
- verifies the PHASER360 shared-mode endpoint without starting playback;
- resets a stale endpoint format to the OEM format if necessary;
- removes stale PHASER360 Project packages only after the full stack is healthy.

ACPI\BOOT0000 Code 28 is logged as NOT_AUDIO_BLOCKER and is not part of the
speaker dependency chain.

RESTORE_PHASER360_AUDIO.cmd restores the original exported drivers when a saved
baseline exists.
