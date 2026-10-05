# PHASER360 PRE-AUDIO GATE

This stage proves the parent HDA interrupt path without booting the audio DSP and without audio playback.

It temporarily binds a diagnostic driver only to the Intel HDMI HDA codec child:
`HDAUDIO\FUNC_01&VEN_8086&DEV_280D`.

The diagnostic sends one standard read-only HDA verb:
`GET_PARAMETER(VENDOR_ID)`.

A valid synchronous response requires CoolStar SklHDAudBus to complete the CORB/RIRB path. Because SklHDAudBus invokes the registered ADSP callback at the start of its shared ISR, the simultaneously installed P360AdspProbe v2 counter should increase. This gives an active IRQ proof without SOF firmware, IPC, streams, speaker control, or playback.

The gate never binds to DA7219 or MAX98357A and never writes codec or amplifier registers.
