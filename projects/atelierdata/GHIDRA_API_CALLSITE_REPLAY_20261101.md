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

## 2026-11-01 — independent .IDF literal provenance gate

The replay now independently verifies the **literal bytes** of reported ASCII
or UTF-16LE `.IDF` strings at the virtual addresses supplied by the private
Ghidra IDF-xref report. The PE32 RVA must map uniquely to initialized,
file-backed section bytes and the expected literal must match exactly.
Missing addresses, unmapped locations and mismatched bytes do not contribute
to the `matching_api_sites_in_idf_string_referencing_functions` count.

The public aggregate includes:
`idf_literal_hits_verified_against_source_pe`,
`idf_literal_hits_missing_address`, and
`idf_literal_hits_unmapped_or_mismatched`. It exposes neither literal names
nor addresses. Four new synthetic tests exercise missing, mismatched,
unmapped and UTF-16LE literal evidence; the synthetic PE fixture also contains
an explicit ASCII .IDF literal at its reported address.

**Important:** a verified literal is not a verified code xref, and a
Ghidra-reported containing function is not independently proven by this gate.
Neither the loader nor any .IDF record format is identified. This change
must be run on a privately held, SHA256-verified original before it can
support any original-specific conclusion. CI runs synthetic fixtures only.


## Additional independently checked IDF xref operand candidates (2026-11-01)

The static replay now reports two separate **aggregate-only** counters:
`idf_xrefs_with_raw_push_or_mov_literal_va` counts unique PE32 source/literal
pairs where a Ghidra-reported string xref starts in a file-backed executable
section and the raw bytes match `PUSH imm32` or `MOV r32, imm32` with the
exact verified .IDF literal VA. `matching_api_sites_in_idf_raw_pointer_functions`
counts corroborated IAT callsites in functions also associated with one of
those narrow raw pointer candidates.

These are **byte-pattern corroborations**, not independent disassembly,
instruction boundaries, reachable call graphs, a proven IDF loader or decoder.
Other valid addressing modes are intentionally omitted; a zero count is not
proof that no IDF references exist. The original Ghidra-reported shared-function
counter remains separate and is not upgraded to independent evidence.
Synthetic tests cover a matching operand, a wrong operand, a non-executable
source, duplicate reports and redaction. No private input is used in CI.


## Ghidra IDF data-xref instruction evidence tier (2026-11-01)

The private `AtelierData_IDF_Xrefs.py` exporter now records, for each IDF
string xref, its Ghidra reference type, whether it is a data reference, and
the exact instruction start address, byte length and mnemonic (if Ghidra
recognizes an instruction at that source). These fields stay in the **private**
Ghidra report. The original executable is never executed by the script.

The offline replay adds two aggregate-only fields:
`idf_xrefs_with_ghidra_boundary_and_raw_pointer` and
`matching_api_sites_in_ghidra_idf_pointer_functions`. A candidate contributes
to this stricter tier only when its independently checked raw PE bytes match
a five-byte x86 `PUSH imm32` or `MOV reg, imm32` targeting a verified IDF
literal, **and** the private Ghidra report explicitly says the xref is a data
reference from a five-byte instruction beginning at the same source address
with the matching mnemonic. Older reports without these fields contribute
zero to the new tier; the legacy raw-byte candidate count remains separate.

These counters are *Ghidra-boundary-supported candidates*, not independently
decompiled instructions, verified control-flow paths or an IDF decoder.
Synthetic-only tests exercise valid PUSH/MOV evidence and reject missing,
contradictory or off-by-one instruction metadata. No original-specific result
is claimed until the updated scripts are run against the privately held,
independently SHA256-verified original and reviewed.
