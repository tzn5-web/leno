PHASER360 FINAL INTERNAL-SPEAKER TEST
======================================

Double-click START_AUDIO_TEST.cmd.

The launcher requests Administrator rights and performs one fail-closed transaction:

  1. Recover/verify the known healthy P360AdspProbe baseline and MAX98357A baseline.
  2. Validate the exact pinned f686 SOF firmware.
  3. Back up the currently-bound MAX98357A driver.
  4. Disable MAX98357A so the old driver drives SDMODE LOW.
  5. Stage the signed P360Max98357Safe package, remove only the exact ACPI\MX98357A devnode, rescan, and prove:
       Service=P360Max98357Safe
       Provider=PHASER360 Project
       Version=2.0.0.0
  6. Bind the final P360SofAudio HOST/WaveRT driver.
  7. PRE-AUDIO gate: prove fresh SOF boot, FW_READY, runtime IRQ, IPC3, HOST topology/AUDIO_CORE and the acknowledged MAX mute state.
  8. Only after PRE-AUDIO passes, run the single physical test:
       Windows PCM -> WaveRT -> CoolStar HDA DMA -> SOF HOST -> SSP1 -> MAX98357A.
     The test vector is 997 Hz, 2 seconds, 0.5% digital full-scale, 16 valid bits left-aligned in a 32-bit container.
  9. Prove MAX STOP/mute ACK, SOF STOP and HDA STOP.
 10. Disable/stop the P360 target and prove D0 STOP.
 11. Restore the original ADSP driver, the exact original MAX98357A driver, firmware state and temporary test certificate.

No previous PRE-AUDIO result is reused. The PRE-AUDIO proof is fresh in the same run,
and the runner advances directly to the speaker test only after every gate passes.

Fixed target:
  Windows 10 x64 build 19044
  Intel 8086:3198 / Phaser360
  SSP1 -> MAX98357A internal speakers
  48 kHz stereo
  pinned firmware SHA256:
  f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab

Safety:
- no BIOS/UEFI or BCD changes;
- no automatic reboot;
- no automatic retry of the physical speaker phase;
- safe MAX D0Entry is always muted;
- START/STOP are generation-tagged and require an ACK with resulting GPIO state;
- amplifier STOP/mute is proved before DSP/HDA ownership is released;
- DMA-backed WaveRT pages are never freed while SOF/HDA ownership remains possible;
- final test vector is 0.5% digital full-scale for 2 seconds;
- both ADSP and MAX98357A baselines are restored and verified at the end.

Emergency/manual recovery:
  Double-click RESTORE_LAST_SESSION.cmd.

Results:
  Desktop\P360_AUDIO_SAFE\
