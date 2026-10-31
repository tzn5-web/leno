# Autodata 3.45 — IDF cross-index and PE static inspection (31 October 2026)

## Scope and evidence

This is analysis of the **original** Autodata 3.45 archive. No new application is being built. Original EXE/DLL/keygen/BAT/CMD files were **never run**. No Google Drive malware-block override was used and part `0016` was not fetched. Source material remains outside GitHub.

Verified local inputs (already hash checked against `INVENTAR.json` in prior audit):
- `autodata_part_0001.zip`: `COMMON/FAS.IDF`, `MIDS.IDF`, `MIDTDoc.IDF`, `SGINT.IDF`, `ADBCD.exe`;
- `autodata_part_0002.zip`: `COMMON/SGOPS.IDF`.

## Newly measured opaque record-prefix relationships

| File | Candidate row width | Candidate prefix rows | Candidate prefix bytes | Distinct 8-byte values |
|---|---:|---:|---:|---:|
| COMMON/FAS.IDF | 19 | 29,100 | 552,900 | 180 |
| COMMON/MIDS.IDF | 17 | 21,571 | 366,707 | 5,031 |
| COMMON/MIDTDoc.IDF | 17 | 15,927 | 270,759 | 4,773 |
| COMMON/SGINT.IDF | 21 | 19,658 | 412,818 | 178 |
| COMMON/SGOPS.IDF | 21 | 19,658 | 412,818 | 178 |

Method: from each candidate record, compare the first 8 bytes with the next record's first 8 bytes, identify the last equality before at least 1,024 consecutive adjacent nonmatches, and group contiguous identical 8-byte values. This is an **empirical prefix segmentation**; exact format boundaries and key semantics remain unproven, except stronger 21-byte SGINT/SGOPS *pair agreement* from prior audit.

### Confirmed joins

**MIDS.IDF ↔ MIDTDoc.IDF**
- 4,059 **identical** 8-byte values across the two candidate prefixes, which appear in the **same exact ordering** (no inversion in the 4,059 shared values).
- 972 values occur only in the candidate MIDS region; 714 only in MIDTDoc.
- Pearson correlation of corresponding shared group sizes: **0.90876436** (not the same as Spearman).
- Comparing the 9-byte record payloads at shared-group matching row positions: 14,344 compared rows; **527 identical bytes out of 129,096** (0.00408223); no whole 9-byte paired payload matched. This is near the 1/256 chance rate and **does not** establish shared plaintext payloads, decryption or meaning.

**SGINT.IDF ↔ SGOPS.IDF**
- 178 shared opaque values, in identical order, same group sizes: group-size Pearson **1.0**.
- 19,658 paired 21-byte rows have exactly the same initial 8 bytes; the following 13 bytes differ almost completely.
- The 178 values appear in 178 contiguous runs; no value is seen returning in a different run within that region.

**Negative controls**
- FAS vs MIDS: 0 shared opaque 8-byte values.
- MIDS vs SGINT: 0 shared opaque 8-byte values.
- Ordering is **not applicable**, rather than 'true', when zero shared values exist.

These are strong evidence for shared *internal indexing* between some datasets, but not proof of a particular vehicle/model or technical field schema.

## Static inspection of ADBCD.exe — concrete blocker

- Original executable is **PE32 x86**, 18,102,272 bytes, SHA-256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
- 13 PE sections, primarily numerically named, PE entrypoint RVA **0xE6B2EF**.
- Import directory has **17 named imports** from KERNEL32, USER32, ADVAPI32 and MSVCRT.
- `GetProcAddress` and `LoadLibraryA` are among imports. `ReadFile` and `CreateFileA` are **not** in the static import table, but **their string names are present** in the large internal API-name table in section `0000013`:
  - `CreateFileA`: raw offset **16,555,708**, RVA **17,172,156**.
  - `ReadFile`: raw offset **16,555,822**, RVA **17,172,270** (the `ReadFileEx` string follows).
- zlib-like strings are in a **different** PE section `0000003`:
  - `incorrect header check` raw offset **7,072,588**;
  - `inflate 1.2.3` raw offset **7,073,265**.
- No literal ASCII `.IDF`, `MODELS.IDF` or `TDGRAPH.IDF` was found anywhere in the PE file. This **does not** prove absence of IDF loader code: file names can be built dynamically, stored as data, encoded, or handled by another module.
- The entrypoint region contains code that is difficult to follow through a straightforward linear disassembly. Do not assume a particular packer/obfuscator family from this alone.
- Presence of zlib strings **does not establish** that an IDF is compressed using zlib. The relationship to the load/decode pathway is not traced.

## Reproducibility and tests

- `tools/autodata_idf_cross_index.py`: aggregate-only static analysis, requiring only normally accessible ZIP parts 0001 and 0002.
- `tests/test_autodata_idf_cross_index.py`: synthetic ZIP fixtures, shared-group and negative-control tests.
- `tools/autodata_pe_static_audit.py`: PE32 sections/import/string offsets without executing the target.
- Synthetic local tests of the IDF join code: **PASS**. Published workflow has been extended; **do not call GitHub Actions PASS until a corresponding run result is confirmed**.
- The raw 8-byte tokens, raw PE binary and unknown proprietary IDF payloads are not committed.

## Next technical gate

The next meaningful gate is **static cross-referencing** inside Ghidra (or equivalent) from the internal API-name table / `GetProcAddress` load path and zlib references to an IDF file-open and read routine. Identify a verified data-transformation step before claiming any decoded technical value. Until then, keep the 17/19/21-byte prefixes as opaque record data with reproducible joins. Do **not** run, emulate or debug original binaries.
