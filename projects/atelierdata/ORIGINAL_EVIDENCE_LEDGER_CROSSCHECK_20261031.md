# AtelierData — original distribution evidence reconciliation (2026-10-31)

## Verified scope

This report cross-checks owner-provided **private Google Drive audit records** against the SHA256 inventory. No original executables, installers, drivers, keys, proprietary `.IDF` bytes or blocked ZIP were downloaded into the public repository, executed, extracted, or published. The records were inspected in a private analysis context. The public Python implementation and its tests use synthetic fixtures only.

Source records (kept in Drive): `INVENTAR.json`, `manifest_vs_actual.csv`, `download_hashes.csv`, and `download_failures.json`. Manifest SHA256, independently computed on the currently accessible copy: `ec867e0fae97523caff4677e7684b03a2e30832856de67239861986221a804ca`.

## Actual reconciliation

| Cross-check | Observed |
| --- | ---: |
| Manifest files / package names / chunks | 139 / 16 / 163 |
| Download-hash ledger rows | 16 (manifest + 15 ZIPs) |
| Reconstruction CSV rows | 139, no duplicate identity |
| Records marked PASS and structurally consistent | 100 |
| Unavailable records | 39, all in blocked package 0016 |
| `.IDF` PASS records | 81 |
| PASS files with a **single** manifest chunk, reconstructed SHA256 equal to manifest chunk SHA256 | 92 |
| PASS files with multiple chunks, reconstructed whole-file SHA256 **not directly comparable** with the per-chunk manifest hashes | 8 |
| Metadata inconsistencies in this cross-check | 0 |
| Original bytes freshly SHA256-rehashed by this cross-check | 0 |

The 8 multi-chunk files are **not** claimed as cryptographically reverified by this CSV-only tool. Earlier direct ZIP/chunk audits recorded 124/124 available chunks passing SHA256; those results are separate evidence and are not silently promoted into a new hash check.

The Google Drive folder currently lists 16 ZIPs. Their reported aggregate compressed size is 2,323,731,093 bytes, of which 51,956,344 bytes belong to the blocked `autodata_part_0016.zip`. The Drive metadata field `can_download=true` on that item is **not** evidence of safe or successful retrieval: the private `download_failures.json` records a provider-side `403 cannotDownloadAbusiveFile`. No bypass was attempted.

## Code changes

- `original_evidence_ledger_crosscheck.py`: validates manifest identity, audit row uniqueness and coverage, status/size/chunk counts, single-chunk digest agreement, unavailable-file classifications, and a hard exclusion of the blocked package from the download ledger. Reports only aggregate counts and refuses to overwrite input evidence.
- `test_original_evidence_ledger_crosscheck.py`: synthetic tampering, blocked-package, missing-row, wrong-hash, and multi-chunk tests.
- `original_runtime_dependency_audit.py`: refuses the blocked package **before any filesystem probe** in the direct PE reader.
- `original_installation_readiness.py`: excludes the blocked package from all availability calculations even if a caller supplies it as available or a local file appears.
- `test_original_blocked_package_boundary.py`: regression tests proving that the blocked package is never probed by the three audit paths.

## Limits and decision

**Original Windows installation: NOT VERIFIED / NOT READY.** All available `.IDF` records are consistent, but the authentic installer and license have not been verified. The flagged package is not a repair source. An authentic licensed vendor distribution and compatibility evidence are needed for an authorized isolated Windows startup test. No `.IDF` decoder is claimed, and this work does not alter licensing or DRM.

The separate AtelierData Windows application remains the supported development path. This iteration changed only original-distribution audit and evidence files, not the REA/Ghidra or procedures/schematics components owned by the other work streams.

Reproduction using owner-authorized **private** copies (never check input files into public GitHub):

```powershell
python projects/atelierdata/original_evidence_ledger_crosscheck.py --manifest C:\PRIVATE\INVENTAR.json --reconstruction-csv C:\PRIVATE\manifest_vs_actual.csv --downloads-csv C:\PRIVATE\download_hashes.csv --output C:\PRIVATE\ledger-report.json
python -m unittest discover -s projects/atelierdata -p 'test_*.py' -v
```

CI status must be checked at the exact commit/run; a source commit alone is not proof of Windows test success.
