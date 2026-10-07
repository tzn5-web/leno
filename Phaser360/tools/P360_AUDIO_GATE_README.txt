PHASER360 FINAL AUDIO SELF-HEALING INSTALL
===========================================

Double-click START_AUDIO_TEST.cmd.

The runner now treats a failure as a repair problem, not as an automatic
request to restore the old stack. The original ADSP/MAX/firmware baseline is
kept only so RESTORE_LAST_SESSION.cmd remains available as an explicit manual
choice.

Flow:
  1. Detect a clean baseline or resume an existing persistent P360 repair state.
  2. Preserve the original ADSP/MAX/firmware recovery provenance once.
  3. Validate the exact pinned f686 SOF firmware.
  4. Install or reuse the fail-closed P360Max98357Safe driver.
  5. Install or reuse the final P360SofAudio HOST/WaveRT driver.
  6. Bring the core to AUDIO_CORE. On failure the runner classifies and repairs
     PnP binding, firmware, bus/resource refresh, IRQ, IPC, topology or CSAudio
     dependency state, then re-verifies instead of rolling back.
  7. Repair Windows Audio/AudioEndpointBuilder publication and perform a
     no-audio WAVE_FORMAT_QUERY before any sample buffer is submitted.
  8. Run the bounded physical vector:
       997 Hz, 2 seconds, 0.5% digital full-scale,
       48 kHz stereo, 16 valid bits in a 32-bit container.
  9. If a physical attempt fails after waveOutWrite accepted the buffer, the
     runner first proves clean STOP/mute or forces fail-closed MAX D0Exit mute
     followed by ADSP D0Exit quiesce. Only a proved quiesced stack may be
     repaired and tried again.
 10. On PASS, leave the final stack installed and the speaker endpoint active
     for normal Windows audio.
 11. On unresolved failure, preserve the P360 stack and repair state for the
     next run. There is no automatic baseline rollback.

Automatic repair classes include:
- stale/wrong P360 child binding -> exact final rebind/rescan;
- pinned firmware load/FW_READY -> exact f686 recopy + ADSP restart;
- IRQ/IPC/topology runtime failure -> ADSP restart + fresh telemetry proof;
- CSAudio/MAX dependency issue -> safe MAX restart + ADSP restart;
- resource/identity/NHLT runtime mismatch -> audio-bus refresh + exact rebind;
- missing/delayed WaveRT endpoint -> AudioEndpointBuilder/Audiosrv repair,
  PnP rescan and silent format query;
- committed physical failure -> MAX mute + ADSP quiesce proof, then repair.

The same failure fingerprint repeating after repair is marked NEEDS_DRIVER_PATCH.
The installed stack and full diagnostics are preserved; the runner does not
pretend that repeated restarts can repair a deterministic kernel-code defect.

Hard stop is reserved for conditions where continuing would be physically
unsafe or recovery provenance is unavailable:
- the exact target/recovery provenance cannot be established;
- the exact f686 firmware/package identity cannot be validated;
- MAX98357A mute cannot be proved;
- ADSP/stream ownership cannot be quiesced after a committed playback.

TestSigning:
- if TestSigning is OFF, the runner enables it with bcdedit and schedules
  itself to resume after one normal manual Windows restart;
- it never reboots Windows automatically;
- Secure Boot still requires an explicit firmware-setting change if it blocks
  test-signed kernel drivers.

Fixed target:
  Windows 10 x64 build 19044
  Intel 8086:3198 / Phaser360
  SSP1 -> MAX98357A internal speakers
  48 kHz stereo
  firmware SHA256:
  f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab

Restore is manual only.

Manual restore:
  Double-click RESTORE_LAST_SESSION.cmd.

Results:
  Detailed state remains under Desktop\P360_AUDIO_SAFE\.
  Every Audio run writes one result ZIP directly on Desktop:
  P360_AUDIO_*.zip

Important result fields:
  RepairHistory, LastRepairClass, LastRepairAction, PhysicalAttempts,
  PhysicalCommitted, HardStop, NeedsDriverPatch, NeedsManualRestart.

A successful run ends with working PHASER360 audio installed.
A failed run leaves the repairable stack in place unless a manual Restore is
explicitly requested.
