# Arhivat ca șablon concurent — nu folosi pentru o instalare finală

**31.10.2026:** Aceasta este o implementare istorică, păstrată pentru comparație. Proiectul canonic pentru instalarea programului Autodata original este **[`tools/autodata-installer/`](https://github.com/tzn5-web/leno/tree/autodata-installer-20261030/tools/autodata-installer)**, pe ramura `autodata-installer-20261030`. Nu sunt validate nici versiunea exactă a programului, nici cele cinci DLL-uri inaccesibile din ZIP-ul 0016, licența, calea implicită de instalare sau lansarea aplicației. **Nu rulați acest builder concurent ca soluție finală.** Această ramură rămâne pentru analiza statică originală `.IDF`, REA și Ghidra, nu pentru alt instalator.

---

# Autodata 3.45 One-Click — Windows installer project

Goal: package a VERIFIED, LAWFULLY LICENSED Autodata 3.45 installation in ONE Windows Setup.exe, with shortcuts and an uninstaller. Original Autodata program binaries remain proprietary; they are not recompiled.

Status: installer source is available, FINAL AUTODATA EXE NOT YET BUILT. The original instruction documents are located in ZIP part 0016, whose download was blocked by Google Drive (cannotDownloadAbusiveFile). No complete documentation/license audit can be claimed yet.

Inno Setup 6.5.2+ or 7 supports one executable approaching 4 GB, enough in principle for the 2.32 GB extracted tree. Compiler, disk capacity, DLL/driver dependencies, genuine license activation and Windows runtime still require testing.

Contents:
- oneclick.iss: Inno Setup script. Copies the verified ADCDA2 tree, adds start-menu/desktop shortcuts and uninstaller.
- verify_payload.py: validates the exact 64 MiB chunk SHA256 digests against the original private INVENTAR.json; rejects missing, unexpected or unsafe paths.
- source_review.py: reads and reports TXT/PDF/CMD/BAT/REG documents inertly; never executes archive content.
- build_oneclick.ps1: runs hash verification, Microsoft Defender scan and ISCC compilation on a Windows machine.

PRIVATE WINDOWS BUILD AFTER DOCUMENTATION REVIEW:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneclick.ps1 -ExtractedRoot "C:\Autodata__3.45" -Manifest "C:\INVENTAR.json" -ReviewRecord "C:\Private\autodata_review.json"

Output on success:
  %TEMP%\AutodataPrivateBuild\Autodata_3_45_OneClick_Setup.exe

The builder will NOT compile from incomplete files or when a Defender threat is identified. Nothing from the private archive is uploaded to this public GitHub repository. No keygen, emulator, altered driver, fake product license, identity spoof or activation bypass is included.

Even a successfully compiled installer cannot prove Autodata will launch: check application dependencies, authorization, driver versions and the app running in an isolated Windows test before production.


## REA integration (2026-10-30)

A new GitHub Actions workflow `.github/workflows/autodata-rea-static-ci.yml` installs **rea-agents 6.8.0** with **Node 24.22.1** and runs `inspect-pe-imports`, `inspect-pe-certificates` and `inspect-desktop-application` on a **Windows system executable fixture only**. It does not include or upload the original Autodata binaries. It tests the actual REA CLI, JSON output, hash-gating and read-only process. See the CI logs before treating this lane as PASS.

For the **original** `ADBCD.exe`, place a verified authorized local copy on a Windows computer, install REA 6.8.0 under a compatible Node runtime from the [REA upstream repository](https://github.com/morluto/rea), and execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\rea_static_private.ps1 `
  -SourceExe "C:\Private\ADCDA2\ADBCD.exe" `
  -ExpectedSha256 "a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4" `
  -OutputDir "C:\Private\Autodata_REA_Reports"
```

The runner refuses a SHA mismatch, unsupported Node, missing REA, or a report destination inside the public checkout. Reports remain on the private computer; no target binary, driver, keygen or dongle emulator is executed. **Do not publish these original-binary reports until reviewed for proprietary content.** A synthetic REA CI PASS is not a real Autodata PE REA PASS.

## Private release-review gate

The private build runner now requires `-ReviewRecord` pointing to a JSON file **outside this public repository**. `release_gate.py` refuses a build until a human reviewer has recorded the original RAR and ADBCD hashes, their identity, UTC review time, and affirmative reviews of source authenticity, vendor license evidence, installation instructions, Sentinel dependencies, the CDA3.44 vs 3.45 discrepancy, and private-only distribution. The record must also confirm no license material is stored in a public repository. A human attestation is **not** automated validation of a vendor license.

Required JSON keys:

```json
{
  "original_rar_sha256": "e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da",
  "application_sha256": "a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4",
  "reviewer": "REPLACE_WITH_REAL_REVIEWER",
  "reviewed_at_utc": "2026-10-30T18:00:00Z",
  "source_authenticity_reviewed": false,
  "vendor_license_evidence_reviewed": false,
  "installation_instructions_reviewed": false,
  "sentinel_dependencies_reviewed": false,
  "version_discrepancy_reviewed": false,
  "private_distribution_only": false,
  "license_material_in_public_repo": false
}
```

The reviewer must not set any check to true without actually completing it. Production release additionally requires isolated Windows install/launch/uninstall PASS and binary signing, via `release_gate.py --stage release`. This is a fail-closed process: the final installer is not released from synthetic CI.
