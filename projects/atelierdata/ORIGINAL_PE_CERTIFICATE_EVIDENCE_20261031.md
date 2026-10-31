# Original Autodata — PE certificate evidence, 2026-10-31

## Scope and reproducible method

Read-only static audit of **five** allowlisted root PE files in the owner's already authorized ZIP parts, using `INVENTAR.json`. Each file was streamed from its ZIP member, matched by name and size, and checked against its manifest SHA256 before parsing the PE optional header and `IMAGE_DIRECTORY_ENTRY_SECURITY` (file offset, not RVA). The tool neither executes nor extracts the executable, DLLs, installers, drivers or license tools. The malware-flagged `autodata_part_0016.zip` was not accessed. No original bytes were committed to this repository.

Command used in the private analysis environment:

```powershell
python projects/atelierdata/original_pe_certificate_audit.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\pe_certificates.json
```

## Actual findings (owner-manifest SHA256 verified)

| PE file | Size (bytes) | Embedded WIN_CERTIFICATE | PKCS#7 container | SHA256 |
| --- | ---: | --- | --- | --- |
| `ADBCD.exe` | 18,102,272 | **Absent** | 0 | `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` |
| `ChilkatCert.dll` | 856,992 | Present | 1 | `3f1ee751d68b62e7d587f42d1c70dec6861c9b84f841232d2428f72eb1df89cd` |
| `ChilkatCrypt2.dll` | 926,624 | Present | 1 | `3883e2a1eb115e3aac63651f58b5d41ecea246fe1e80e3ff1a6d780ab24ea534` |
| `ChilkatUtil.dll` | 660,384 | Present | 1 | `fe2090450e9761da52fcd037934553d061fd0b395ad260dff3b81c30c202a10c` |
| `RelLic.dll` | 28,792 | Present | 1 | `a654e285a051a005fff895492f85242803f570ec9fdbcb49dedd60d8cac4e504` |

All five are PE32 x86. The certificate directories of the four DLLs contain one structurally well-formed `WIN_CERTIFICATE` entry each (`wRevision=0x0200`, `wCertificateType=0x0002`). The main `ADBCD.exe` has **no embedded certificate table**. That does **not** rule out a separate catalog signature or establish that the executable is malicious.

An additional **static ASN.1 metadata inspection**, using `asn1crypto 1.5.1` on the private PKCS#7 payloads, found embedded signer identifiers matching certificate subjects named **Chilkat Software, Inc.** (three Chilkat DLLs) and **SafeNet, Inc.** (`RelLic.dll`). These are untrusted *claims in embedded certificates*, **not verified identities, signature integrity, valid timestamps, or trusted publisher chains**. A PKCS#7 structure alone is insufficient for any authenticity or safety verdict.

## What this changes for the original repair

The archive is not a uniformly signed, publisher-authenticated installer. The original main EXE lacks an embedded certificate, whereas the bundled library files contain certificate structures from at least two named third parties. Therefore **file integrity against the user-provided manifest and presence of certificates cannot establish genuine Autodata provenance**. The unavailable installer/registration components in part 0016 and absent proof of entitlement remain decisive blockers.

The only permitted next Windows execution gate is a *genuine rights-holder installer*, independent publisher verification (e.g. Windows Authenticode validation with appropriate trust policy), a valid license, and isolated compatibility testing. Do not substitute DLLs, bypass malware warnings, change license dates or execute untrusted activation/emulation components. The 81 verified `.IDF` files remain **not decoded**.

## Tests and change isolation

`test_original_pe_certificate_audit.py` provides **11 synthetic regression tests**: unsigned and PKCS#7-bearing PE32/PE32+, invalid certificate length, out-of-file offset, invalid PE, SHA256 mismatch, duplicate ZIP member, mandatory blocked-part refusal, blocked symlink refusal, and five-file aggregate evidence. These 11 tests passed locally with inert fixtures. The full 5-file audit was also executed against the owner-provided private originals (5/5 SHA256 matched, 4 PKCS#7 containers, 1 absent). Windows CI must be checked independently for the branch commit; CI uses only synthetic files.

The existing `original_installation_evidence_gate.py` was also corrected so that passing `--blocked-package` can **never override** the mandatory exclusion of `autodata_part_0016.zip`. An additional regression test enforces this.

**Status: ORIGINAL_EXECUTION=NOT_TESTED; AUTHENTICITY=NOT_PROVEN; LICENSE=NOT_PROVEN; IDF_DECODER=NOT_PROVEN.** This is a static evidence advance, not a functional repair.
