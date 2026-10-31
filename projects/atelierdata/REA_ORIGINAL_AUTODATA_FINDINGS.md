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
