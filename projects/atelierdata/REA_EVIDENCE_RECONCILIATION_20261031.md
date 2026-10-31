# REA PE-import evidence reconciliation — 2026-10-31

Reprocessed the previously captured private REA 6.8.0 JSON report for AD BCD original executable (ADBCD.exe) from the user's Library archive REA_Autodata_Original_Static_Analysis.zip. The REA evidence reports source SHA256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 and size 18,102,272 bytes.

**Important:** This is an audit of the previously generated REA JSON, not a new execution of REA or Ghidra, and not a new byte-level SHA256 of the original PE. No original binary, private REA report, addresses, IDF bytes, or proprietary data were uploaded.

## Actual reconciliation of the private report

- Standard import table: 4 DLL descriptors and 17 imported functions; consistent with REA coverage.
- REA warning categories: unsupported_form=18, name_unreadable=17, thunk_unreadable=16, malformed_entry=1; total **52**.
- Declared delay-load directory: **1,104 bytes**, equivalent to 34 complete 32-byte descriptors plus 16 trailing bytes.
- REA recorded 17 partial delay rows: all 17 have nonstandard attributes and no readable DLL name.
- One REA row's descriptor index would place its 32-byte range beyond the directory's declared length. This is a **report/parser boundary concern**, not proof that Windows recognizes that descriptor.
- No valid delay-import functions or IDF decoder were demonstrated. The 52 warnings are not 52 imports; 17 partial rows are not 17 proven DLL dependencies.

## Implemented

rea_evidence_consistency.py validates the report's SHA256 provenance fields, IAT uniqueness, standard import counts, delay row bounds and warning categories, and emits aggregate-only JSON. Optional --source-pe additionally verifies the original SHA256 against the actual bytes and independently reconciles standard imports using pe_file_io_xrefs.py. Synthetic tests exercise tampering and byte-level cross-checking. No code from the original is executed.

Reproduce privately:

    python projects/atelierdata/rea_evidence_consistency.py --rea-report PRIVATE/rea-imports.json --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output PRIVATE/rea-summary.json

For independent source verification add --source-pe PRIVATE/ADBCD.exe. Keep all private source and detailed evidence outside public GitHub.

## Blocker

No real Ghidra disassembly of the private original was performed here. The file-loader and IDF format remain unknown; the original installer and valid license remain unverified. The Google Drive package 0016 stays blocked and must not be bypassed. The independent AtelierData application is not a proven 1:1 replacement.
