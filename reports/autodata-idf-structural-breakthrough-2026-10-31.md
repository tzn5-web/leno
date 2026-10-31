# Autodata 3.45 — static IDF structure evidence (2026-10-31)

**Scope:** Original archive, not AtelierData/new application. The source executable was **never run**. The 0016 ZIP blocked by Google Drive was **not bypassed or downloaded**. Only derived metadata and reproducible code are published; no proprietary binary payloads are committed.

## Exact original input

- `autodata_part_0001.zip`: `ADCDA2/COMMON/SGINT.IDF`, `FAS.IDF`, `MIDS.IDF`, `MIDTDoc.IDF`, `MIDLINKS.IDF`, `RTINCJOB.IDF`, and `ADBCD.exe`.
- `autodata_part_0002.zip`: `ADCDA2/COMMON/SGOPS.IDF`.
- `autodata_part_0004.zip`: technical English IDF files and supplementary data.
- The local analysis used read-only ZIP APIs to sample binary entries without launching the EXE.

## Finding 1: SGINT and SGOPS share a 21-byte-wide table region

For exactly **19,658** consecutive 21-byte rows (**412,818 bytes**) at the start of each file:

| Candidate field | Observed width | Direct evidence |
|---|---:|---|
| First region of every row | 8 bytes | Exact byte-for-byte equality between the corresponding SGINT and SGOPS rows in **19,658 / 19,658** cases |
| Second region of every row | 13 bytes | Different in 19,657/19,658 paired rows; **996 / 255,554** bytes equal (0.003897415), close to chance 1/256 |
| Common 8-byte value count | 178 distinct | Same set and row order in the two source files |
| Region boundary | 412,818 | First 8-byte field mismatch is exactly at the next 21-byte-row start (offset 412,818, i.e. 19,658 × 21) |

Byte equality at lag 21 in 64 KiB windows: SGINT starts at **0.379944** (offset 0), **0.379562** (offset 262144), and falls to **0.003801** starting exactly at offset **412818**. SGOPS shows **0.380279**, **0.379684**, and **0.004243** respectively. This identifies an **empirical fixed-width section boundary**, not a complete file format or semantic schema.

**Do not assume:** 8-byte field = an automotive model ID, 13-byte field = a decoded technical value, or any particular encryption algorithm. These are observed byte regions only.

## Finding 2: other IDF files have different candidate widths

Observed consecutive-byte autocorrelation (matching at offset + lag), using first 128 KiB of individual files:

| Logical file | Candidate lag | Matching byte fraction | Notes |
|---|---:|---:|---|
| `COMMON/FAS.IDF` | 19 | 0.420784 | First 8 residue positions show ~0.994 equality to next row; remaining positions ~0.004 |
| `COMMON/MIDS.IDF` | 17 | 0.359414 | First 8 residue positions show ~0.759 equality to next row; remaining positions ~0.004 |
| `COMMON/MIDTDoc.IDF` | 17 | 0.329739 | First 8 residue positions show ~0.697 equality to next row; remaining positions ~0.004 |
| `COMMON/SGINT.IDF` | 21 | ~0.380 | See bounded table evidence above |
| `COMMON/SGOPS.IDF` | 21 | ~0.380 | See bounded table evidence above |

For the first 131,072 bytes, the 8-byte candidate fields from `MIDS` and `MIDTDoc` have **1,557 common distinct values** (MIDS: 1,868; MIDTDoc: 2,349). This is evidence of a shared *byte-token vocabulary*, not a verified key format. Other files tested show near-random autocorrelation for these candidate lags.

These are **candidate regions**, not guaranteed record lengths across the complete files.

## Finding 3: static ADBCD.exe evidence

PE32 Windows (x86) executable, **18,102,272 bytes**, SHA-256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` (matched the original manifest's recorded hash when streamed from ZIP 0001). Static byte-string inspection shows:

- `inflate 1.2.3` (file offset 7,073,265) and `incorrect header check` (offset 7,072,588).
- `CreateFileA`, `ReadFile`, `GetProcAddress` names appear in import/name data.
- Literal `.IDF`, `TDGRAPH.IDF`, `MODELS.IDF`, and `COMMON` were **not found in raw ASCII/UTF-16LE scans**.

This justifies investigation of decompression routines and file-reading call sites in static Ghidra analysis. It does **not** prove the IDF content is zlib or locate the actual loader/decryptor. The source executable has not been run.

## Reproducibility

- `tools/autodata_idf_similarity_audit.py` — sample pair comparison and PE string offsets.
- `tools/autodata_idf_record_probe.py` — formally checks 19,658 × 21 region, 8-byte field agreement, distinct values and post-boundary lag.
- `tools/autodata_idf_periodicity_audit.py` — compares candidate periods 17,19,21 and residue positions across available files.
- `tests/test_autodata_idf_record_probe.py` — synthetic fixture test; CI configuration includes it, but CI PASS is not asserted until confirmed.
- No original executable launches, dangerous-archive reshares, bypass tools, or AWS/Azure resources.

## Next engineering gates

1. Run the 21-byte field check on an independent permitted copy of ZIPs 0001 and 0002; confirm boundary and values on a second interpreter/runtime.
2. Trace only **static** file reading and transform functions in `ADBCD.exe` with Ghidra, following name resolution/import callsites and zlib references. Never use `Run`, debugger, emulator or execute original contents.
3. Look for independently checkable relationships between 8-byte tokens and known XML/text data without presuming the token encodes a particular label.
4. Define a `Kaitai Struct` record layout only for the verified **table region**, not the full IDF format; an 8+13 structure may be documented as opaque bytes until semantics are proven.
5. Gate any decoder claim on cross-file parsing, known-value validation and explicit false-positive checks.

**Result:** Real structural decoding progress; no plaintext extraction or complete Autodata runtime yet.
