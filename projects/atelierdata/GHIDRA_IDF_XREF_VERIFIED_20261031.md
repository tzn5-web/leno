# Verified Ghidra IDF cross-reference evidence gate — 2026-10-31

## Scope and observed status

This iteration adds an **actual static-analysis implementation and synthetic regression tests**, not a new finding about the proprietary IDF format. The SHA256-bound original analyzed in prior authorized runs is:

- `ADBCD.exe`: `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` (prior private evidence).
- REA v6.8.0: PE32 x86; 17 classic imports; 43 raw FF15/FF25 IAT candidates in prior independent scan; 52 uncertain delay-load observations, **not** validated imports.
- Ghidra 12.1.4: prior `-noanalysis` scan found `inflate 1.2.3` and `TFRMAUTODATABASE` literals without existing references; full auto-analysis previously timed out. Zero references without analysis **does not** mean zero code references.
- Earlier independent structural audit found the declared delay directory does not validate as standard descriptors.
- No loader, file-format grammar, IDF decoder, licensing mechanism, or legitimate installation has been established.

The connected Google Drive folder was reachable by metadata in this iteration, but direct search did not expose the original `ADBCD.exe` or `autodata_part_0001.zip` as downloadable items. **Neither REA nor Ghidra was rerun on the original during this iteration.** Original SHA256 above is previously verified evidence, not a newly recomputed hash. The blocked `autodata_part_0016.zip` was not accessed or bypassed.

## New implementation

- `tools/ghidra/AtelierData_IDF_Xrefs_Verified.java`: Ghidra Java post-script; requires the **original local PE**, its expected SHA256, and two distinct private/public report paths. It independently hashes the original PE and checks Ghidra's imported-program MD5 before scanning. It uses a **global 128 MiB initialized-memory scan cap**, bounded chunk overlap, at most 32 hits per literal/encoding, and counts existing Ghidra references and those originating inside recognized instructions. Private report retains addresses; public report includes only aggregate counts, provenance, coverage and explicit limitations. Input/output paths are canonicalized to prevent overwriting the PE.
- `projects/atelierdata/ghidra_idf_xref_verify.py`: independent validator. Rechecks the original PE SHA256, parses PE32 section mappings, verifies each Ghidra-reported literal at the corresponding original PE bytes, rejects duplicate/unmapped/tampered hits, validates private/public aggregate agreement and reference-count consistency. This **does not independently prove Ghidra disassembly or code flow**.
- `projects/atelierdata/test_ghidra_idf_xref_verify.py`: nine synthetic tests for positive evidence, tampered source, altered/unmapped addresses, falsified aggregates, inconsistent references, duplicate hits, false Ghidra identity and source safety contracts. These tests use only synthetic PE32 bytes and are discovered by the existing Windows workflow.

## Private reproduction

Import a locally authorized, SHA256-verified original PE into Ghidra. The Java script works in a `-noanalysis` project, but existing Ghidra reference counts can then be zero **because no disassembly exists**. If targeted/full analysis is available, reference counts become more informative. Never run the original program or bypass its licensing.

```powershell
$sha = 'a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4'
$exe = 'C:\\PRIVATE\\ADBCD.exe'
# Run the Java post-script in an authorized Ghidra project, with four script arguments:
# C:\\PRIVATE\\ADBCD.exe  <sha>  C:\\PRIVATE\\ghidra-idf-private.json  C:\\PRIVATE\\ghidra-idf-public.json
python projects/atelierdata/ghidra_idf_xref_verify.py --pe $exe --expected-sha256 $sha --private-ghidra C:\\PRIVATE\\ghidra-idf-private.json --public-ghidra C:\\PRIVATE\\ghidra-idf-public.json
python -m unittest discover -s projects/atelierdata -p 'test_ghidra_idf_xref_verify.py' -v
```

**Do not publish:** original PE/DLL/IDF bytes, private report addresses, Ghidra projects, proprietary strings or decompilation. The public aggregate is intentionally non-reconstructive; inspect it before sharing.

## CI and limitations

The workflow `.github/workflows/atelierdata-windows.yml` discovers `test_*.py`, runs application SQLite/GUI smoke tests, builds the Windows EXE, and tests the compiled executable. A new CI run must be inspected for this commit before marking Windows PASS. The Java script is **not** compiled or executed by those synthetic Python tests; its runtime behavior still requires an authorized Ghidra run on the original.

This task intentionally does not change the vehicle/procedure/schematic GUI modules owned by the parallel implementation task. A successful evidence gate is **not** an IDF decoder, a functional Autodata installation, or proof of equivalent catalog coverage.
