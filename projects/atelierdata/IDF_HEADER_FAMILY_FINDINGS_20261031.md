# IDF header-family evidence from private Drive audit (2026-10-31)

## Scope and provenance

This investigation reuses the **existing, privately stored** `static_analysis.csv` generated from the owner's authorized Autodata archive. The CSV contains the first at most 64 bytes per file and sample entropy, so it is **not** committed to this public repository. The CSV was fetched from the owner's Google Drive analysis folder using the authenticated Drive connector. Its SHA256 was checked before analysis:

`1a9831ffbb2a0d94f1ee51087ecfd97a622336358f75215f018efea82b50c0e7`

The CSV has 84 rows, of which 81 are categorized as `.IDF`. This run analyzed those 81 records with a new, bounded read-only parser. **It did not re-download or independently hash the 81 original IDF files**; those integrity checks are separate earlier work. It did not access blocked `autodata_part_0016.zip`, execute the original EXE, decode IDF, or inspect licensing.

## Direct measurements (actual private CSV, not synthetic data)

| Exact shared prefix | Groups with at least two IDF records | IDF records in those groups |
| --- | ---: | ---: |
| 4 bytes | 4 | 8 |
| 8 bytes | 3 | 6 |
| 16 bytes | 3 | 6 |
| 32 bytes | 1 | 2 |

All groups above consist of pairs. Of the 81 samples, 80 contain at least 32 bytes and one is shorter. The pre-existing CSV reports sample entropy at least 7.9 bits/byte for 75 of the 81 IDF records. This is **not evidence that they are encrypted**: compression, sample size and the data distribution can also influence entropy.

The exact 16-byte shared prefixes provide **reproducible candidates for further format-family comparison**. They do not prove a common container, record schema, checksum, key, decompressor or decoding mechanism. The report deliberately omits raw prefixes, file paths and original data.

Public machine-readable evidence: [IDF_HEADER_FAMILY_PUBLIC_20261031.json](IDF_HEADER_FAMILY_PUBLIC_20261031.json).

## New implementation

- [idf_header_family_audit.py](idf_header_family_audit.py) validates the SHA256 of the private input CSV, enforces bounds and strict hex/entropy fields, rejects duplicate private paths, computes exact prefix clusters and writes **only aggregates**.
- [test_idf_header_family_audit.py](test_idf_header_family_audit.py) uses synthetic CSV records to test clustering, privacy, bad hashes, malformed headers, duplicate paths, invalid entropy, missing IDF records and protection against overwriting private input.
- Local Python test run: **9/9 passed**. The tool was then run against the SHA256-verified Drive CSV and produced the aggregate JSON above. Windows CI is a separate verification and must be checked after the commits land.

Reproduction in an authorized private workspace:

```powershell
python projects/atelierdata/idf_header_family_audit.py --input-csv "C:\\PRIVATE\\static_analysis.csv" --expected-sha256 1a9831ffbb2a0d94f1ee51087ecfd97a622336358f75215f018efea82b50c0e7 --public-output "C:\\PRIVATE\\idf-header-family-public.json"
python -m unittest discover -s projects/atelierdata -p test_idf_header_family_audit.py -v
```

## Remaining blockers

Neither REA nor Ghidra was executed on the private PE in **this** iteration. Existing Ghidra scripts still need a real, privately authorized execution to verify candidate instruction boundaries and data-access xrefs. The original's legitimate installer and license remain unverified. There is no demonstrated IDF decoder or complete Autodata-equivalent catalog. Do not publish the original binary, the private CSV, its raw headers, or proprietary IDF files.
