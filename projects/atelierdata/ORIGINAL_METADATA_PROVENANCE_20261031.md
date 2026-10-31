# Original Autodata — static product metadata provenance (2026-10-31)

Read-only analysis of the owner-authorized `autodata_part_0004.zip` from private Google Drive. Blocked `autodata_part_0016.zip` was not accessed. No executable or installer was run, no registry or license operation attempted. No original XML text, distributor contact information, translations or proprietary databases are published.

## Directly verified finding

Four members were individually SHA256-verified against the private owner-supplied `INVENTAR.json`:

| Source member | Bytes | SHA256 | Static observation |
| --- | ---: | --- | --- |
| `COMMON/VERINFO.DAT` | 79 | MATCH | `ProductCode=CDA3.44`, `VersionNo=9.200` |
| `COMMON/distinfo.xml` | 14,255 | MATCH | `Distributors` root, 319 XML elements |
| `ENG/country.xml` | 3,355 | MATCH | `Countries` root, 97 XML elements |
| `ENG/string.xml` | 114,993 | MATCH | `AllText` root, 2,168 XML elements |

The archive and root folder are labeled `Autodata__3.45`, while the SHA256-verified internal product metadata contains `ProductCode=CDA3.44`. This is a **real metadata difference, not proof** of a defective, mismatched, counterfeit, expired, or unlicensed installation. The internal `VersionNo=9.200` has unknown semantics. Expiry and registration fields were not interpreted or modified.

A legitimate vendor/support inquiry can determine whether a 3.45 distribution intentionally carries a 3.44 product identifier. This observation does not justify patching metadata, replacing DLLs, or bypassing activation.

## Code, tests and limitations

`original_metadata_provenance_audit.py` reads only four allowlisted members from part 0004, checks declared size, member uniqueness, encryption/symlink flags, SHA256, XML validity and DTD/entity rejection. Public output contains only product/version labels and XML tag counts. Eleven synthetic unit tests passed locally (Linux); the real four-member audit also succeeded. Windows CI is a separate gate, to be checked for the exact commit. No private original bytes are used in CI.

Reproduce in an authorized private environment:

    python projects/atelierdata/original_metadata_provenance_audit.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\metadata-public.json

Original installation remains **NOT READY**: installation and activation-related materials are only named in blocked part 0016; vendor authenticity, license entitlement and Windows runtime compatibility are not established. All 81 IDF files remain undecoded. SHA256 against the owner's manifest does not prove publisher authenticity.
