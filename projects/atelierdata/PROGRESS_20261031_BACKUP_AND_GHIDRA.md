# AtelierData — backup verification and private Ghidra evidence (2026-10-31)

## Implemented application capability

`backup_verification.py` adds **read-only ZIP backup verification** without restoring files to the active catalog. The new `atelierdata.py --verify-backup PATH.zip` command checks:

- expected ZIP member set and absence of duplicate/unexpected paths, ZIP symlinks, encrypted members, oversized entries and excessive decompressed size;
- backup schema, database SHA256, each managed document SHA256 and its content-addressed filename;
- SQLite `quick_check`, `foreign_key_check` and exact agreement between attachment references and the ZIP manifest, using a temporary read-only SQLite snapshot.

The command returns an aggregate JSON summary, never document bytes. It does not open an application database or mutate the original ZIP. It does **not** verify copyright ownership or decode proprietary data. The existing backup/restore format is unchanged.

Nine synthetic-only unit tests passed in an isolated local Python 3 environment with lightweight dependency stubs (ZIP integrity, altered documents/SQLite, traversal, malformed manifest, duplicate entries, mismatched references, symlink and valid archive). Two additional integration tests cover the actual CLI path (no default catalog created) and verification of a ZIP produced by the real AtelierData Store and managed-document backup code. Both are **committed but require the full application in CI**. The new module and tests are integrated in `.github/workflows/atelierdata-windows.yml`; **Windows CI and the new packaged EXE are not yet verified in this report**.

## Ghidra evidence enhancement — prepared, not executed on original

`tools/ghidra/AtelierData_IDF_Xrefs.py` now requires an independently computed **MD5 of the authorized source PE**, and refuses to scan when the imported Ghidra program's executable MD5 differs. It scans bounded ASCII/UTF-16LE keyword candidates, including `.IDF`, `CreateFileA/W`, `ReadFile`, `SetFilePointer`, `GetProcAddress`, `LoadLibraryA/W`, and the previously observed `pbvm90.dll`/`libjcc.dll` strings. For Ghidra-created references it records the owning function and entry point in a **private-only** JSON report.

This creates a focused static workflow for locating functions that reference file-I/O API names, rather than merely counting strings. **String xrefs are not proof of API calls, reachability, a decoder, encryption, or licensing behavior.** Ghidra was **not run on the original PE** in this update. Do not publish its address-bearing report.

Example only, in a private authorized Ghidra workspace:

```text
-postScript AtelierData_IDF_Xrefs.py C:\PRIVATE\idf-xrefs-private.json <MD5-computed-independently-from-verified-ADBCD.exe>
```

The known SHA256 reference for `ADBCD.exe` is `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`, as recorded in the original private inventory. No original binary was available for independent rehashing during this update. No private PE, IDF, ZIP, or Ghidra report was added to this public repository; blocked package 0016 was not accessed.

## Open gates

1. Confirm the latest Windows CI run for the new commit; inspect logs and artifact before claiming PASS or offering a new EXE.
2. Execute the hash-bound Ghidra script in a private, authorized analysis environment; validate the actual function xrefs and code paths, not just candidate strings.
3. Continue licensed-data catalog integration and practical UX tests. The IDF format remains **undecoded**.
