# YouTube 21.40.5 — audit de proveniență

Official App Store: https://apps.apple.com/ro/app/youtube/id544007664

This branch tests the THIRD-PARTY decrypted candidate for stock YouTube 21.40.5
as declared by the reproducible build workflow at
https://github.com/itzzace/ytkace/blob/v1.1.2/.github/workflows/build-ipa.yml
The candidate is NOT a Google/Apple-issued download.

The workflow downloads it only as untrusted data and never runs or publishes the IPA.
The gate checks SHA256, ZIP path/CRC/size hazards, arm64 Mach-O, cryptid, declared
YouTube bundle/version, and indicative injection modules. The resulting status
STRUCTURE_PASS_PROVENANCE_UNVERIFIED is not an attestation or malware-free proof.
It cannot detect all malicious modifications of a proprietary Mach-O binary.
Further independent source/code comparison and iPhone tests are required.

No old YouTubeX/YouPiP hooks are injected into this new 21.40.5 binary, because
their compatibility with the new selectors and player ABIs is not established.
The already working 20.21.6 IPA remains untouched. Updating an App Store copy
will not preserve sideload-injected code; any new version requires re-injection
and re-signing.
