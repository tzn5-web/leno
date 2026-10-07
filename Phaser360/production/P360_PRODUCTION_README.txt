PHASER360 PRODUCTION AUDIO PACKAGE
=================================

This package is the direct PnP driver form of the project.

Contents:
- P360AudioBundle.inf
- P360AudioBundle.cat
- P360SofAudio.sys
- P360Max98357Safe.sys
- p360-f686.ri
- P360_TEST.cer

The INF has two hardware models:
- CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198 -> P360SofAudio
- ACPI\MX98357A -> P360Max98357Safe

There is no PREAUDIO stage, no diagnostic driver swap, no 997 Hz test and no
automatic rollback in this package. It is intended to remain installed as the
normal Windows audio stack.

The kernel drivers themselves retain the required target-ID, DMA ownership,
stream STOP and amplifier mute protections. Those are part of correct driver
operation rather than an external test gate.

The catalog is test-signed. Windows must already be configured to accept the
test-signed PHASER360 package, and the included public certificate must be
trusted on the target machine before PnP can bind the package.
