# Original Autodata — Windows pathname gate (2026-10-31)

## Real private metadata checked

Read-only retrieval of `INVENTAR.txt` and `TRANSFER_FINALIZAT.txt` from the owner's Google Drive folder `Autodata_3_45_EXTRACTED`. The first contains 139 declared file sizes and relative paths. This iteration inspected **metadata only**: no ZIP content, original EXE, DLL, IDF or blocked package was opened or executed.

Aggregate findings from the actual inventory:

| Check | Result |
| --- | ---: |
| Declared files | 139 |
| Sum of declared file sizes | 2,323,704,957 bytes |
| Files named `.IDF` | 81 |
| Windows-invalid pathname components | 0 |
| Reserved Windows device names | 0 |
| Trailing dot/space pathname components | 0 |
| Case-insensitive/NFC pathname collisions | 0 |
| Relative paths above 240 UTF-16 code units | 0 |

This eliminates a **specific potential Windows extraction failure** (invalid/colliding paths) for the declared names. It does **not** prove extraction, binary safety, runtime compatibility, installer availability, or a valid license. Windows filename equality is more nuanced than Unicode casefold; the check is conservative and not an NTFS filesystem test.

The owner's `TRANSFER_FINALIZAT.txt` records the archive SHA256 as `e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da`; this iteration **did not rehash the RAR**. Previous full accessible-chunk SHA256 checks and their limitations are documented in `ORIGINAL_INSTALLATION_READINESS_20261031.md`.

## Concrete changes

- Added `original_windows_path_gate.py`: metadata-only TXT/JSON validator, aggregate JSON output, Windows filename checks, rejects accidental overwrite of the input. It never opens archive contents.
- Added 11 synthetic regression tests covering case collisions, path traversal, Windows device names, invalid characters, long paths, TXT/JSON parsing and output safety, and empty-inventory rejection.
- Fixed `original_archive_preflight.audit()` to **skip `autodata_part_0016.zip` unconditionally at the base reader layer**, including if the file appears on disk. This closes a gap where direct invocation of the lower-level preflight (as opposed to the stricter integrity gate) could otherwise have opened the malware-flagged package.
- Added a synthetic regression test with a deliberately invalid file named `autodata_part_0016.zip`, proving the reader reports it missing without calling `zipfile.ZipFile`.

## Reproduce with an authorized local inventory

```powershell
python projects/atelierdata/original_windows_path_gate.py --inventory C:\\PRIVATE\\INVENTAR.txt --output C:\\PRIVATE\\windows_path_report.json
python -m unittest discover -s projects/atelierdata -p "test_*.py" -v
```

**Status:** path compatibility confirmed for declared filenames; **original installation remains BLOCKED**. The unavailable flagged package contains installation/licensing-related files, and a legitimate installer and entitlement are still not independently authenticated. No DRM or license bypass was attempted; `.IDF` remains undecoded.
