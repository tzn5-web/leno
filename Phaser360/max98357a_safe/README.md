# PHASER360 MAX98357A fail-closed driver

This is a narrow Apache-2.0 derived replacement for the CoolStar MAX98357A
GPIO amplifier driver on the Phaser360 target.

Safety contract:

- D0Entry always writes SDMODE low.
- START carries a monotonically increasing generation.
- START first forces low, waits 5 ms, re-checks generation/state, then writes high.
- A concurrent STOP invalidates the pending START before GPIO can be asserted.
- START/STOP emit generation-tagged ACK callbacks containing NTSTATUS and the
  resulting powered state.
- P360SofAudio remains forbidden from touching the GPIO directly.

It targets only ACPI\MX98357A. It is not a generic replacement for the other
devices supported by the upstream CoolStar package.
