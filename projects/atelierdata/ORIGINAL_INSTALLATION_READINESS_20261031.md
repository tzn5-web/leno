# AtelierData — original Autodata installation readiness, 2026-10-31

## Evidence and scope

Read-only analysis of the owner-supplied `INVENTAR.json` and authorized `autodata_part_0001.zip` through `autodata_part_0015.zip`. The unavailable `autodata_part_0016.zip` was **not** fetched, bypassed, scanned, extracted or executed. No original executable, DLL, installer, key, license file or `.IDF` data is included in the public repository. No Windows installation or original application execution was attempted.

The new script `original_installation_readiness.py` distinguishes **package present**, **SHA256-verified component**, **runtime-tested**, **license-proven** and **vendor-authenticated** states. It does not treat one as evidence of the others.

## Direct results from the real private manifest and ZIPs

| Evidence | Result | Meaning |
| --- | --- | --- |
| Manifest | 139 files / 16 ZIPs | Manifest structurally validated. |
| Accessible ZIPs | 15 / 16 | `0016` remains blocked by Drive. |
| Full SHA256 recheck of accessible chunks | 124 / 124, no errors | Checksums match the **owner-provided** manifest; does not establish publisher authenticity. |
| `.IDF` | 81 / 81, verified SHA256 | Data bytes available; **not decoded**. |
| Original main `ADBCD.exe` | 18,102,272 bytes, SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` | PE32 x86; never executed. |
| Root EXE/DLL static inspection | 5 SHA256-verified PE components, 5 unavailable | `RelLic.dll` and three Chilkat DLLs are in available ZIPs. |
| Main executable direct import closure | 0 unresolved **direct** imports | Not evidence that dynamically loaded modules are present. |
| Sentinel DLL name | Literal reference exists; DLL unavailable | A literal is **not** proof of unconditional loading or the cause of failure. |
| Named installer/registration entrypoints | 0 / 7 available | Their content, signatures, dependencies and intended behavior cannot be inspected. |
| Runtime/licensing | Not tested / not established | No conclusion about legal startup on Windows. |

The available 15 ZIPs contain **all 81 IDF files**; the unavailable package contains **39 other files**. Its manifest includes `SentinelKeyW.DLL`, `cw3220mt.dll`, `gdiplus.dll`, `libeay32.dll`, `ssleay32.dll`, installation scripts, registration files, Sentinel and Visual C++ redistributables, and files named as activation/emulation tools. These are **manifest filenames only**; their authenticity and behavior have not been established. The package's malware flag must not be bypassed.

Six groups of files in package `0016` have matching **manifest-declared** size and SHA256, including the x86/x64 emulator names and similarly named `AuDaS` executables, `GetUid` duplicates, a license tool duplicate and a Sentinel installer duplicate. Because package `0016` is unavailable, these duplicate claims have **not** been independently hash-verified. No assertion that any file is malware is made solely from its filename.

## Decision and next legitimate diagnostic gate

**ORIGINAL INSTALLATION: BLOCKED / NOT READY TO EXECUTE.** The missing package includes installation and licensing-related material that cannot be inspected safely. Even if those files became available, entitlement, authentic vendor provenance and supported runtime compatibility would still need independent verification. Neither changing the date/registry, installing emulator tools, disabling protections nor substituting license DLLs is an acceptable repair path.

The only defensible next original-installation test is to obtain a **genuine, authorized installer and valid license** from the rights holder, check publisher signatures and official compatibility guidance, then test on an isolated Windows environment. The verified `.IDF` bytes need no repair on the evidence currently available.

In parallel, develop the independently written AtelierData application using authorized technical content. No proprietary database is published or claimed to be decoded.

## Reproduction and tests

~~~powershell
python projects/atelierdata/original_installation_readiness.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\readiness.json
python projects/atelierdata/original_archive_preflight.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\integrity.json
python -m unittest discover -s projects/atelierdata -p "test_*.py" -v
~~~

The seven new tests use synthetic manifests only. The real manifest/ZIP recheck and dependency inspection were performed in a private local analysis environment. CI tests the **source and synthetic fixtures**, not the inaccessible `0016` or a licensed original runtime.
