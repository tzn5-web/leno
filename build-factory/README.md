# Multi-platform build factory

Four isolated, on-demand GitHub Actions builds with no Azure VM deployment and no credentials stored in source.

| Choice | Build inputs | Output |
| --- | --- | --- |
| windows | `build-factory/windows` .NET 8 sample and WiX installer | Executable EXE + MSI |
| android | `build-factory/android` Java/Gradle sample | Debug APK |
| tizen | Existing `tzn5-web/adfree-tizen-q60r` Q60R workflow sources | Signed WGT when the existing signing process succeeds |
| ios | Existing `leno` XcodeGen project | **Unsigned** IPA archive; not installable without suitable Apple signing |

## Run

On the repository's default branch after merging, choose **Actions > Multi-platform build factory > Run workflow**, then the target. Build artifacts are retained for seven days. The initial branch push tests Windows and Android only; iOS and Tizen run on explicit request.

## Boundaries

- This is a verified *build-factory smoke-test configuration*, **not** a claim that any unrelated third-party app will build without adapting its source and dependency chain.
- Existing iOS and Q60R pipelines remain intact. This workflow calls their project-specific recipes without editing application sources.
- The Windows and Android targets are minimal working demonstration apps. Replace or adapt those sources and build commands for real projects.
- APK is debug-signed by Android tooling; use a private release keystore stored in encrypted secrets for release builds.
- The iOS file is an unsigned IPA-formatted archive, not an Apple-signed installable package. Proper provisioning and Apple signing credentials are needed for device distribution.
- Tizen devices require a valid TV signing profile / DUID where applicable; retain the existing repository's signing flow.
- GitHub Actions artifact links expire. Use signed releases for permanent distribution.
- No paid Azure resources are created and no Azure secrets or keys are required. If Azure is connected later, prefer OIDC federation, least-privilege roles and explicit budget alerts.

## Authoritative references

- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://developer.android.com/build/releases/agp-8-9-0-release-notes
- https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/command-line-interface.html
- https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases
