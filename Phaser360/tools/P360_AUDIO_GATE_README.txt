PHASER360 AUDIO GATE
====================

This package is intentionally fail-closed.

ONE-CLICK PATH:
  Double-click START_AUDIO_TEST.cmd.

The CMD launcher requests Administrator rights automatically, checks for the
latest previous hardware-changing Audio session and restores it first when
needed, then starts the new Audio transaction. It keeps the window open at the
end so the result is visible. No PowerShell command needs to be typed manually.

Audio mode performs PRE-AUDIO proof first and reaches the 250 ms speaker tone
only when FW_READY + IRQ + IPC3 -22/12 bytes + STOP are all proved in the same run.

If automatic recovery cannot prove the baseline, Audio does not start. In that
case use RESTORE_LAST_SESSION.cmd. If its log explicitly says Windows restart
is required, restart Windows once and double-click START_AUDIO_TEST.cmd again.

The separate Audit / PreAudio / BoundedSpeaker modes remain available only for diagnosis.

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

Recovery is available through RESTORE_LAST_SESSION.cmd; no manual PowerShell
command is required.

Firmware discovery is automatic. The runner checks the audited known
D:\PHASER360_WORK locations first, then the package folder, Desktop, Downloads
and D:\PHASER360_WORK recursively. Every candidate is accepted only if it is
exactly 246528 bytes with the pinned f686 SHA256.

Results are written under:
  Desktop\P360_AUDIO_SAFE\
