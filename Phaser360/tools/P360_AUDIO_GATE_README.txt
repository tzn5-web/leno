PHASER360 FINAL INTERNAL-SPEAKER TEST
======================================

Double-click START_AUDIO_TEST.cmd.

The launcher requests Administrator rights and performs one transaction only:

  1. Verify/recover the known healthy P360AdspProbe baseline.
  2. Validate and install the pinned f686 SOF firmware.
  3. Bind the final P360SofAudio test driver.
  4. Boot SOF and establish IRQ + IPC3.
  5. Build the proven Tone -> SSP1 -> MAX98357A path.
  6. Before PCM prepare, force both SOF Tone channels to Q1.31 0x01000000,
     exactly 1/128 = 0.78125% full-scale (~ -42.14 dBFS).
  7. Play the internal-speaker diagnostic for exactly 2000 ms.
  8. Mute/STOP MAX98357A, stop the SOF stream and prove D0 STOP.
  9. Restore the original driver, firmware state and temporary test certificate.

There is no separate PRE-AUDIO driver swap in this package. The already-proven
FW/IRQ/IPC checks remain fail-closed inside the final driver before speaker START.

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
- amplifier STOP/mute is issued before DSP teardown;
- final diagnostic amplitude is below 1% digital full-scale;
- final diagnostic duration is 2 seconds;
- baseline restore is verified at the end.

Emergency/manual recovery:
  Double-click RESTORE_LAST_SESSION.cmd.

Results:
  Desktop\P360_AUDIO_SAFE\
