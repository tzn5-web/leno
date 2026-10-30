# Autodata ADBCD.exe — additional offline PE import evidence (2026-10-30)

## Provenance and method

Read-only inspection of the **original** `Autodata__3.45/ADCDA2/ADBCD.exe` member from `autodata_part_0001.zip` (the Drive archive fragment already obtained via the authorized connection). The ZIP member is 18,102,272 bytes; SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`, matching the manifest. No executable was started. A local Python `struct` parser read PE32 headers, section mapping, IMAGE_IMPORT_DESCRIPTOR and 32-bit import thunk arrays. **This is an independent static parser, NOT a REA analysis of the original binary.**

## Concrete import-table observations

PE machine `0x014c` (Intel x86), optional-header magic `0x10b` (PE32), 13 section headers, 4 import DLL descriptors, 17 named imported functions.

| Imported DLL | Count | Imported function names |
| --- | ---: | --- |
| KERNEL32.dll | 7 | GetSystemDirectoryA; SetErrorMode; MultiByteToWideChar; LoadLibraryA; GetModuleHandleA; ExitProcess; GetProcAddress |
| USER32.dll | 3 | EnumWindows; MessageBoxA; wsprintfA |
| ADVAPI32.dll | 3 | RegCloseKey; RegQueryValueExA; RegOpenKeyExA |
| MSVCRT.dll | 4 | _except_handler3; printf; malloc; free |

The presence of `LoadLibraryA` and `GetProcAddress` means **runtime-loaded dependencies are possible and cannot be excluded by the static import table**. Thus the four DLLs are *declared imports*, not a complete dependency inventory. No dependency on `SentinelKeyW.DLL` was observed in the standard import descriptors; this does **not** establish that Sentinel is unnecessary or not dynamically loaded. Dynamic dependency confirmation would require additional permitted static analysis or isolated runtime evidence.

Section names are mostly numeric (`0000001` through `0000013`) plus `.rsrc`. These are atypical but not proof of packing, encryption, tampering, or maliciousness. No embedded Authenticode certificate directory was declared. PE version-resource fields and `COMMON/VERINFO.DAT` are self-reported metadata, not an authenticity guarantee. `VERINFO.DAT` reports `ProductCode=CDA3.44`; the RAR label `3.45` is therefore not a validated product-version identity.

## Additional binary string evidence: Sentinel dependency candidate

A bounded ASCII scan of the same SHA256-verified original PE, without execution, found an embedded contiguous NUL-separated DLL-name block in the last PE section. The following exact byte offsets (zero-based, decimal) were observed:

- `SentinelKeyW.DLL` at **17,718,897**
- `gdiplus.dll` at **17,718,931**
- `cfgmgr32.dll` at **17,718,914**
- `netapi32.dll` at **17,718,948**
- `wsock32.dll` at **17,718,965**
- `oleacc.dll` at **17,718,999**

The same block includes `advapi32.dll`, `user32.dll`, `kernel32.dll`, `msimg32.dll`, `gdi32.dll`, `version.dll`, `mpr.dll`, `ole32.dll`, `comctl32.dll`, `winspool.drv`, `shell32.dll`, `comdlg32.dll`, `winmm.dll` and `MSVCRT.dll`. These strings provide **direct evidence that the original executable contains references to SentinelKeyW.DLL and gdiplus.dll**, although they are absent from its four standard import descriptors. The block's exact role (dynamic loader list, embedded import metadata, resource or other) has **not** been determined. This is not evidence of successful license activation or that a driver must be installed.

## REA integration and limits

The **separate** pinned REA 6.8.0 GitHub Actions job on 2026-10-30 executed real REA `inspect-pe-imports`, `inspect-pe-certificates`, `inspect-desktop-application` on a **harmless Windows notepad.exe fixture**, with Node 24.22.1, hash-negative gate, JSON output and artifact capture. The synthetic job returned PASS; see [run 41109921444](https://github.com/tzn5-web/leno/actions/runs/41109921444). This verifies the REA integration, **not** original Autodata analysis. The original private PE must not be uploaded to the public repo. Use `rea_static_private.ps1` with its exact SHA256 on a private authorized Windows machine to obtain original-PE REA evidence.

## Blockers

`autodata_part_0016.zip` remains unavailable through the provider due to `403 cannotDownloadAbusiveFile`, including five DLLs in `ADCDA2` and original install instructions. Do not bypass provider filtering. No valid vendor license or authorized redistribution evidence has been independently confirmed. No original installation/launch/uninstall was run. Final authentic installer status: **BLOCKED**.
