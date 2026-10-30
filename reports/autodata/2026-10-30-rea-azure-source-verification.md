# Autodata OneClick / REA / Azure — run verification, 2026-10-30

## Source integrity and new static findings

- Original RAR Drive metadata rechecked: `Autodata__3.45.rar`, 2,284,074,345 bytes, ID `1lC8pgAMU4RMkcatQClkzNnABJZpsKxZE`. The full archive SHA256 is recorded in the original `INVENTAR.json`; the original RAR bytes were not re-downloaded in this run.
- Existing ZIP part 0001 copy was inspected inertly. `ADBCD.exe` is 18,102,272 bytes with SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`; matches the manifest. No executable was launched.
- PE32 x86 original static import table: four DLLs, 17 named functions. In particular `LoadLibraryA` and `GetProcAddress` are present, so a four-DLL import table does not exclude dynamic dependencies. See `tools/autodata-oneclick/PE32_SOURCE_IMPORTS_STATIC_AUDIT.md`.
- A contiguous embedded DLL-name block includes `SentinelKeyW.DLL` at byte offset 17,718,897 and `gdiplus.dll` at 17,718,931. These are references, not proof of runtime loading or licensing.
- Original `COMMON/VERINFO.DAT` declares `ProductCode=CDA3.44`, so the RAR filename's `3.45` label remains unverified.

## Google Drive access (rechecked)

- Source folder listing succeeded and contained 16 ZIP parts.
- `autodata_part_0016.zip`, ID `1wSRLAczGM3ugwb_GWBA5AcoeNJit719P`, **still returns HTTP 403 `cannotDownloadAbusiveFile`** with provider message `This file has been identified as malware or spam and cannot be downloaded.`
- Five application DLLs and the original installation instructions remain inaccessible in this part. No attempt was made to bypass the provider's security restriction.

## REA integration (executed, not hypothetical)

- Upstream `morluto/rea` package `rea-agents` version **6.8.0**, required Node versions `^22.23.4 || ^24.22.1 || >=26.12.1`. Release tag `rea-agents-6.8.0` published 2026-10-25.
- New `rea_static_private.ps1` pins the expected SHA256, checks Node, keeps evidence outside public repository and runs `inspect-pe-imports`, `inspect-pe-certificates`, `inspect-desktop-application` read-only.
- New `.github/workflows/autodata-rea-static-ci.yml` executed **real REA 6.8.0** on a harmless `notepad.exe` Windows fixture, Node 24.22.1. Hash mismatch rejection, PE imports, PE certificates, desktop inspection and evidence artifact upload all **PASS**.
- Confirmed GitHub Actions run: [41109921444](https://github.com/tzn5-web/leno/actions/runs/41109921444). Fixture SHA256 `84b484fd3636f2ca3e468d2821d97aacde8a143a2724a3ae65f48a33ca2fd258` (Windows runner-specific).
- **Original ADBCD.exe was not analyzed with REA**, because the REA environment available in GitHub Actions has no access to the private original and public upload is prohibited. Independent Python PE inspection above is a different analysis method.

## Installer safety gates

- Added `release_gate.py` requiring private human attestation for source, genuine vendor-license evidence, install instructions, Sentinel, source version discrepancy and private distribution. This attestation is not independent vendor license verification.
- Updated `build_oneclick.ps1` to refuse builds without a private review record and to require the `--production` manifest identity check. Output defaults outside the public repository.
- `verify_payload.py --production` pins original RAR manifest SHA256/size/count and original `ADBCD.exe` SHA256/size and rejects symlink/path traversal. Synthetic fixtures are not accepted in production mode.
- Existing Inno Setup synthetic template CI tests installation/uninstallation only with harmless fake content, not the real application. Final installer remains blocked.

## Azure (actual connected-account read-only checks)

- Subscription `0ac7a514-32b3-47bf-bf89-e17906b1cc86` is **Enabled**.
- `RG-CHATGPT-AZURE` resources can be listed through ARM. Storage account `tzn5androidartifacts26` exists (StorageV2, Standard_LRS, HTTPS-only, no public blob access).
- Linux VM `android-dev-linux` is **deallocated** (instance-view confirmed). It was not started; no new VM was created.
- Blob container list failed with `IDW10502` / `MsalUiRequiredException` / incremental consent. Azure data-plane permissions are not usable through this connection until re-consent. The ARM metadata access does not imply Blob access.
- A Windows Azure VM was **not** provisioned: complete, verified authorized original source and vendor activation are unavailable, and the current GitHub-hosted Windows runner already covers synthetic template testing. Avoided additional Azure spend.

## Pending and release status

**Authentic Autodata OneClick Setup.exe: NOT BUILT / NOT TESTED / NOT RELEASED.** The original installation instructions, five DLLs, authentic vendor activation, version validation and isolated real Windows install/launch/uninstall tests remain missing. No proprietary binary or activation utility was uploaded to GitHub.
