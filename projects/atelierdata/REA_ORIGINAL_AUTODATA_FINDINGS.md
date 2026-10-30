# REA 6.8.0 — Autodata static analysis, original private binary (2026-10-30)

REA (official `morluto/rea`, npm `rea-agents@6.8.0`) was **actually executed locally** on the source owner's `ADBCD.exe` and three Chilkat DLLs from their private Autodata archive, without uploading any original program content to this public repository.

**Source provenance:** `autodata_part_0001.zip` + `autodata_part_0004.zip` read through permitted means; 12 input files were validated against the original `INVENTAR.json` SHA256 chunks. This is a *partial* set, not the complete 139 files.

## Direct REA findings

| Original target | REA command | Result |
| --- | --- | --- |
| `ADCDA2/ADBCD.exe` | `inspect-pe-imports` | PASS, PE32 x86, imported DLLs KERNEL32, USER32, ADVAPI32, MSVCRT; 52 warnings/uncertain delay-load observations |
| `ADCDA2/ChilkatCert.dll` | `inspect-pe-imports` | PASS, PE32 x86 |
| `ADCDA2/ChilkatCrypt2.dll` | `inspect-pe-imports` | PASS, PE32 x86; declares functions from ADVAPI32 and CRYPT32, including CryptEncryptMessage/CryptDecryptMessage |
| `ADCDA2/ChilkatUtil.dll` | `inspect-pe-imports` | PASS, PE32 x86 |
| Verified partial `ADCDA2/` directory | `inspect-desktop-application` | PASS, 14 observed entries (includes directories), 4 bounded file probes; no detected runtime-family marker |
| `COMMON/CONST.IDF` | `inspect-artifact` | Unsupported binary format |
| `COMMON/MODELS.IDF` | `inspect-artifact` | Unsupported binary format |
| `ENG/DTC.IDF` | `inspect-artifact` | Unsupported binary format |

The `ADBCD.exe` delay-load table has 52 partial-coverage issues, including unsupported virtual-address forms and unreadable name ranges. Imports are not necessarily complete or reachable at runtime.

Chilkat cryptographic imports **do not prove** that the data files are encrypted with those functions. No `.IDF` decoder was established; no Autodata procedure, diagram, specification or full vehicle record was extracted. No part of the original application was executed, and no license protection was bypassed.

The complete REA Evidence JSON artifacts and a Romanian report are retained as conversation deliverables (private original files excluded).

## Reproducibility

- `.github/workflows/atelierdata-rea-analysis.yml` ran REA on the newly authored AtelierData app on Windows and published `AtelierData_REA_Static_Reports`: [CI run 41110122747](https://github.com/tzn5-web/leno/actions/runs/41110122747) — PASS.
- `.github/workflows/rea-offline-runtime.yml` built an isolated REA runtime on Ubuntu from the official npm package: [CI run 41110694843](https://github.com/tzn5-web/leno/actions/runs/41110694843) — PASS.
- `tools/cloud/autodata_rea_static_colab.ipynb` runs REA against the original `ADBCD.exe` privately in user-authorized Google Colab and writes evidence to Drive.

Next technically meaningful investigation: identify the legitimate data-format loader and obtain a supported, authorized export/format specification, without duplicating protected application code or bypassing license checks.
