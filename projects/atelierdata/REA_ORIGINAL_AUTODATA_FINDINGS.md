# REA 6.8.0 — Autodata static analysis, original private binary (2026-10-30)

REA (official `morluto/rea`, npm `rea-agents@6.8.0`) was **actually executed locally** on the source owner's `ADBCD.exe` and three Chilkat DLLs from their private Autodata archive, without uploading any original program content to this public repository.

**Source provenance:** `autodata_part_0001.zip` + `autodata_part_0004.zip` read through permitted means; 12 input files were validated against the original `INVENTAR.json` SHA256 chunks. This is a *partial* set, not the complete 139 files.

## Direct REA findings

| Original target | REA command | Result |
| --- | --- | --- |
| `ADCDA2/ADBCD.exe` | `inspect-pe-imports` | PASS, PE32 x86, imported DLLs KERNEL32, USER32, ADVAPI32, MSVCRT; 52 warnings/uncertain delay-load observations |
| `ADCDA2/ChilkatCert.dll` | `inspect-pe-imports` | PASS, PE32 x86 |
| `ADCDA2/ChilkatCrypt2.dll` | `inspect-pe-imports` | PASS, PE32 x86; declares functions from ADVAPI32 and CRYPT32, including CryptEncryptMessage/CryptDecryptMessage |
| `ADCDA2/ChilkatUtil.dll` | `inspect-pe-imports` | PASS, PE32 x86 |
| Verified partial `ADCDA2/` directory | `inspect-desktop-application` | PASS, 14 observed entries (includes directories), 4 bounded file probes; no detected runtime-family marker |
| `COMMON/CONST.IDF` | `inspect-artifact` | Unsupported binary format |
| `COMMON/MODELS.IDF` | `inspect-artifact` | Unsupported binary format |
| `ENG/DTC.IDF` | `inspect-artifact` | Unsupported binary format |

The `ADBCD.exe` delay-load table has 52 partial-coverage issues, including unsupported virtual-address forms and unreadable name ranges. Imports are not necessarily complete or reachable at runtime.

Chilkat cryptographic imports **do not prove** that the data files are encrypted with those functions. No `.IDF` decoder was established; no Autodata procedure, diagram, specification or full vehicle record was extracted. No part of the original application was executed, and no license protection was bypassed.

The complete REA Evidence JSON artifacts and a Romanian report are retained as conversation deliverables (private original files excluded).

## Reproducibility

- `.github/workflows/atelierdata-rea-analysis.yml` ran REA on the newly authored AtelierData app on Windows and published `AtelierData_REA_Static_Reports`: [CI run 41110122747](https://github.com/tzn5-web/leno/actions/runs/41110122747) — PASS.
- `.github/workflows/rea-offline-runtime.yml` built an isolated REA runtime on Ubuntu from the official npm package: [CI run 41110694843](https://github.com/tzn5-web/leno/actions/runs/41110694843) — PASS.
- `tools/cloud/autodata_rea_static_colab.ipynb` runs REA against the original `ADBCD.exe` privately in user-authorized Google Colab and writes evidence to Drive.

Next technically meaningful investigation: identify the legitimate data-format loader and obtain a supported, authorized export/format specification, without duplicating protected application code or bypassing license checks.


## Audit nou: apeluri IAT și nume API de acces la fișiere (2026-10-30)

S-a executat **efectiv**, local și exclusiv static, scriptul nou
[`pe_file_io_xrefs.py`](pe_file_io_xrefs.py) pe originalul privat
`ADBCD.exe`, cu SHA256 verificat
`a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
Nu a fost executat codul original și nu s-au accesat rutine de licențiere.

Rezultat reproductibil: PE32 x86, **17 intrări în tabela clasică de import**,
4 DLL-uri (`KERNEL32`, `USER32`, `ADVAPI32`, `MSVCRT`).
Au fost scanate **10.819.584 octeți** din 3 secțiuni marcate executabile.
S-au găsit **43 secvențe brute** `FF 15/FF 25` compatibile cu adrese IAT,
dintre care **19 secvențe** `FF 15` pentru `LoadLibraryA`.
Aceste secvențe sunt **candidați**, nu instrucțiuni validate prin dezasamblare.

`CreateFileA` (1 apariție ASCII), `CreateFileW` (1),
`ReadFile` (2) și `SetFilePointer` (1) apar literal în PE, însă
**nu sunt printre cele 17 importuri statice**. Scanarea brută nu a găsit
referințe LE32 directe către adresele acestor șiruri în secțiunile
marcate executabile. Nici `.IDF` nu apare literal (ASCII/UTF-16LE).
Interpretarea corectă este că **lanțul de acces la fișiere trebuie urmărit
prin rezolvare dinamică/importuri întârziate sau cod intermediar**;
nu s-a demonstrat încă mecanismul exact.

Testele sintetice ale scriptului au trecut local: **4/4**, inclusiv
respingerea SHA256 greșit, a unui antet PE invalid și separarea raportului
privat (offseturi) de agregatele publice. Testele au fost integrate în
workflow-ul Windows `atelierdata-windows.yml`; rezultatul CI pentru
această modificare trebuie verificat separat.

Rulare pe o copie privată autorizată:

~~~powershell
python projects/atelierdata/pe_file_io_xrefs.py --pe C:\PRIVATE\ADBCD.exe --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output C:\PRIVATE\iat-summary.json --private-output C:\PRIVATE\iat-details.json
~~~

Nu publica `iat-details.json` sau binarele originale. Datele brute
nu au fost urcate în repository. Scriptul nu decodează `.IDF`,
nu verifică licențe și nu stabilește fluxul de control. Următorul pas
Ghidra este confirmarea instrucțiunilor reale și a lanțului
`LoadLibraryA`/`GetProcAddress` către operațiile de citire a fișierelor.

### Verificare Ghidra pregătită, fără rezultat pretins

Scriptul Java nou `tools/ghidra/AtelierData_IAT_Instruction_Check.java`
citește raportul **privat** al analizei IAT, verifică SHA256-ul
raportului, apoi verifică dacă fiecare candidat brut corespunde unei
instrucțiuni `CALL`/`JMP` de 6 octeți recunoscute de Ghidra și
notează referințele existente. Este o verificare a limitelor de
instrucțiune, **nu** un decodor IDF. Nu modifică binarul.

Acest script Ghidra **nu a fost executat în această etapă**, deoarece
mediul curent nu include Ghidra. Raportul privat de intrare există
local și nu este publicat. Nu se pretinde validarea celor 43 candidați
de către Ghidra până la o rulare reală pe proiectul privat.


## Verificare statică suplimentară cu GNU objdump 2.44 (2026-10-31)

**Rulare reală** a scriptului nou `pe_static_call_alignment.py` asupra copiei private
`ADBCD.exe`, SHA256 `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`
verificat înainte de disassembly. S-a folosit `objdump -p` pentru tabela IAT și
`objdump -d -M intel` pentru dezasamblare liniară, fără lansarea executabilului.

- **17** importuri PE clasice, în **3** secțiuni cu flag executabil.
- **43** secvențe brute `FF 15/FF 25` care indică adrese IAT.
- **38/43** sunt aliniate cu instrucțiuni `call/jmp` în disassembly-ul liniar GNU;
  **5/43** nu sunt confirmate în această reprezentare.
- Cele **38** instrucțiuni candidate sunt în secțiunea `0000013`;
  dintre ele, **16** vizează `KERNEL32!LoadLibraryA`.
- Nu există instrucțiuni `call/jmp` aliniate cu `GetProcAddress` în
  această scanare. Acest lucru **nu dovedește absența** utilizării
  `GetProcAddress` prin alte forme de apel indirect.
- Nu s-a identificat un traseu demonstrat până la citirea `.IDF`,
  nici un decodor și niciun format de date validat.

**Limitare esențială:** `objdump -d` este o dezasamblare liniară;
poate interpreta date drept cod. Potrivirea celor 38 de instrucțiuni
nu dovedește că sunt accesibile din punctul de intrare sau că rulează.
**Ghidra CFG/xrefs nu a fost rulat în această etapă**, deci cele 38
rămân candidați de validat, nu funcții de încărcare IDF confirmate.

Scriptul nou are un autotest sintetic executat local cu rezultat
`PE_STATIC_CALL_ALIGNMENT_SELF_TEST=PASS` și este integrat în CI.
Nu au fost publicate binare, offseturi detaliate, resurse sau date
proprietare. Exemplu de rulare numai pe o copie privată autorizată:

```bash
python projects/atelierdata/pe_static_call_alignment.py --self-test
python projects/atelierdata/pe_static_call_alignment.py --pe /private/ADBCD.exe --output /private/pe-summary.json
```


## LoadLibrary literal argument triage — verified original (2026-10-31)

A new independent **read-only PE32 parser** was run on the privately held, owner-supplied original `ADBCD.exe`, with SHA256 verified first: `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`. No original executable or DLL was launched. The script only accepts direct adjacent x86 byte patterns `PUSH imm32; CALL dword ptr [LoadLibraryA IAT]`, resolves the immediate to a bounded ASCII DLL string, and produces a public **aggregate-only** JSON. Detailed addresses and strings stay private.

**Direct result:** 14 raw PUSH/CALL candidates, 13 resolving to 13 distinct DLL name literals, one unresolved. These are **byte-pattern candidates**, not proven reachable runtime calls. A GNU objdump disassembly explicitly started at the candidate instruction boundary shows a contiguous run of PUSH/CALL instructions, but the linear disassembly from the beginning of the section disagrees at the first PUSH. That is precisely why Ghidra function/CFG validation is still required.

**New and actionable runtime-family clue:** among the 13 literal candidates are `pbvm90.dll` and `libjcc.dll`, and the former is a PowerBuilder 9 virtual machine DLL. [PowerBuilder 9 documentation](https://pblib.com/knowledge-base/powerbuilder-runtime-files-pb-docs-90/) explicitly identifies `PBVM90.DLL` as the core runtime and `LIBJCC.DLL` as its dependency. **Inventory cross-check:** neither `pbvm90.dll` nor `libjcc.dll` appears as a standalone file among the 139 reconstructed inventory paths. If the candidate code is reachable, these runtime components may be supplied externally; this is not a proven missing-DLL launch error.

This supports **PowerBuilder 9 runtime compatibility as a working hypothesis**. It does not prove these calls execute, that PowerBuilder handles the IDF format, or that any particular .IDF decoder has been identified. A separate source lists the [PowerBuilder 9 Runtime Packager](https://pblib.com/knowledge-base/powerbuilder-runtime-packager-pb-docs-90/). **Do not download arbitrary DLLs or run the suspicious original to test the hypothesis.**

Reproducible code (no original files committed):
- `projects/atelierdata/pe_loadlibrary_literals.py`: SHA256 gate, strict PE32 import parsing, bounded static DLL argument matching, separate aggregate/private outputs.
- `projects/atelierdata/test_pe_loadlibrary_literals.py`: **four locally passing synthetic tests** (valid PE, privacy split, bad SHA/PE, invalid pointers and output collisions), also added to the Windows CI test discovery.
- `tools/ghidra/AtelierData_LoadLibrary_Argument_Check.java`: Ghidra script prepared to verify program MD5, instruction boundaries, operand bytes, referenced IAT slot and pointed-to strings. **Not executed in Ghidra during this run**; Java/Ghidra compatibility and CFG reachability remain unverified.

Private execution command (run only with an authorized local copy):
```powershell
python projects/atelierdata/pe_loadlibrary_literals.py --pe C:\PRIVATE\ADBCD.exe --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output C:\PRIVATE\loadlibrary-summary.json --private-output C:\PRIVATE\loadlibrary-details.json
```

**Boundary:** The reported 14/13 counts are verified locally on the original. The new GitHub Actions run and Ghidra script have not been confirmed successful; do not report them as PASS until inspected. The blocked ZIP 0016 was not accessed or bypassed.


## SHA256-gated fixed-stride evidence and Ghidra direct-call graph preparation (2026-10-31)

Real read-only local inspection of the owner-supplied `SGOPS.IDF`, `SGINT.IDF` and `FAS.IDF` (entire first chunk of each independently SHA256-verified) revealed long, constant-stride repetitions of an identical eight-byte token: 960 occurrences at 21-byte intervals in both SGOPS and SGINT, with matching token and offsets, and 870 occurrences at 19-byte intervals in FAS. These are **static structural observations**, not a demonstrated format, record decoder, decryption algorithm or source of usable vehicle data. See [IDF_STRIDE_EVIDENCE_20261031.md](IDF_STRIDE_EVIDENCE_20261031.md) and the synthetic-only regression tests.

The private Ghidra LoadLibrary script now also computes bounded membership in the **direct-call graph from Ghidra-declared entry-point functions**. It does not resolve dynamic or indirect calls, and a missing path is not proof of unreachability. **Ghidra has not been executed for this new code in this run**; no new Ghidra counts are asserted. No private data or binaries were published.


## Ghidra evidence identity and keyword scanner correctness (2026-10-31)

The private Ghidra LoadLibrary argument checker now records the **actual MD5 reported by Ghidra for the imported executable** as `source_md5`, after comparing it with the SHA256-gated Python triage's MD5. The Python Ghidra-report consistency validator rejects a missing or mismatched `source_md5`, even if a report claims `ghidra_executable_md5_verified=true`. This closes a concrete evidence-integrity gap: a Boolean alone did not bind the report to the expected imported program. The independent replay still recomputes the original PE SHA256 and triage evidence. These checks improve provenance consistency; they do **not** prove that a report was honestly produced by Ghidra, that code is reachable at runtime, or that IDF decoding works.

The static `AtelierData_IDF_Xrefs.py` memory scanner also now excludes matches fully contained in a previous chunk's overlap, while retaining patterns crossing chunk boundaries. Previously an occurrence within the 128-byte carry could be counted twice. This affects the correctness of **future** private keyword-hit counts; earlier reports should be re-generated before comparing counts.

Regression tests added: two for missing/wrong Ghidra MD5 and one for wrong MD5 in the SHA256-gated replay, all using **synthetic data only**. They are picked up by the existing `python -m unittest discover -s projects/atelierdata -p 'test_*.py' -v` Windows workflow. No original executable, DLL, proprietary IDF or private Ghidra report has been committed. The modified Ghidra scripts have **not been executed on the private original during this update**; GitHub Actions outcome for these commits is **not yet verified**. The blocked package 0016 remains untouched.


## 2026-10-31: independent PE-IAT / Ghidra evidence hardening

A concrete false-positive risk was found in `tools/ghidra/AtelierData_IAT_Instruction_Check.java`: the earlier script trusted the SHA256 string in a private triage report without checking the **identity of the executable actually imported into Ghidra**. It also accepted the `FF 15` / `FF 25` opcode and six-byte instruction length without comparing the embedded 32-bit target operand against the reported IAT address; unrelated references from an instruction could inflate the count.

Changes implemented:
- `pe_file_io_xrefs.py` now includes an independently computed **MD5 of the source PE** in its **private-only** report (existing SHA256 remains mandatory). The public summary does not expose the MD5 or addresses.
- The Ghidra Java script now **rejects** a mismatched `currentProgram.getExecutableMD5()`, validates the **exact little-endian 32-bit IAT operand** and counts only references to the expected IAT address on verified instructions.
- Each private Ghidra row includes numeric PE32 VA, kind, IAT target and identity metadata for deterministic independent replay.
- New `ghidra_iat_consistency.py` validates report schema, exact source SHA256/MD5, candidate addresses and symbols, kinds, IAT pointers, evidence flags and aggregate totals; writes only an **atomic, redacted aggregate**.
- `test_ghidra_iat_consistency.py` adds synthetic regression tests and is explicitly invoked in Windows CI.

Private reproduction, only on an authorized original copy:

```powershell
python projects/atelierdata/pe_file_io_xrefs.py --pe C:\PRIVATE\ADBCD.exe --expected-sha256 a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4 --public-output C:\PRIVATE\iat-summary.json --private-output C:\PRIVATE\iat-private.json
# In a private Ghidra headless project, after auto-analysis:
# -postScript AtelierData_IAT_Instruction_Check.java C:\PRIVATE\iat-private.json C:\PRIVATE\ghidra-iat-private.json a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4
python projects/atelierdata/ghidra_iat_consistency.py --private-triage C:\PRIVATE\iat-private.json --private-ghidra C:\PRIVATE\ghidra-iat-private.json --public-output C:\PRIVATE\iat-public-aggregate.json
```

**Proof boundary:** the Java script was changed but **has not yet been run against the original in Ghidra** in this update. Python tests use synthetic PE bytes, not private application code. Neither MD5 matching nor instruction/IAT cross-reference matching proves an IDF decoder, a reachable loader, or any legal right to extract proprietary data. No protected ZIP, PE, IDF or private report was committed.
