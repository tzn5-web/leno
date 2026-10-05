# Vanced iOS stage status

Branch: `vanced-ios`

Current stage: original-IPA packaging pipeline ready; static core validation passed; device/IPA validation is pending.

Static validation evidence:
- GitHub Actions core build passed on macOS 15 / Xcode 16.4 / Apple clang 17
- all five Objective-C sources compiled with `-Werror`
- `VancedCore.dylib` linked, signed with ldid, and identified as arm64 Mach-O
- structural audit/self-tests passed independently
- SponsorBlock, RYD, speed memory, quality memory, native settings and Shorts UI are `validated_static`

Supply chain:
- production build now depends only on pinned Theos plus Apple SDK/system frameworks
- no PoomSmart/YTLite/iSponsorBlock/RYD tweak source is vendored or compiled into the product
- SponsorBlock and RYD are independent in-tree integrations using their public APIs

IPA packaging safeguards:
- input must be an authorized usable official YouTube IPA with bundle id `com.google.ios.youtube`
- compatibility selectors/classes are checked before packaging
- packaged output must contain and link `Frameworks/VancedCore.dylib`
- bundle identifier, version, build, executable name and `UIBackgroundModes` must remain identical to the input IPA
- no proprietary YouTube IPA is stored in this repository

Still pending:
- actual package/injection audit against a real YouTube IPA (none is attached or available in Library)
- device validation of settings, navigation, SponsorBlock, RYD, speed/quality memory and Shorts controls
- PiP and pause-state behavior where supported by the unmodified YouTube/iOS capability set

Explicitly not implemented:
- YouTube Premium entitlement impersonation
- internal YouTube advertising/monetization bypass hooks
- background-playback entitlement bypass

The product report remains `NEEDS_REVIEW` until the pending IPA/device gates are supplied. Structural CI is allowed to pass independently so incompleteness is never confused with a source/build defect.
