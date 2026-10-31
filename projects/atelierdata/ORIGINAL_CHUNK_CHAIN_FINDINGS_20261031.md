# Original archive: multipart reconstruction ordering gate (2026-10-31)

The user-provided private Drive `INVENTAR.json` was read again. SHA256 of that manifest is `ec867e0fae97523caff4677e7684b03a2e30832856de67239861986221a804ca`, consistent with the earlier evidence ledger. No ZIP member or original binary was opened, executed, decoded, or published in this iteration.

## Measured manifest-only results

- 139 declared files, 163 chunk records, 16 ZIP package names.
- 131 files have a single ZIP member; 8 multipart files comprise 32 chunks.
- All 8 multipart files are IDF files; their non-final chunks are exactly 67,108,864 bytes.
- 4 multipart chains cross a ZIP package boundary. Largest chain: 11 chunks.
- 81 IDF files account for 105 chunk records. None requires blocked `autodata_part_0016.zip`.
- Blocked package `0016` contains 39 declared chunk records, but was not probed.
- No gaps, reversals, unexpected names, invalid terminal sizes, or declared-total discrepancies were found.

The new `original_chunk_chain_gate.py` checks exact `.chunkNNNN` ordering, single-member names, 64 MiB nonterminal split sizes, terminal size bounds, nondecreasing package order, aggregate sizes and counts. Its tests use synthetic metadata only. These checks protect against a silently misordered multipart reconstruction; they **do not** verify actual payload bytes or identify the IDF format.

Local verification: 11 synthetic unit tests passed using the published loader logic; the real private manifest produced `chain_structure=PASS`. Windows GitHub CI must independently complete before claiming a new Windows build PASS.

## Legal installation decision

The available metadata still does **not** prove that the original Autodata distribution is authentic, licensed, safe to install or compatible with Windows. The inaccessible package contains installer/registration files and dependencies, so it must not be forced or replaced with emulators. Use only a genuine licensed installer from the rights holder for any future isolated Windows test. The original IDF content remains proprietary and undecoded.

To reproduce with the user's private manifest (never commit it):

```powershell
python projects/atelierdata/original_chunk_chain_gate.py --manifest C:\PRIVATE\INVENTAR.json --output C:\PRIVATE\chunk-chain.json
python -m unittest discover -s projects/atelierdata -p 'test_*.py' -v
```

This change is isolated to original-archive integrity analysis; it does not modify REA/Ghidra scripts, procedures, schematics, or the application database.
