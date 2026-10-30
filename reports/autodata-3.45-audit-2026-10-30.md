# Audit Autodata 3.45 — 2026-10-30

## Scope

The subject is the user's **original Autodata 3.45 archive**, distributed for static analysis as 16 ZIP files. This is **not** a new AtelierData application. GitHub holds analysis code, Google Drive holds source material and reports, and Colab runs only when started by the user. **No Azure.**

## Evidence audited

- Google Drive source folder: https://drive.google.com/drive/folders/1XqpDaYI5zkdUXY85wLSvpsklatT0P0Bd
- Drive folder listing at audit time: 21 entries (16 numbered ZIPs, INVENTAR.json, INVENTAR.txt, listare_7z.txt, TRANSFER_FINALIZAT.txt, Autodata_OneClick_Audit folder).
- All 16 names, autodata_part_0001.zip to autodata_part_0016.zip, were present; 16 unique nonzero-size ZIPs. Drive metadata size sum: **2,323,731,093 bytes**. This is a metadata check, **not a content hash check**.
- INVENTAR.json: **139 logical files**, **163 ZIP entries/chunks**, **2,323,704,957 extracted bytes**, **16 package names**, without duplicate manifest file paths, duplicate chunk references, invalid relative paths, declared-size mismatches or incorrect chunk order.
- Extensions: **81 .IDF**, **17 .exe**, **9 .dll**, **6 .reg**, **4 .cmd**, **2 .bat**, **1 .vbs**, with other text, XML, image, help, document and metadata files. The 81 .IDF are distributed as COMMON 32, ENG 31, GRAPHICS 18.
- Original RAR SHA-256 shown by manifest: `e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da`. **This is an unverified declaration**; ZIP metadata cannot prove the RAR's hash.

## Access and security

- `Autodata_OneClick_Audit/SOURCE_ACCESS_STATUS.json` reports a prior provider rejection for `autodata_part_0016.zip`: HTTP **403**, `cannotDownloadAbusiveFile`, text: "This file has been identified as malware or spam and cannot be downloaded." Do not retry with abuse acknowledgements, mirror the blocked package or evade provider malware protections.
- Original EXE/DLL/keygen/activator/emulator/installers/scripts are never executed. Files with active content are hashed/inventoried rather than interpreted or launched.
- No conclusions about IDF internals can be drawn from names alone, even for files whose names contain GRAPH/TD/WD.

## GitHub code review and changes

Branch: `autodata-colab-20261030`.

1. Notebook `notebooks/autodata_3_45_static_audit.ipynb` retains the fixed Drive API `pageSize` parameter (not the invalid `page_size`).
2. The known provider-blocked part 0016 is explicitly skipped. Other downloads are attempted only via normal authenticated Drive access; partial files are discarded and their size is checked against Drive metadata.
3. A **manifest-only structural audit** was added so useful evidence is available despite blocked ZIPs.
4. Reports include `manifest_structural_audit.json` and `manifest_structural_errors.csv`; report uploads update existing file names instead of endlessly duplicating them.
5. A self-contained synthetic test `tests/test_autodata_static_notebook.py` and GitHub Actions workflow `.github/workflows/autodata-static-audit-tests.yml` were added. This test is intended to detect syntax errors, bad chunk hashes and regressions using **synthetic** files, not original executable content.

## Status and acceptance criteria

| Gate | State | Pass requirement |
|---|---|---|
| Drive listing metadata | PASS | 16 unique nonempty ZIP names present |
| Manifest internal consistency | PASS | Counts, sizes, chunk order and references consistent |
| Original RAR byte-for-byte SHA256 | NOT VERIFIED | Actual original archive independently hashed if legitimately accessible |
| Raw ZIP contents | NOT VERIFIED | Ordinary downloads and chunk SHA256 comparisons on each accessible ZIP |
| Known-blocked part 0016 | BLOCKED | Preserve explicit provider refusal; do not bypass |
| Notebook publication and readback | PASS | Notebook exists at exact GitHub branch/path |
| Notebook execution with real Drive data | NOT VERIFIED | User starts Colab Run all and reports are written |
| Automated synthetic CI result | NOT VERIFIED | Passing GitHub Actions job; workflow exists but no successful run confirmed |
| IDF structure decoded | NOT ESTABLISHED | Independent repeatable parser proof on accessible sample data |
| Windows application outcome | OUT OF SCOPE | This phase targets the original archive, not an app build |

## Next execution

Notebook: https://colab.research.google.com/github/tzn5-web/leno/blob/autodata-colab-20261030/notebooks/autodata_3_45_static_audit.ipynb

The next **user-initiated** action is to open a fresh notebook version, authenticate Drive and select **Runtime → Run all**. Reports should be written to an `Autodata_3_45_ANALYSIS` folder (created in the source folder when allowed, otherwise in My Drive). After the first complete report, prioritize accessible COMMON/ENG IDF headers and safely parsed XML, then develop documented hypotheses and tests without asserting undocumented format semantics.

This report distinguishes manifest validation from byte verification and records the known provider block rather than working around it.
