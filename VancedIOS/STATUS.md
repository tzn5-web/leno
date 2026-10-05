# Vanced iOS stage status

Branch: `vanced-ios`

Current stage: original-IPA packaging pipeline ready for a user-supplied compatible YouTube IPA; runtime validation is still pending.

Implemented in the isolated `VancedIOS/` workspace:
- dynamic, version-tolerant speed memory
- remembered quality with closest-resolution fallback
- own SponsorBlock client using 4-character SHA-256 k-anonymous queries and native YouTube seek selectors
- SponsorBlock duration sanity checks before skipping
- own Return YouTube Dislike client with caching and API rate-limit backoff
- native Vanced settings section
- feed Shorts filtering and optional native Shorts-tab removal
- exact dependency pins, source audit, IPA compatibility audit and post-injection linkage audit
- jailed Theos packaging mode for a user-supplied official YouTube IPA

Not claimed as validated yet:
- Objective-C compilation on GitHub-hosted runners (current Actions jobs are receiving no runner: `runner_id=0`)
- actual IPA packaging/injection, because no YouTube IPA is attached or present in Library
- device behavior for navigation, settings, SponsorBlock, RYD, speed/quality and Shorts controls

Explicitly outside this implementation:
- hooks that impersonate Premium entitlements
- internal YouTube ad-service/monetization bypass hooks
- background-playback entitlement bypass

`RUNNER.sh` intentionally reports `NEEDS_REVIEW` while requested-but-unvalidated functionality remains unresolved. It does not turn missing evidence into a false PASS.
