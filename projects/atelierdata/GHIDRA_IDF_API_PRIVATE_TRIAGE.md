# Private Ghidra IDF/file-API cross-reference triage

Scope: authorized, static interoperability analysis only. **Never execute**
the original executable, DLLs or installers. Do not bypass licensing/DRM,
do not attempt to retrieve the blocked part 0016, and do not publish private
binaries, .IDF bytes, addresses, full Ghidra reports, or license data.

The existing `tools/ghidra/AtelierData_IDF_Xrefs.py` scans for selected
ASCII/UTF-16LE IDF names and records Ghidra references and containing
functions. The new `tools/ghidra/AtelierData_File_API_Xrefs.py` separately
enumerates Ghidra symbols for file-access and dynamic-loader APIs, references
to their addresses, instruction mnemonics, and containing functions. Both
check the SHA256 that Ghidra reports for the **imported executable** against
the analyst's independently verified original hash before writing a report.

Run both scripts as **post-analysis scripts** in a private Ghidra project,
passing two arguments to each: an output path in private storage and the
independently verified original PE SHA256. Ghidra's `analyzeHeadless` supports
`-scriptPath` and repeated `-postScript` arguments. Use a local private
working directory, not the public repository or a public CI runner. These
scripts only inspect Ghidra's static database; they do not run the target.

Then use the **metadata-only** correlation step (from the project directory):

```text
python ghidra_idf_api_correlation.py --idf-private-report <private-idf-xrefs.json> --api-private-report <private-api-xrefs.json> --expected-sha256 <verified-sha256> --public-output <aggregate.json>
```

The correlation requires both private reports to declare the same source
SHA256, no target execution, and no proven decoder. It counts functions with
IDF string references, functions referencing API symbols, and their overlap.
Only aggregate counts and an explicit `idf_decoder_proven: false` go into the
public output. **Do not publish either input report.**

Important limitations: a reference to an IDF string is not a file read;
a reference to an API symbol is not necessarily a call; a function appearing
in both lists is not a decoder. Ghidra may omit IAT indirection, dynamically
resolved APIs, or indirect calls. This tool is triage for manual CFG and
decompiler review, **not** evidence of decoding or authorized use of the
original database. The new Ghidra script has not yet been run against the
private original in this development step. Only synthetic regression tests
are eligible for public CI.

Independent API documentation:
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/SymbolTable.html
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/ReferenceManager.html
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/address/Address.html
