# AtelierData — independent Windows Authenticode gate (2026-10-31)

## Why this gate exists

The private owner-supplied Autodata archive has 81/81 SHA256-verified IDF files, but the original installer/registration components are only named in the unavailable, malware-flagged part 0016. The main executable's certificate table is absent; four other available DLLs contain PKCS#7 containers, **not independently verified signatures**. This is not evidence of a genuine, licensed, safe-to-run installation.

The new script [original_windows_authenticode_gate.py](original_windows_authenticode_gate.py) provides a **read-only Windows trust-policy check for a separate, authentic, legally acquired installer or library**, once an independent vendor hash and signing-certificate thumbprint are available. It does not open the blocked ZIP, execute the target, bypass license controls, install drivers, change system policy, or decode IDF. It must **never** be used as justification to override a malware warning.

## Verification model

1. Accept only an existing ordinary EXE, DLL or MSI file; refuse symbolic links/junctions and any path component named autodata_part_0016.zip.
2. Validate the caller-provided expected SHA256 (64 hexadecimal digits) and signer thumbprint (40 hexadecimal digits). Both expectations **must come from a trusted, independent vendor channel**, not from the untrusted archive itself.
3. Stream and check SHA256 before invoking Windows signature APIs; mismatched files never reach signature inspection.
4. On Windows, call Microsoft Get-AuthenticodeSignature -LiteralPath in a noninteractive PowerShell process. The target path is passed through an environment variable, never interpolated into PowerShell code. PowerShell is resolved from the Windows SystemRoot system directory, not from PATH, to prevent executable search-path hijacking. The target itself is never started.
5. Require Windows signature status Valid, an exact signer thumbprint match and, if provided, an exact subject match. Recheck the SHA256 after signature inspection to catch file modification.
6. Report a structured result with installation_authorized_by_this_tool=false and license_entitlement_verified=false **even if the signature matches**. The report does not prove that the vendor actually issued the supplied expectations or that the installer is safe.

Microsoft documents that Get-AuthenticodeSignature is Windows-only and that a Windows catalog signature can take precedence over an embedded signature:
https://learn.microsoft.com/powershell/module/microsoft.powershell.security/get-authenticodesignature

## Command (for a separate authentic vendor installer, not the original flagged archive)

Run this one-line command in Windows PowerShell after replacing the placeholder values with independently confirmed vendor values:

    python projects/atelierdata/original_windows_authenticode_gate.py --candidate "C:\AUTHORIZED\vendor-installer.exe" --expected-sha256 "<64-hex-hash-from-vendor>" --expected-signer-thumbprint "<40-hex-certificate-thumbprint-from-vendor>" --output "C:\AUTHORIZED\signature-report.json"

A return code of 0 means **signature and hash matched the supplied expectations**, not that installation or licensing is approved. All other results return code 2, fail closed, and leave the target untouched.

## Verification and remaining blockers

The new test module [test_original_windows_authenticode_gate.py](test_original_windows_authenticode_gate.py) exercises synthetic valid/invalid signature metadata, mismatched hash, mismatched signer, missing certificate, mutation during inspection, forbidden ZIP, forbidden extension, symlink, non-interpolated PowerShell input, and a Windows-only test that a fake powershell.exe in PATH is ignored. On Windows CI it also calls the **real Windows Authenticode API** on an inert, unsigned fixture and requires rejection. This is a negative-control test, not validation of the original Autodata files.

**No authentic installer, trusted vendor SHA256/thumbprint, or valid license was available for this run.** Accordingly the original application was not started, repaired, or certified. The 81 IDF files remain unmodified and **not decoded**. The new gate is useful for a later legitimate vendor-provided installer but cannot resolve the current missing provenance/entitlement.

The tool and tests are new isolated files, so they do not overwrite ongoing work on the AtelierData GUI, procedures, schematics, REA or Ghidra. GitHub Actions automatically discovers the new test_*.py file on the existing Windows workflow; inspect the specific run before claiming PASS.
