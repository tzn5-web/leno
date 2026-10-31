# IDF standard-container signature triage — 2026-10-31

## Actual private-source inspection

The owner-authorized static_analysis.csv was retrieved through the authenticated Google Drive connector, **not** published to GitHub. The downloaded file was independently hashed in the analysis container:

- SHA256: 1a9831ffbb2a0d94f1ee51087ecfd97a622336358f75215f018efea82b50c0e7
- 84 metadata records, of which **81 are IDF**.
- Each row supplies at most the first 64 bytes of its file as private hex metadata and a previously computed entropy estimate.
- The 81 original IDF files were **not independently downloaded or rehashed** in this run. The SHA256 gate validates the *CSV*, not original-file provenance.

The new idf_signature_evidence.py was run locally on this verified CSV. Results:

| Observation | Count |
| --- | ---: |
| IDF header records analyzed | 81 |
| Recognized ZIP, gzip, bzip2, xz, zstd, LZ4 frame, 7z, RAR, SQLite, PDF, PNG, OLE/CFB, CAB or ELF signature at offset zero | **0** |
| Those same signatures embedded at nonzero offsets within the first 64 bytes | **0** |
| Standard zlib CMF/FLG-compatible header at offset zero | **0** |
| Sample entropy reported as at least 7.9 bits/byte | 75 |
| Header samples shorter than 64 bytes | 2 |

This is **negative evidence for the tested, conventional signatures at the sampled offsets**, not evidence that the data is encrypted, that it lacks compression, or that the .IDF format has been identified. The file could have a custom header, nonstandard framing, offsets beyond the first 64 bytes, raw compression streams, or another encoding. Entropy from the existing CSV is not a cryptographic test.

## Code, reproducibility and privacy

- idf_signature_evidence.py enforces an expected SHA256 for the private input CSV, size/row/hex/entropy bounds, and rejects duplicate private paths.
- test_idf_signature_evidence.py has **eight synthetic-only tests**, passed locally on Linux; the existing Windows workflow discovers test_*.py automatically. A Windows CI result must be checked separately.
- The public output IDF_SIGNATURE_AGGREGATE_20261031.json contains counts and booleans only. No original paths, raw header bytes, binary files, private reports or licensed content are committed.
- Reproduce privately with the authorized CSV:

~~~powershell
python projects/atelierdata/idf_signature_evidence.py --input-csv C:\PRIVATE\static_analysis.csv --expected-sha256 1a9831ffbb2a0d94f1ee51087ecfd97a622336358f75215f018efea82b50c0e7 --public-output C:\PRIVATE\idf-signatures-public.json
python -m unittest discover -s projects/atelierdata -p test_idf_signature_evidence.py -v
~~~

**Interpretation:** prioritize verified structural relationships, Ghidra cross-references and authorized format documentation rather than assuming a standard compressed container. This run did not execute REA/Ghidra on the private original, did not access blocked ZIP part_0016, did not run original executables, did not bypass licenses or DRM, and did not decode IDF.
