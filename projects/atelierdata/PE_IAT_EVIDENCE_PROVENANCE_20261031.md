# AtelierData — PE IAT evidence provenance and Ghidra cross-check (2026-10-31)

## Scope

The private original `ADBCD.exe` remains outside the public repository.
Previously verified SHA256:
`a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.

This iteration implements **independent byte-level validation** of the
existing `pe_file_io_xrefs.py` private IAT candidate report. It does not
run the original, disassemble it, unpack executable sections, or decode IDF.

## Changes

- `pe_iat_evidence_validate.py` reads a private PE32 and a private IAT
  report, verifies the original SHA256, re-parses its import table and
  independently re-scans executable section bytes for `FF 15` / `FF 25`
  patterns targeting imported IAT slots. It checks every candidate's exact
  file offset, instruction VA, IAT operand, section name, import DLL, symbol
  and call/jump kind, including missing and duplicated candidates.
- Optional input from `AtelierData_IAT_Verified.java` is checked for
  candidate identity, SHA256, claimed MD5 match, per-row boolean verdicts
  and aggregate consistency. **This validates report consistency, not
  the authenticity of a Ghidra execution.** A forged report cannot be
  ruled out without a trusted private execution log.
- Bounded input sizes, mandatory SHA256 and path-isolation checks prevent
  accidental overwrite of original binaries or private reports.
- `pe_file_io_xrefs.py` now also rejects attempts to overwrite its original
  PE through either report output path.
- Synthetic tests cover forged offsets/operands/symbols, duplicates, omitted
  candidates, wrong hashes, malformed JSON, output isolation and inconsistent
  Ghidra results. The Windows workflow runs these tests.

## Private reproduction

Use a **locally authorized** original and keep all private files in a
non-public directory. Run from repository root:

```powershell
$sha = 'a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4'
$dir = 'C:\PRIVATE\atelierdata-audit'
python projects/atelierdata/pe_file_io_xrefs.py --pe "$dir\ADBCD.exe" --expected-sha256 $sha --public-output "$dir\iat-summary.json" --private-output "$dir\iat-private.json"
python projects/atelierdata/pe_iat_evidence_validate.py --pe "$dir\ADBCD.exe" --expected-sha256 $sha --private-iat "$dir\iat-private.json" --public-output "$dir\iat-evidence-public.json"
```

If an actual private Ghidra run has generated
`ghidra-iat-private.json` from the verified original, append
`--private-ghidra "$dir\ghidra-iat-private.json"` to the second command.

**Never upload** the original EXE/DLL/IDF, `iat-private.json`,
`ghidra-iat-private.json`, extracted strings, private offsets or raw
code to this public repository. The public JSON contains only counts,
classifications and the already-known original hash.

## Evidence and limitations

The previous REA v6.8.0 run found 52 uncertain delay-import observations.
The previously reported 43 IAT matches were **raw-byte candidates**,
not 43 validated instructions. The validator can prove consistency of
those raw matches with the SHA256-verified PE; it cannot establish
control-flow reachability or a data loader. The Ghidra script itself
has not been executed on the original during this iteration.

No `.IDF` decoder, file-format specification, legitimate original
Windows installation, valid original license or right to redistribute
Autodata data has been established. The blocked `part_0016` was not
accessed or bypassed.

CI status for this iteration must be obtained from the actual Windows
Actions run, not inferred from publication of these source changes.
