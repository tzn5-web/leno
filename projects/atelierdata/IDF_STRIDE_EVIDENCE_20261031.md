# Verified fixed-stride IDF evidence (2026-10-31)

Scope: owner-supplied original archive in private storage; **static, read-only interoperability research**. No original executable or DLL was executed. No .IDF contents, byte motifs, license data, original executables or private Ghidra reports are committed.

## Direct measurements on private originals

The script `projects/atelierdata/idf_stride_evidence.py` was **executed locally** against `INVENTAR.json` and the original ZIP packages 0001–0002. Before any pattern measurement, the **entire first ZIP chunk** of each selected IDF was streamed and SHA256-checked against the manifest. It inspected only the first 262,144 bytes of each verified file and sought contiguous runs of an identical eight-byte motif at fixed strides between 12 and 128 bytes.

| Original file | SHA256 gate | Dominant eight-byte motif occurrences | Stride | First / last observed motif offsets |
| --- | --- | ---: | ---: | --- |
| `COMMON/SGOPS.IDF` | PASS (51,464,668 bytes) | 960 | 21 bytes | 214,368 / 234,507 |
| `COMMON/SGINT.IDF` | PASS (31,956,465 bytes) | 960 | 21 bytes | 214,368 / 234,507 |
| `COMMON/FAS.IDF` | PASS (3,381,989 bytes) | 870 | 19 bytes | 22,534 / 39,045 |

**Cross-file observation:** the dominant eight-byte motif is identical in `SGOPS.IDF` and `SGINT.IDF`, at the same observed offsets. Only a Boolean indicating this equality is exported; **the actual eight-byte value is never serialized**.

These repeated fixed-stride regions are evidence of nonrandom repeated byte structure. They **do not prove** a specific IDF record schema, cipher, compression method, key, loader, semantic content or decoder. Identical bytes could be repeated metadata, padding, templates or another mechanism. No vehicle, procedure, diagram or technical value was extracted.

The standalone program produces only an aggregate JSON. It does not reconstruct the full IDF, unpack to disk, invoke the original software or attempt DRM/license operations.

Reproduce **only on an authorized private copy** (do not commit the inputs or outputs containing private paths):

```powershell
python projects/atelierdata/idf_stride_evidence.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE --output C:\PRIVATE\idf_stride_aggregate.json
python -m unittest discover -s projects/atelierdata -p test_idf_stride_evidence.py -v
```

## Test and Ghidra boundaries

Six synthetic tests were executed locally: **6/6 PASS**, including SHA256 mismatch rejection, missing archive, zero-byte repetitive false positive, 19- and 21-byte stride fixtures, cross-file comparison and absence of motif bytes from the aggregate report. The tests are added to Windows CI discovery, but **the new GitHub Actions run must be checked before claiming Windows PASS**.

`tools/ghidra/AtelierData_LoadLibrary_Argument_Check.java` was extended with a bounded traversal of Ghidra's direct-call graph from its declared entry-point functions, and a per-candidate static membership flag. Ghidra's `Function.getCalledFunctions(TaskMonitor)` API enumerates **known static calls only**; it cannot establish execution of indirect, delayed or dynamically resolved paths. The new Java script **was not executed against the private original in this run**, so no reachability counts are claimed.

**Next evidence gate:** run headless Ghidra against the private SHA256-verified `ADBCD.exe`, enable full autoanalysis, then execute the updated script with the private JSON candidate report. Validate which loader callsites belong to actual analyzed functions and which are in the bounded direct-call graph; only then investigate authorized file-open API cross-references. Keep every private binary and detailed report out of the public repository.
