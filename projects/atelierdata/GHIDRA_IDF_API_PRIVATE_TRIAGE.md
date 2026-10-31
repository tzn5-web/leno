# Private Ghidra IDF/file-API cross-reference triage

Scope: authorized, static interoperability analysis only. **Never execute**
the original executable, DLLs or installers. Do not bypass licensing/DRM,
do not attempt to retrieve the blocked part 0016, and do not publish private
binaries, .IDF bytes, addresses, full Ghidra reports, or license data.

The existing `tools/ghidra/AtelierData_IDF_Xrefs.py` scans for selected
ASCII/UTF-16LE IDF names and records Ghidra references and containing
functions. The updated `tools/ghidra/AtelierData_File_API_Xrefs.py` enumerates Ghidra
symbols for file-access and dynamic-loader APIs, including `__imp_` and
stdcall-decorated aliases. It records references, mnemonics and containing
functions. The IDF script checks the imported-program SHA256 against the
analyst's independently verified hash. The API script additionally reads
the **local original PE** in bounded read-only mode, verifies its SHA256,
and compares Ghidra's **reported** imported-program SHA256 and MD5 with
those of that file. These are Ghidra import metadata checks, not an
independent reconstruction of all mapped bytes or proof of a loader/decoder.

Run both scripts as **post-analysis scripts** in a private Ghidra project,
passing two arguments to `AtelierData_IDF_Xrefs.py`: the private output
path and independently verified original PE SHA256. The API script requires
**three** arguments: the local original PE path, expected SHA256, and private
output path, in that order. Ghidra's `analyzeHeadless` supports
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
original database. The updated Ghidra API script has not yet been run against the
private original in this development step. Only synthetic regression tests
are eligible for public CI.

Independent API documentation:
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/SymbolTable.html
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/symbol/ReferenceManager.html
- https://ghidra.re/ghidra_docs/api/ghidra/program/model/address/Address.html

Validation note (2026-10-31): `test_ghidra_file_api_contract.py` tests the
actual import-name normalization function and checks the source's safety
gates with synthetic inputs. These tests cannot substitute for Ghidra
headless execution or establish that the original `.IDF` format is decoded.
