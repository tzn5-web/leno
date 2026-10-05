# Vanced iOS stage status

Branch: `vanced-ios`

Current stage: audit foundation.

Present:
- isolated `VancedIOS/` workspace
- pinned dependency lock with exact commit SHAs
- complete requested feature matrix
- autonomous Python stage audit
- shell runner that emits `reports/STAGE_AUDIT.json`
- dedicated GitHub Actions audit workflow

The audit intentionally requires implementation-stage files before it can pass. Missing implementation is reported as an error rather than silently accepted.

Runtime-only behaviors remain explicit device gates: background continuation, lock-screen pause/play state preservation, unlock state restoration, PiP while navigating YouTube, and return-from-PiP state preservation.
