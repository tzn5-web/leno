# PE entrypoint / section layout: static evidence (2026-10-30, second iteration)

## Inputs and method

- Private original: `ADCDA2/ADBCD.exe`, supplied by the user; **SHA256 verified again** as `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
- Inspection only: Python PE32 parser and bounded entropy/entrypoint/IAT-pattern scanner in [`pe_entrypoint_layout.py`](pe_entrypoint_layout.py). The original was **never executed**.
- Independent spot check: GNU `objdump -D -b binary -m i386 -M intel` disassembled a **256-byte private window at the PE entrypoint**, beginning with an ordinary x86 `push ebp; mov ebp, esp` prologue. This is not full control-flow analysis.
- The script invokes the earlier IAT triage and attributes raw byte-pattern matches to PE sections. These matches are **not validated instruction boundaries**.

## New verified findings

| Metric | Result |
| --- | --- |
| PE architecture | x86 PE32 |
| PE sections | 13 |
| Executable sections | 3 (indices 0, 1, 12) |
| PE entrypoint location | Section **12** (the last executable section) |
| Raw IAT-call/jump byte-pattern candidates | **43** |
| Candidates located in entrypoint section | **43/43** |
| Candidates in executable section 0 | **0** |
| Executable section 0 size | **7,044,608 bytes** |
| Executable section 0 Shannon entropy (first/middle/last 64 KiB) | **7.9970 / 7.9975 / 7.9971** bits/byte |
| Executable section 1 size | **14,848 bytes** |
| Executable section 1 entropy (entire small section, three overlapping windows) | **7.9864** bits/byte |
| Entrypoint section 12 size | **3,760,128 bytes** |
| Entrypoint section 12 entropy (first/middle/last 64 KiB) | **6.3990 / 7.9971 / 7.9747** bits/byte |
| Bytes after last section raw range | **0** |
| Target executed | **No** |
| IDF decoder identified | **No** |

**Interpretation:** the combination of a lower-entropy entrypoint region, highly entropic other executable regions, and concentration of all 43 import callsite candidates in the entrypoint section is **consistent with a wrapper/loader and opaque payload**. This is a *hypothesis*, not proof of a packer, encryption, executable unpacking, DRM, or the IDF file format. Other explanations remain possible.

**Practical consequence:** blindly pursuing `CreateFileA`/ `ReadFile` xrefs in the 17 ordinary imports will not by itself identify the original application's data reader. The next *authorized* static step is to distinguish the PE wrapper from application logic in Ghidra, using an explicit entrypoint-centered project and evidence of reachable calls. No unpacking or license bypass is proposed.

## Reproduction and safety

```powershell
python projects/atelierdata/pe_entrypoint_layout.py --pe C:\\PRIVATE\\ADBCD.exe --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output C:\\PRIVATE\\pe-layout-summary.json
python -m unittest discover -s projects/atelierdata -p 'test_*.py' -v
```

The tool was **run on the actual SHA256-verified private executable**. Its **four new synthetic regression tests passed locally**, including hash rejection, invalid entrypoint rejection, overlay calculation, and IAT attribution. GitHub Actions was updated to include these files in Python syntax and test discovery. **Windows CI run 41134102681 completed SUCCESS** on commit `0b02da9638ad03ebfb65cb0d729a2243b65ba79b`, with **66/66 automated tests**, application SQLite self-test, compiled EXE self-test and GUI smoke test PASS. [Windows CI run](https://github.com/tzn5-web/leno/actions/runs/41134102681). Compiled `AtelierData.exe` is **19,483,581 bytes**, SHA256 `d552178f5e43b413aaf09613e24b2045c89b729d96ee42aab5b7498eccd7fdef`. This validates existing test coverage, not data correctness or equivalence with Autodata.

No executable bytes, proprietary resources, source database contents, protected file keys, or private Ghidra evidence were uploaded to this public repository. The script reports section-level aggregate statistics only. The restricted ZIP part 0016 was not accessed or bypassed.

The earlier REA 6.8.0 analysis is documented in [`REA_ORIGINAL_AUTODATA_FINDINGS.md`](REA_ORIGINAL_AUTODATA_FINDINGS.md). **REA and Ghidra were not rerun during this specific iteration**. Ghidra 12.1.4 is not installed in the current execution environment; the targeted Ghidra instruction check remains pending.

## Status

- Original data integrity: previously verified for 81/81 IDF files.
- Original application starts with legitimate license: **not demonstrated**.
- IDF structure and decoder: **not established**.
- New PE entrypoint/section evidence: **verified**.
- New synthetic tests: **4/4 locally PASS**; Windows CI: **66/66 tests PASS**, compiled EXE and GUI smoke test PASS.
