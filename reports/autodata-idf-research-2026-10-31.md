# Autodata 3.45 — targeted GitHub/web research and IDF evidence (2026-10-31)

## Purpose

Research the original Autodata 3.45 archive's **.IDF data format**, rather than creating a replacement application. This is a static-analysis project. Source ZIP files and proprietary data remain in the user's Google Drive, not in GitHub. No Azure, executable launch, licensing bypass, keygen, emulator, or provider malware-block bypass.

## Internet/GitHub findings (retrieved 2026-10-31)

1. Public GitHub code searches for exact identifiers `TDGRAPH.IDF`, `MIDLINKS.IDF` and `MODELS.IDF` paired with Autodata did not yield an independently demonstrable IDF parser. An absence of search matches is **not** proof that no parser exists.
2. An older Autodata CD-3 v8.770 file listing includes the same distinctive names: `ADBCD.EXE`, `COMMON/MODELS.IDF`, `MIDLINKS.IDF`, `TDGRAPH.IDF`, `GRAPHICS/WDGRAPH.IDF`. This establishes a file-family correspondence but not matching binary format/version or readability. Source: https://www.advanceduninstaller.com/Autodata-CD-3-v8_770-0a615a28641b9e19bcfefc15fbc41d6d-application.htm .
3. A discussion from 2018 about Autodata 3.45 IDF asks how to open/translate the files and documents unsuccessful attempts using unrelated applications. No working extraction proof was found in the examined discussion. Source: https://carmasters.org/topic/10739-autodata-345_free-for-all/page/12/ .
4. The official Autodata Group API exposes licensed technical data using REST and JSON/XML; this is an alternative **authorized data source**, not a parser for these historical IDF files. https://developer.autodata-group.com/docs/read/Home .
5. Relevant open-source research instruments (not Autodata-specific parsers):
   - ImHex https://github.com/WerWolv/ImHex — binary visual analysis, Pattern Language;
   - Binwalk https://github.com/ReFirmLabs/binwalk — signatures, entropy, embedded formats; use **inspection only**, not auto-extraction of untrusted active content;
   - Kaitai Struct https://github.com/kaitai-io/kaitai_struct — specify a **verified** data layout as a .ksy parser;
   - Detect It Easy https://github.com/horsicq/Detect-It-Easy — classify files and statically inspect PE resources;
   - Ghidra https://github.com/NationalSecurityAgency/ghidra — **static** cross-reference inspection in the original PE module, especially file-opening, reading and decode paths. Do not execute the EXE.

## Findings from local read-only data samples

Local sample set: 66 ZIP entries whose file name ends in `.IDF` or `.IDF.chunkNNNN`, from available ZIP parts 0001, 0002, and 0004; maximum 65,536 read-only sample bytes per entry. Results:
- 61 / 66 samples have Shannon entropy >=7.8 bits/byte (sample-level, not whole-file statistics);
- zero samples begin with common ZIP, GZIP, zlib, SQLite, OLE, PNG, JPG, BMP, PDF, 7z or RAR signatures;
- small IDF entries `CONST.IDF` (10 bytes) and `TDDIFF.IDF` (42 bytes) have lower entropy, as expected from sample length;
- some entries have repeated 4-byte blocks, notably `FAS.IDF`, `MIDS.IDF`, `MIDTDoc.IDF`, `SGINT.IDF`, `SGOPS.IDF`. Repetition is measurable and merits further statistical study.
- A **read-only** ASCII-string sweep of `ADBCD.exe` finds ordinary Windows file I/O names and a zlib-style `incorrect header check` error message; this **does not establish** that the IDF loader calls zlib or that the IDF payload is zlib-compressed.

**No decryption claim:** high entropy can indicate encryption, compression, obfuscation or other dense binary encoding. No common magic signature at offset zero proves only that the listed signatures were absent at that offset.

## Next evidence gates

1. Run read-only signature/entropy profiling on **all 81 logical IDFs** from the already verified accessible ZIP entries, with cross-chunk continuity where needed. Report aggregate hashes/offsets/statistics only.
2. Compare fixed-window entropy, block-repetition, adjacent-byte correlation, frequency and possible record boundaries across files of the same family; always retain falsifiable hypotheses.
3. Statically inspect `ADBCD.exe` and relevant dependencies with Ghidra/DiE, mapping strings and file-I/O call sites to the actual IDF reading path. Do not run any original code; do not assume that zlib strings belong to the relevant pathway.
4. Publish a `.ksy` **only after** a candidate structure can be independently validated on multiple distinct files and multiple records.
5. AI can help classify, draft parsers and compare hypotheses, but **cannot infer a correct decoder from entropy alone** or bypass cryptographic security without evidence.
6. `autodata_part_0016.zip` remains blocked by Google Drive's provider malware assessment; no retries using abuse bypass or mirror distribution.

Success means demonstrably parsed data fields with validations and documented uncertainty; the manifest's hash PASS and graphical similarity are not sufficient.

## AI-assisted reverse engineering options (research update)

- **GhidrAssist** https://github.com/symgraph/GhidrAssist integrates LLM explanations of decompiled functions in Ghidra; local Ollama or other compatible hosted model can be used. The model's hypotheses must be checked against real data.
- **GhidrAssistMCP** https://github.com/symgraph/GhidrAssistMCP exposes Ghidra analysis tools via MCP to AI agents.
- **ghidra-headless-mcp** https://github.com/mrphrazer/ghidra-headless-mcp describes a headless workflow; despite read-only program mode, its scripting execution interface is **not a general sandbox**. Such tooling should run in an isolated environment and should not be given broad host execution privileges.
- **ghidra-mcp** https://github.com/bethington/ghidra-mcp provides many static and dynamic features. Only static read-only endpoints are appropriate for this task; debugger/launch/pcode-emulation operations are **out of scope**.

Recommended investigation: first correlate `ADBCD.exe` PE imports and file-reading references to IDF filenames in **static decompiled code**, then use the observations to draft candidate record/transform layout; validate it on multiple independent IDFs. Avoid sending proprietary binary samples to public AI tools without permission, or triggering any program's execution.
