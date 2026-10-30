# Autodata 3.45 — verified source audit (30 October 2026)

**Purpose:** record what the owner's actual private archive supports. No original executable was run. No activation was attempted. Never treat this audit as license validation.

## What was actually examined

- Original Drive archive `Autodata__3.45.rar`, size 2,284,074,345 bytes, SHA256 `e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da` (from the verified Colab manifest).
- `INVENTAR.json`: 139 extracted files, split into 163 fragments over 16 ZIP parts. 105 files belong to `ADCDA2`.
- Downloaded and opened normally through the connected Drive service: `autodata_part_0001.zip` and `autodata_part_0004.zip`. Their files were read as bytes, without execution.
- The extracted original `ADCDA2/ADBCD.exe` from ZIP 0001 has 18,102,272 bytes and SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`. Hash matches the original inventory. ZIP CRC read also passed.
- Its PE/COFF header declares `IMAGE_FILE_MACHINE_I386` (0x014c), PE32 (0x10b), build timestamp 2013-11-20T09:11:29Z, no embedded Authenticode certificate table, DLL imports `KERNEL32.dll`, `USER32.dll`, `ADVAPI32.dll`, `MSVCRT.dll`. Version-resource strings include `FileVersion=2.44.0.2764` and `CompanyName=Autodata Limited`. These are untrusted self-reported metadata, not a guarantee of authenticity or safety.
- `ADCDA2/COMMON/VERINFO.DAT` from ZIP 0004 declares `ProductCode=CDA3.44`, `VersionNo=9.200` and `ExpiryDate=42004`. Its SHA256 was verified against the manifest. **Therefore 'Autodata 3.45' in the archive filename cannot alone establish the product's actual version.** The expiry field's semantics are not confirmed.
- `ADCDA2/ENG/RegMessage.htm` and `ADCDA2/ENG/TERMCOND.TXT` were directly read from ZIP 0004 and SHA256-checked against the manifest. They describe a vendor-issued registration code / electronic permit supplied for a subscription; the terms refer to subscription CDs becoming unusable after approximately eight months. They restrict redistribution/copying without written permission. These documents could pertain to the CD subscription lineage, and do **not** establish that any keygen/emulator in the supplied bundle is authorized.
- `ADCDA2/ENG/COPY.txt` further records copyright and database rights; it must be preserved in any authorized copy.

## Unread source blockers

The Drive API returned `403 cannotDownloadAbusiveFile` for `autodata_part_0016.zip`; this is a provider malware/spam warning. Do not bypass this check.

Crucially, the blocked ZIP contains **five files in the core application tree**:
- `ADCDA2/SentinelKeyW.DLL` (2,961,712 bytes)
- `ADCDA2/cw3220mt.dll` (245,760 bytes)
- `ADCDA2/gdiplus.dll` (1,748,992 bytes)
- `ADCDA2/libeay32.dll` (1,069,056 bytes)
- `ADCDA2/ssleay32.dll` (221,184 bytes)

Other members include installation instructions, several license-generation and dongle-emulator utilities, driver/signing helpers, registry files, and redistributable installers. Their content has not been read and is not executed or integrated.

**No complete production installer can be built and verified from the accessible ZIPs only.** The vendor activation requirements cannot be satisfied by copying the program files.

## Installer design changes verified

1. `ADBCD.exe` is PE32/x86. The Inno Setup source no longer forces the 64-bit install mode.
2. The tentative default folder is now `{sd}\ADCDA2` (typically `C:\ADCDA2`), rather than nesting beneath Program Files. This is **a compatibility hypothesis** based on the legacy program's packaging, not proof of the original setup's requirements.
3. The Inno template writes the validated `ADCDA2` content to the installation root, creates shortcuts and uninstall entry. It does **not** register arbitrary DLLs or import registry scripts of unknown provenance.
4. The builder rejects incomplete source trees or SHA256 mismatches; Defender scanning is required before packaging.
5. A GitHub Actions Windows job builds and checks **synthetic test data only**. It does not verify that a real installation of Autodata starts or has a valid license.

## Remaining work before a final executable

- Obtain all original files through a source permitted by Google/provider checks. Confirm authenticity and licensing terms.
- Inspect the actual installation TXT/PDF/REG/CMD files inertly and derive any legitimate prerequisites. Never apply arbitrary registry patches or load a suspect kernel driver automatically.
- Obtain a genuine valid Autodata activation. Do not use the enclosed keygen/emulators as a substitute.
- Run an isolated Windows install/start/uninstall test with an authorized application source and a legitimate activation.
- Only then publish a signed, labeled install artifact, ideally in a private repository/distribution. The original proprietary package is not published in this repository.

## Source vs inference

The hashes, file sizes, metadata, and quoted field names are from the user's package. The selected Inno installation path and compatibility choices are engineering hypotheses. Vendor authenticity, entitlement, licensing status, runtime success and expiry behavior are **not verified**.
