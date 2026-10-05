# Vanced iOS stage status

Branch: `vanced-ios`

Current stage: reproducible audit + core compile foundation.

Present:
- isolated `VancedIOS/` workspace
- pinned dependency lock with exact commit SHAs
- complete requested feature matrix
- explicit per-feature implementation status
- autonomous Python stage audit
- audit self-tests
- shell runner that emits `reports/STAGE_AUDIT.json`
- pinned Theos bootstrap
- exact dependency fetch/pin verifier
- minimal arm64 core scaffold
- macOS core compile workflow with SHA-256 evidence
- dedicated stage-audit workflow with superseded-run cancellation

Important: the core scaffold only proves that the isolated tweak project can compile. It does not claim the requested Vanced feature set is implemented.

The stage audit deliberately remains `NEEDS_REVIEW` while any required feature is not implemented/validated.

Runtime-only behaviors remain explicit device gates: background continuation, lock-screen pause/play state preservation, unlock state restoration, PiP while navigating YouTube, and return-from-PiP state preservation.
