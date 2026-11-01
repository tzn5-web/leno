# AtelierData — PE32 source replay of private Ghidra API xrefs (2026-11-01)

## Implemented

`ghidra_api_callsite_replay.py` is a read-only, SHA256-gated independent
check of **reported** Ghidra API-reference sites against the exact original
PE32 bytes. It first validates the two private Ghidra reports with the existing
`ghidra_idf_api_correlation.correlate` gate. It then maps each reported flow
source to an unambiguous file-backed executable section and checks for the
six-byte x86 `FF 15` (indirect CALL) or `FF 25` (indirect JMP) form.
The embedded LE32 operand must identify a PE import-table slot whose imported
symbol equals the API name in the report. A reported CALL/JUMP type must agree
with the raw opcode. Repeated sites are counted once.

The public JSON contains **only aggregate counts** and coverage flags. It
does not contain original bytes, offsets, addresses, names of original DLLs,
proprietary strings, or IDF content. The PE and both Ghidra reports must remain
in the authorized private environment.

## Private invocation (only after actual Ghidra reports exist)

```powershell
python projects/atelierdata/ghidra_api_callsite_replay.py `
  --pe C:\PRIVATE\ADBCD.exe `
  --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 `
  --idf-private-report C:\PRIVATE\idf-xrefs-private.json `
  --api-private-report C:\PRIVATE\file-api-xrefs-private.json `
  --public-output C:\PRIVATE\api-callsite-aggregate.json
```

The two private reports are produced by
`tools/ghidra/AtelierData_IDF_Xrefs.py` and
`tools/ghidra/AtelierData_File_API_Xrefs.py`, respectively, when run on the
same SHA256-verified imported program. They have **not** been generated on the
original in this update.

Eight synthetic-only regression tests cover matching and mismatched import
names, shared and distinct IDF-string functions, DATA/mnemonic-only
references, unmapped sites, conflicting CALL/JUMP opcodes, SHA256 and claimed
identity checks, duplicate sites and report immutability. Windows CI discovers
`test_ghidra_api_callsite_replay.py` automatically.

## Evidence boundary

This is **byte-pattern corroboration, not instruction-boundary verification**.
A raw `FF 15` sequence could be embedded data; no CFG reachability is proven.
Valid file I/O through dynamic imports, runtime wrappers, thunks, registers,
or different instruction encodings may yield zero matches. In particular,
the original's classic import table did not expose `ReadFile` in earlier
verified triage, so this tool cannot establish its dynamic file reader.

The previously documented original `ADBCD.exe` SHA256 is an expected value
for future private verification, **not a freshly recalculated original hash
in this update**. No original PE, DLL, IDF or blocked `part_0016` package was
read, run, published or bypassed in this implementation.

No .IDF record format, decoder, decryption, protected content extraction, or
right to use proprietary data has been demonstrated.
