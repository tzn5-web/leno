# AtelierData — SHA256-verified IDF prefix provenance (2026-10-31)

This is a **new direct binary read** of owner-authorized \`autodata_part_0001.zip\` from private Google Drive. The original executable was **not executed**. The malware-flagged \`autodata_part_0016.zip\` was not accessed. The public repository contains no proprietary file contents, binary headers, source paths to the private original, keys, or decoded data.

## Verified observations

The tool \`original_idf_prefix_provenance.py\` streamed each complete single-chunk IDF in part 0001, compared SHA256 to the private owner-provided \`INVENTAR.json\`, and retained only up to 4096 bytes per file in memory for pairwise comparisons. This was a **fresh rehash of 19 actual IDF ZIP members**, not a re-read of the earlier CSV report.

- 19/19 SHA256 comparisons matched the owner manifest; 161,112,171 uncompressed bytes were hashed.
- 171 unordered pairs were compared. Exactly one pair shares at least 4, 8, 16 and 20 initial bytes; none shares 32 or 64 initial bytes. The **longest common prefix is 20 bytes**.
- None of the 19 samples begins with the small set of common ZIP/GZIP/SQLite/PDF/PNG/7z/RAR magic signatures tested. This does not rule out a custom container.
- Average Shannon entropy of the first up to 4096 bytes for samples with at least 256 bytes: 7.8225 bits per byte. This is a **sample statistic**, not proof of encryption or compression.
- Multipart IDF reconstruction is deliberately outside this tool's scope; other authorized ZIPs were not rehashed in this execution.

**Interpretation:** the repeated 20-byte prefix is a concrete structural clue for a possible shared header or data family. It does not establish record boundaries, encryption, a decoder, or a valid license. SHA256 consistency with the owner's manifest does not establish vendor authenticity.

## Reproduce privately

\`\`\`powershell
py -3 projects/atelierdata/original_idf_prefix_provenance.py --manifest C:\PRIVATE\INVENTAR.json --parts-dir C:\PRIVATE --package autodata_part_0001.zip --output C:\PRIVATE\idf_prefix_public.json
py -3 -m unittest discover -s projects/atelierdata -p test_original_idf_prefix_provenance.py -v
\`\`\`

The tool refuses part 0016 **before probing the filesystem**. It also rejects unknown/duplicate package selectors, symlinked ZIPs, duplicate ZIP members, encrypted members, SHA256 mismatches and unsafe output overwrite. Public output contains aggregate statistics only. Synthetic tests cover these invariants; CI builds the independent AtelierData Windows application but does not possess or run original proprietary binaries.

**Original installation blocker unchanged:** the untrusted package 0016 includes installer/registration-related components and is inaccessible without bypassing a malware warning. No authenticated installer, legitimate license entitlement, or Windows execution proof is available. Do not infer that original Windows installation is possible or safe.
