# Original Autodata — evidence gate (2026-10-31)

This is a **read-only** integrity gate for the owner-supplied original archive.
It does not install, run, unpack, decrypt or patch the original application,
drivers, installers or license components. It cannot certify publisher
authenticity, license entitlement, Windows compatibility or IDF decoding.

## Why this gate was added

The earlier installation-readiness inventory deliberately reported **ZIP
presence**, not full SHA256 verification. Treating presence as verification
would be a diagnostic error. The new
`original_installation_evidence_gate.py` calls the bounded streaming ZIP
auditor and verifies every available ZIP member against the owner-provided
manifest, including member names, decompressed sizes and SHA256. It checks
unexpected ZIP members and rejects mismatches. A partial distribution can
be marked as **integrity-verified for available parts** but never as
installation-ready.

The malware-flagged `autodata_part_0016.zip` is explicitly excluded.
If it appears in the selected directory, the tool **refuses to run** rather
than inspecting or bypassing it. The gate also rejects missing packages
other than the explicitly blocked one, as well as manifest package-count
mismatches.

## Reproduce with authorized private files

~~~powershell
python projects/atelierdata/original_installation_evidence_gate.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE\ZIP_PARTS --output C:\PRIVATE\evidence_gate.json
python -m unittest discover -s projects/atelierdata -p test_original_installation_evidence_gate.py -v
~~~

Return code 0 means the **available** ZIP members match the supplied
manifest and the only unavailable packages are explicitly blocked. It does
**not** mean the original installer is safe, authentic, licensed, or
functional. Return code 2 means an integrity/precondition problem or an
unexpected missing package.

## Known evidence (prior private audit)

- 139 manifest files across 16 ZIP parts.
- 15 authorized ZIPs previously read, 124 SHA256-verified chunks and all
  81 IDF files verified, without decoding them.
- Package 0016 remains unavailable; its contents are **not** independently
  verified, and no attempt is made to obtain it by circumventing malware
  protections.
- `ADBCD.exe` SHA256
  `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`,
  PE32 x86. This is integrity against the owner's manifest, not publisher
  authentication.
- No valid license or authentic installer has been demonstrated; original
  Windows execution remains **BLOCKED**.

The seven new tests use tiny, synthetic ZIP files. They exercise success
with the known blocked package, a corrupted IDF, an unexpected ZIP member,
a blocked package that is present, an additional missing package, a fully
present synthetic distribution, and an invalid manifest count. CI
compiles the independent AtelierData Windows EXE; it does not execute or
package any proprietary original binaries or data.

## Next evidence required for the original application

An authentic rights-holder installer, a valid license, publisher signature
verification and compatibility documentation. Only then would an isolated
Windows installation test be meaningful. The independent AtelierData
application continues separately using permitted data sources.
