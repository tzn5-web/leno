PHASER360 FINAL AUDIO INSTALL + ONE PHYSICAL TEST
==================================================

Double-click START_AUDIO_TEST.cmd.

This is one autonomous install/repair transaction. It does not stop at a
separate PRE-AUDIO package and it does not restore the old drivers after a
successful test.

Flow:
  1. Detect and recover any incomplete prior P360 transaction.
  2. Verify the known-good ADSP/MAX baseline and back up both bound drivers.
  3. Validate the exact pinned f686 SOF firmware.
  4. Install the signed fail-closed P360Max98357Safe driver.
  5. Install the final P360SofAudio HOST/WaveRT driver.
  6. Inside that same final driver, prove the non-audible readiness gates:
       hardware identity -> NHLT -> SOF boot/FW_READY -> IRQ -> IPC3 ->
       HOST topology/AUDIO_CORE -> HDA ownership/readback -> MAX mute ACK.
  7. Perform exactly one physical playback test:
       Windows PCM -> WaveRT -> HDA DMA -> SOF HOST -> SSP1 -> MAX98357A.
     Test vector: 997 Hz, 2 seconds, 0.5% digital full-scale,
     48 kHz stereo, 16 valid bits in a 32-bit container.
  8. Prove the test stream stopped cleanly:
       MAX STOP/mute ACK -> SOF STOP/FREE -> HDA RUN=0.
  9. Re-verify the final ADSP driver, MAX driver, firmware, certificate and
     idle telemetry.
 10. On PASS, leave the final stack installed and the speaker endpoint active
     for normal Windows audio and future WaveRT streams.
 11. On any failure, automatically restore the exact saved ADSP/MAX/firmware
     baseline and remove the temporary trust certificate.

A successful run therefore ends with working PHASER360 audio installed.
It does not disable the target and does not return to P360AdspProbe.

The runner is self-aware in the practical sense required here:
- detects stale/partial prior P360 installs;
- uses the saved transaction state to recover before a new run;
- verifies exact driver/provider/version/hash identities;
- replaces the required ADSP/MAX components itself;
- verifies firmware and trust state;
- refuses ambiguous ownership or unproved GPIO/HDA states;
- rolls back automatically only if the install/test fails.

Fixed target:
  Windows 10 x64 build 19044
  Intel 8086:3198 / Phaser360
  SSP1 -> MAX98357A internal speakers
  48 kHz stereo
  firmware SHA256:
  f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab

Safety:
- no BIOS/UEFI changes;
- no BCD changes;
- no automatic reboot;
- one physical 2-second test only;
- MAX D0Entry is muted;
- START/STOP are generation-tagged and require GPIO-state ACK;
- HDA RUN transitions are proved by readback;
- WaveRT DMA pages are retained while ownership is ambiguous;
- failure rolls back; success remains installed.

Manual rollback after a successful install:
  Double-click RESTORE_LAST_SESSION.cmd.

Results:
  Desktop\P360_AUDIO_SAFE\
