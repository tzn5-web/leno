PHASER360 AUDIO GATE
====================

This package is intentionally fail-closed.

Fast path:
  Open PowerShell as Administrator and run one transaction:
       powershell -ExecutionPolicy Bypass -File .\P360_AUDIO_GATE.ps1 -Mode Audio -FirmwarePath "C:\path\to\sof-apl.ri"

Audio mode performs PRE-AUDIO proof first and reaches the 250 ms speaker tone
only when FW_READY + IRQ + IPC3 -22/12 bytes + STOP are all proved in the same run.

The separate Audit / PreAudio / BoundedSpeaker modes remain available for diagnosis.

The runner:
- never changes BIOS/UEFI;
- never enables TestSigning;
- never reboots automatically;
- verifies the exact Phaser360 target and SklHDAudBus;
- requires exact f686 firmware: 246528 bytes,
  SHA256 f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab;
- exports the currently bound OEM driver before any swap;
- backs up any existing P360 firmware;
- installs only the test-signed package included here;
- reads proof telemetry written by P360SofAudio;
- PRE-AUDIO requires FW_READY + IRQ + IPC3 reply -22/12 bytes;
- disables the device and requires STOP_COMPLETE before cleanup;
- restores the original driver, firmware and certificate;
- refuses BoundedSpeaker unless a matching PRE-AUDIO PASS exists;
- Audio mode performs PRE-AUDIO and bounded speaker sequentially in one transaction;
- Audio never reaches speaker START unless PRE-AUDIO proof and STOP succeeded first;
- BoundedSpeaker/Audio emit at most the compiled 250 ms SOF Tone diagnostic.

If an interrupted run prevents automatic rollback:
  powershell -ExecutionPolicy Bypass -File .\P360_AUDIO_GATE.ps1 -Mode Restore

You may specify an exact firmware binary or the audited v10.11B ZIP:
  -FirmwarePath "C:\path\to\p360-f686.ri"
  -FirmwarePath "C:\path\to\PHASER360_v10_11B_FULL_LINK_AUDIT_ONLY.zip"

Results are written under:
  Desktop\P360_AUDIO_SAFE\
