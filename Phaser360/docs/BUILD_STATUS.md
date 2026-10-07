# Phaser360 diagnostic build status

This archive contains unsigned Windows x64 compilation artifacts. It is a
development checkpoint, not a final audio driver or an installable package.

All five build profiles retain their SYS and matching PDB. `build-manifest.json`
records the source commit, workflow run, pinned SDK/WDK version, compilation
gates, file sizes and SHA-256 hashes. Build profiles with SOF boot enabled can
operate the DSP if installed; compilation does not validate their behavior on
hardware.

The speaker endpoint can negotiate 48 kHz stereo PCM16, but its RUN transition
still returns `STATUS_DEVICE_NOT_READY`. The internal speaker policy remains
zero. Topology message builders are not yet integrated into a live playback
pipeline. No physical playback has been proved by this build.

Before a final functional release, the project still requires:

- Live topology create/connect/configure, trigger, STOP and rollback.
- CoolStar render DMA integration with the WaveRT stream and real position.
- Power/suspend/resume and remove lifecycle validation on the target laptop.
- A complete driver installation package, catalog, signing and firmware staging.
- Speaker, DA7219 headset and DMIC hardware tests for their respective paths.

`P360SofAudio.inx` is the existing System-class binding template. It is supplied
for inspection, not installation. No certificate, catalog or firmware binary
is included. The required firmware must match the size and SHA-256 in
`P360_FIRMWARE_MANIFEST.txt`; another file named `sof-apl.ri` is not equivalent.

The target is Phaser360, Intel Gemini Lake 8086:3198 through the pinned
CoolStar SklHDAudBus/CSAUDIO ADSP interface, Windows 10 x64 build 19044 or later.
