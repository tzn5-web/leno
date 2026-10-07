PHASER360 AUDIO ONE-SHOT
=========================

Use:
  Double-click START_AUDIO_TEST.cmd.

No PowerShell commands need to be typed.

The launcher requests Administrator rights and runs one fail-closed transaction:

  1. Recover/verify the known baseline:
       service P360AdspProbe
       provider PHASER360 Project
       version 1.1.0.0
       device problem code 0

  2. PRE-AUDIO only:
       exact f686 firmware
       FW_READY
       IRQ/runtime bind
       IPC3 proof reply -22 / 12 bytes
       D0 STOP proof
     This build has NO Tone topology, NO internal-speaker gate,
     NO bounded-tone gate and NO Windows speaker endpoint.

  3. Restore and re-verify the baseline.

  4. Only if PRE-AUDIO and PRE-AUDIO STOP passed in this same run:
       load the separate bounded speaker build
       prepare the reviewed Tone -> SSP1 path
       start the SOF stream
       arm speaker policy
       start MAX98357A through CSAudio
       emit at most 250 ms of the SOF Tone diagnostic
       stop/mute MAX98357A
       disarm speaker policy
       stop the SOF stream
       prove D0 STOP

  5. Restore the original driver, firmware state and test certificate.

Safety rules:
- no BIOS/UEFI changes;
- no BCD changes;
- no automatic reboot;
- no speaker phase if PRE-AUDIO fails;
- no speaker phase if PRE-AUDIO STOP fails;
- no speaker phase from a saved proof from an older run;
- no normal Windows WaveRT playback is enabled by this test;
- exact firmware required: 246528 bytes,
  SHA256 f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab;
- MAX98357A must be present, healthy and bound before speaker phase;
- the bounded tone build is compiled for a one-shot maximum of 250 ms.

The runner automatically searches the audited firmware locations under
D:\PHASER360_WORK and validates size/hash before use.

If an earlier interrupted test left P360SofAudio selected, START_AUDIO_TEST.cmd
uses the saved P360_AUDIO_SAFE baseline to repair it before starting a new test.

If Windows itself still requires one restart to clear a pending PnP operation,
the runner does NOT reboot automatically. It schedules START_AUDIO_TEST.cmd to
reopen after the next normal Windows restart and exits without starting speaker
audio.

Emergency/manual recovery only:
  Double-click RESTORE_LAST_SESSION.cmd.

Results:
  Desktop\P360_AUDIO_SAFE\
