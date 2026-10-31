# Original archive — verified static inventory triage (2026-10-31)

Scope: owner-supplied private `INVENTAR.json`/`INVENTAR.txt`, and privately stored original ZIP package `autodata_part_0001.zip`. This report contains **no original application, database or proprietary extracted payload**. No original executable, keygen, emulator, driver, license helper or installer was run.

## Verified results

- Inventory JSON/text reconciliation: **PASS**. Exactly **139 reconstructed paths**, **163 chunks**, **16 package files**, **2,323,704,957 reconstructed bytes**, and **81 .IDF files**. Sum of all per-file chunk sizes matches every reconstructed file size.
- Distribution: all **81 .IDF files are in packages 0001–0015**; **package 0016 contains zero .IDF files**. The missing package still matters: its 39 entries include application DLLs, legacy installers and licensing-related utilities. Thus these results do **not** prove that an installed original application would start.
- Package 0001: **PASS**. The retrieved ZIP has exactly **22 expected entries**; every entry's uncompressed size and **SHA256** match the private inventory. This includes the original `ADCDA2/ADBCD.exe`, **18,102,272 bytes**, SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
- Static `file` and GNU `objdump -p` on the verified original showed **PE32/x86 Windows GUI, 13 sections, subsystem version 5.0**, explicit import DLLs **KERNEL32.dll**, **USER32.dll**, **ADVAPI32.dll**, **MSVCRT.dll**. Static PE import lists are not a complete runtime dependency list.
- The PE declares a **delay import data directory** (RVA `0x00764000`, size `0x450`). The first bytes mapped at that RVA do not form a conventional valid delay-import descriptor; therefore no delay DLL symbols are claimed from that directory. This observation alone does not prove packing, infection, licensing behavior, encryption, or any specific IDF decoding mechanism.
- Google Drive reported HTTP 403 `cannotDownloadAbusiveFile` for package 0016. This block was not bypassed.

## Reproducible, non-executing audit

Script: `projects/atelierdata/split_archive_manifest_audit.py`. It validates the inventory's split-chunk ordering and hashes; when user-authorized ZIPs are locally present it compares ZIP member names/sizes, optionally streaming SHA256 for every chunk. It **does not extract or execute any member**.

```powershell
python projects/atelierdata/split_archive_manifest_audit.py --self-test
python projects/atelierdata/split_archive_manifest_audit.py --manifest .\INVENTAR.json --inventory .\INVENTAR.txt
python projects/atelierdata/split_archive_manifest_audit.py --manifest .\INVENTAR.json --inventory .\INVENTAR.txt --parts-dir .\private-original --sha256 --output .\private-original\archive_audit.json
```

The latter command may report missing parts if the directory is incomplete; **do not interpret that as permission to bypass Google Drive security screening**. Do not commit private inventory, original ZIPs, binaries, reports containing proprietary bytes, or protected datasets.

## Remaining blockers

1. Verify the remaining authorized packages individually, if accessible, and establish the complete chain of required runtime DLLs without executing suspicious helpers.
2. The 0016 package cannot currently be accessed through the authorized Google Drive connector; no installation can be called complete on this evidence.
3. Verify official licensing and Windows compatibility through a legitimate vendor distribution, rather than keygens or emulators.
4. A working `.IDF` parser **has not been proven**. No proprietary vehicle procedures/diagrams have been extracted.
5. Re-test a newly built AtelierData executable separately; it is not an Autodata 1:1 replacement.
