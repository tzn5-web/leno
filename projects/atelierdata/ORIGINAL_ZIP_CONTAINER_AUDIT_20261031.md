# Original Autodata ZIP container metadata audit — 2026-10-31

## Purpose and scope

`original_zip_container_audit.py` performs an **independent, read-only ZIP metadata check** before any future authorized payload verification. It compares manifest entry names and declared sizes with ZIP central-directory records, checks local headers and names, rejects duplicate/case-colliding entries, symlink members, encrypted entries, unsupported compression, overlapping member ranges, path traversal and extreme expansion ratios. It never extracts, decompresses, executes or installs original components.

The blocked `autodata_part_0016.zip` is excluded before any filesystem probe; even its local presence is not permission to access it. The audit does **not** calculate CRC or SHA256 of payloads and cannot establish publisher authenticity, software licensing or runtime compatibility. A structurally valid ZIP is not a trusted installer.

## Direct checks performed in this iteration

The private owner-provided `INVENTAR.json` was parsed locally, without publication of its contents. Its declared structure contains **139 files, 163 fragments and 16 ZIP parts**, including **124 fragment entries in parts 0001–0015** and **39 in blocked part 0016**. For every manifest file, the sum of declared fragment sizes equals the declared file size (**0 inconsistencies**). The new `expected_parts` validator accepted this manifest with no duplicate or unsafe member paths.

The manifest places **all seven specifically named installation/registration redistributable entries** (`Install-x32.cmd`, `Install-x64.cmd`, `RegSvr.bat`, `vcredist_x86.exe`, `vcredist_x64.exe`, and the two Sentinel Protection Installer variants) in **part 0016**. The manifest alone cannot authenticate or characterize these files. No installer was executed, and the blocked part was not downloaded or inspected.

## Direct ZIP verification on authorized originals

After the synthetic tests, the owner-provided ZIPs **0001 and 0015** were downloaded normally from Drive and inspected read-only. Part 0016 was not requested. The new ZIP metadata audit reported **2 structurally accepted, 13 not present in this run, 1 blocked, 0 rejected**.

| ZIP part | Local/central ZIP metadata | Entries | Declared uncompressed bytes | Independent streamed SHA256 vs owner manifest |
| --- | --- | ---: | ---: | --- |
| 0001 | No structural errors | 22 | 181,576,893 | 22/22 matching |
| 0015 | No structural errors | 5 | 188,064,901 | 5/5 matching |

**27/27 actual ZIP members were independently streamed and SHA256-matched to the owner-provided manifest** in this run, totaling **369,641,794 uncompressed bytes**. The hash recheck was a separate read-only Python streaming loop; the new ZIP metadata tool itself intentionally does not decompress or hash member payloads. The 13 remaining authorized parts were not downloaded in this iteration. Earlier reports separately document their prior verification. These checks establish consistency with the user-provided manifest, not vendor authenticity or license entitlement.

## Reproduce privately, with authorized local ZIP copies only

```powershell
python projects/atelierdata/original_zip_container_audit.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\zip_container_audit.json
python -m unittest discover -s projects/atelierdata -p "test_original_zip_container_audit.py" -v
```

Outputs contain aggregate status, counts and error categories, not ZIP payload bytes. Never put the private manifest or original binaries in the public repository.

## Original installation decision

**NOT READY FOR WINDOWS EXECUTION.** The installer provenance, licensing entitlement and Windows runtime behavior remain unverified. The unavailable package cannot be forced or substituted with emulators, activation tools or altered license checks. The static analysis and synthetic ZIP regression tests are useful diagnostics, not a demonstration that the original runs or that proprietary `.IDF` data is decoded.
