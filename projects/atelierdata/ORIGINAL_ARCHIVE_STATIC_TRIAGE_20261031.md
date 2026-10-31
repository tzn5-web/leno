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


## Extended direct verification (2026-10-31)

A later read-only verification fetched **packages 0001–0015** through the authorized Google Drive connector. For all 15 ZIP files, **every declared ZIP member's size and SHA256 matched INVENTAR.json**: **124 chunk entries** and **2,271,754,801 uncompressed bytes** verified. Only 0016 remains inaccessible (403). This is verified integrity of all *accessible chunks*, **not** a complete original installation or functional Windows launch.

Using exclusively those 15 verified packages, all **81 reconstructed .IDF files** (combined **2,231,509,692 bytes**) were assembled one-at-a-time in anonymous temporary scratch storage, their source chunks re-verified SHA256, and three 64 KiB windows per file analyzed. **70/81** had entropy >=7.95 bits/byte in each window; **0/81** started with recognizable ZIP/GZIP/zlib headers tested. Neither result identifies a cipher or decoder. No file contents were exported or published, and no original executable ran.

New reproducible scripts:
- `projects/atelierdata/split_archive_manifest_audit.py`: manifest, ZIP and SHA256 verification.
- `projects/atelierdata/full_idf_chunk_audit.py`: verified temporary reconstruction and aggregate IDF statistics, optional local private per-file metadata.
Both have synthetic-data self-tests added to Windows CI. No private ZIP, .IDF, executable, installation key or report containing payload bytes is added to GitHub.

The original `COMMON/VERINFO.DAT` (in verified package 0004) contains `ProductCode=CDA3.44`, `VersionNo=9.200`, and `ExpiryDate=42004`, whereas the supplied archive name refers to 3.45. This **metadata discrepancy merits investigation**, but the expiry field's encoding/meaning and impact on launch have **not** been established. Do not infer or attempt to bypass licensing from these strings. The three bundled Chilkat DLLs in package 0004 are PE32 x86, consistent with the main PE32 x86 executable.

**Remaining critical blocker:** package 0016 contains 39 non-IDF entries, including `SentinelKeyW.DLL`, `cw3220mt.dll`, `gdiplus.dll`, `libeay32.dll`, `ssleay32.dll` and legacy installers/license helpers, and remains inaccessible. A complete install and runtime test were not performed.
