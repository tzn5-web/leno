# Original PE delay-load directory: structural audit (2026-10-31)

## Scope and provenance

Read-only static inspection of the owner-provided original `ADBCD.exe` **inside the already authorized** `autodata_part_0001.zip`, without executing or extracting the original executable. The ZIP member was read into memory and its SHA256 was verified against the user-provided manifest:

- Original PE SHA256: `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
- Format: PE32 x86.
- Source: `INVENTAR.json`, `autodata_part_0001.zip`. Part 0016 was **not opened**.
- Method: independent PE optional-header and RVA-to-raw mapping, bounded inspection of IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT (index 13), validation of 32-byte delay descriptors and termination, and Shannon entropy on the declared directory bytes. No decryption, unpacking, DRM, licensing operations, or runtime execution.

## Verified observations from the real executable

| Metric | Result |
| --- | ---: |
| Declared delay-load directory | Yes |
| Directory size | **1,104 bytes** |
| Complete 32-byte descriptor slots | **34** |
| Remaining bytes | **16** |
| Nonzero slots | **34 / 34** |
| Slots with unsupported attribute bits (outside bit 0) | **34 / 34** |
| Structurally plausible DLL-name descriptors | **0** |
| All-zero terminating descriptor | **Not present** |
| Entropy of the declared 1,104-byte region | **7.8312 bits/byte** |
| Structural verdict | **NOT_VALIDATED_AS_STANDARD_DELAY_IMPORTS** |

These are **actual measurements on the original SHA256-matched file**, not results from synthetic fixtures. The reported region does not conform to a normal array of delay-load descriptors: all 34 candidate descriptors have unsupported attribute bits, and no zero terminator appears in the declared range. A 16-byte remainder is also present. The parser does not treat these 34 entries as legitimate imported DLLs.

**Interpretation:** the previously reported **52 uncertain REA delay-load observations** must **not** be counted as 52 verified imports. This finding is compatible with malformed/opaque or deliberately misleading directory metadata; it does **not** establish why the metadata is malformed, whether a packer exists, whether a loader is reachable, or how `.IDF` data is stored. It does not prove encryption.

## Implementation and reproducibility

Added [`pe_delay_directory_sanity.py`](pe_delay_directory_sanity.py) and [`test_pe_delay_directory_sanity.py`](test_pe_delay_directory_sanity.py). The analyzer rejects mismatched SHA256, malformed PE headers, ambiguous RVA mappings and blocked package names, and exports only structural aggregates (not original bytes, imported names or private offsets).

Nine synthetic tests **passed locally** (Python 3.13.5): absent directory, RVA/VA descriptors, malformed attributes, non-descriptor trailing bytes, incorrect SHA256, unmapped directory, blocked part 0016, and ZIP integration/output isolation. The original was also analyzed successfully and produced the measurements above. Existing Windows CI discovers `test_*.py` automatically, but **Windows CI for these new commits must be checked independently** before any PASS claim.

To reproduce in a private authorized workspace:

```powershell
python projects/atelierdata/pe_delay_directory_sanity.py --zip-part-0001 "C:\\PRIVATE\\autodata_part_0001.zip" --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --output "C:\\PRIVATE\\delay-directory-public.json"
python -m unittest discover -s projects/atelierdata -p 'test_pe_delay_directory_sanity.py' -v
```

The script intentionally accepts only `autodata_part_0001.zip` and the exact `ADBCD.exe` member. The blocked `autodata_part_0016.zip` is never accessed.

## Remaining blockers

The actual IDF reader and any valid data format are **not identified**. The original's licensing, genuine installer and safe Windows execution remain unverified. Ghidra was **not run** in this iteration; this analysis does not validate the 43 raw FF15/FF25 instruction candidates. The next useful REA/Ghidra investigation is a bounded, SHA256-bound control-flow check of actual executable code rather than treating the malformed delay directory as a real import list.

No original binary, proprietary IDF content, key material or private REA/Ghidra evidence was committed.
