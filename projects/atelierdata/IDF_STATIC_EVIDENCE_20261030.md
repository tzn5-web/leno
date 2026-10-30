# Autodata IDF: reproducible static evidence (2026-10-30)

This investigation uses the **original private** `ADBCD.exe`, `autodata_part_0001.zip`, `autodata_part_0004.zip` and private `INVENTAR.json`. Original bytes remain outside this public repository. The program was **never executed**. The checked inputs do **not** include blocked `part_0016`.

The published `idf_static_evidence.py` script ran locally with explicit manifest SHA256 verification and a 64 MiB per-entry bound. Result: **57 distinct, complete .IDF files** from the two available ZIP packages passed SHA256 verification against their exact inventory ZIP entries. The full inventory lists **81 .IDF files**; 24 were not inspected in this run. Do not interpret 57 as all 139 files of the archive.

## Findings, not format claims

- For 49/57 IDF samples, **each** of the three 64 KiB windows (start/middle/end) has Shannon entropy at least 7.95 bits/byte. This is consistent with compressed or encrypted data and does **not** establish either.
- Several files have lower/variable entropy, including `FAS.IDF` (approx. 7.35–7.53), `TECDOC.IDF` (approx. 7.44–8.00), `SGINT.IDF` (approx. 7.72 at start, near 8 later), and `MIDTDoc.IDF` (approx. 7.72–7.99). Thus **not all IDF files have uniform statistical behavior**.
- `CONST.IDF` is only 10 bytes. Its entropy is not meaningful evidence of encryption.
- SHA256 of the inspected original `ADBCD.exe` is `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` (verified). A bounded literal scan found **zero exact ASCII/UTF-16LE occurrences** of `.IDF`, `MODELS.IDF`, `CONST.IDF`, `CSS.IDF` or `DTC.IDF` in that executable. Dynamic name construction, resources, other modules and indirect loaders remain possible.
- The executable contains `inflate 1.2.3` (ASCII file offset `0x6bedf1`) and `TFRMAUTODATABASE` (UTF-16LE file offset `0xa832a8`). These are leads for static xref inspection, **not** proof that IDF uses zlib, or that a Delphi form implements the loader.

## Reproducibility and status

- Tool: `projects/atelierdata/idf_static_evidence.py`, including a synthetic-data self-test that deliberately rejects a wrong SHA256.
- Private execution: 57 verified samples, 0 skipped for the configured size bound, output retained as private report `AtelierData_IDF_Static_Evidence_ALL_Available_20261030.json` in the conversation environment, **not uploaded to GitHub**.
- Ghidra 12.1.4: the **Java** script `tools/ghidra/AtelierData_IDF_Xrefs.java` was executed headlessly on the original SHA256-verified `ADBCD.exe` with `-noanalysis`, returning PASS and a private JSON report. The program was identified as x86:LE:32:default. `inflate 1.2.3` was located at memory address `00ac01f1` and `TFRMAUTODATABASE` at `00f170a8`. No existing xrefs were recorded in this no-analysis run. A full autoanalysis attempt timed out with decompiler/resource warnings, so a working loader call chain is **not** established.
- REA 6.8.0 `inspect-pe-resources` was also **actually executed** on the same SHA256-verified original PE. It returned complete resource-directory coverage: **1,299 directory entries and 644 resources**, including 190 RT_RCDATA (type 10), 337 RT_BITMAP (type 2), 65 RT_STRING (type 6), and 6 named `UNICODEDATA` entries. Named form resources include `TAUTODATAFORM`, `TFRMAUTODATABASE` and `TTECHDATAFORM`, consistent with Delphi/VCL form metadata. This identifies UI/resource structure, **not** the IDF loader or its encoding. The detailed resource inventory remains private. REA does not currently decode the IDF format.

**Status:** IDF decoder not proven. No vehicle data, repair procedure, wiring diagram, or proprietary content has been extracted. Next investigation should focus on the static loader/xref chain with private Ghidra evidence and an authorized export or format specification. Never bypass license checks or publish original files.
