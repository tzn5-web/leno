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
  powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneclick.ps1 -ExtractedRoot "C:\Autodata__3.45" -Manifest "C:\INVENTAR.json"

Output on success:
  dist\Autodata_3_45_OneClick_Setup.exe

The builder will NOT compile from incomplete files or when a Defender threat is identified. Nothing from the private archive is uploaded to this public GitHub repository. No keygen, emulator, altered driver, fake product license, identity spoof or activation bypass is included.

Even a successfully compiled installer cannot prove Autodata will launch: check application dependencies, authorization, driver versions and the app running in an isolated Windows test before production.
